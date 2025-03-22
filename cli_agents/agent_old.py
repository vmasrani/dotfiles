#!/usr/bin/env python3
import os
import random
import time
import sys
import json
import argparse
from pathlib import Path
import yaml
import logging
from openai import OpenAI
from parallel import pmap
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

AGENT_CONFIG = Path.home() / "dotfiles/cli_agents/agent.yaml"
CHUNK_SIZE = 8000  # characters (roughly 2000 tokens)

CHARS_PER_TOKEN = 4  # approximate

client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
)


def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN

def get_chunk_dir(file_path: Path) -> Path:
    """Get the directory for storing chunk results."""
    if file_path:
        # Create a directory alongside the original file
        chunk_dir = file_path.parent / f"{file_path.stem}_chunks"
    else:
        # For stdin input, create in the current directory
        chunk_dir = Path("stdin_chunks")

    chunk_dir.mkdir(exist_ok=True)
    return chunk_dir

def get_chunk_path(chunk_dir: Path, chunk_index: int) -> Path:
    """Generate a path for saving a specific chunk result."""
    return chunk_dir / f"chunk_{chunk_index:04d}.txt"

def process_chunk(args) -> str:
    """Process a single chunk with optional caching."""
    chunk, model, system_prompt, chunk_path = args

    if chunk_path.exists():
        logger.info(f"Using cached result for {chunk_path.name}")
        return chunk_path.read_text()

    # Random delay between 0 and 2 seconds to avoid rate limiting
    time.sleep(random.uniform(0, 2))

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": chunk}
        ],
        timeout=300
    )
    result = response.choices[0].message.content

    # Save the result
    chunk_path.write_text(result)
    logger.info(f"Saved chunk result to {chunk_path}")

    return result

def process_content(content: str, model: str, system_prompt: str, file_path: Path = None, n_jobs: int = 10, num_chunks: int = None) -> str:
    """Process content in chunks with fault tolerance."""
    # Split content into lines
    lines = content.splitlines()
    total_lines = len(lines)

    if not lines:
        return ""

    # Calculate how many lines per chunk
    if num_chunks and num_chunks > 0:
        lines_per_chunk = max(1, total_lines // num_chunks)
    else:
        # Use default CHUNK_SIZE to estimate number of chunks
        avg_line_length = len(content) / max(1, total_lines)  # avoid division by zero
        lines_per_chunk = max(1, int(CHUNK_SIZE / avg_line_length))

    # Create chunks by slicing the lines and joining them
    chunks = []
    for i in range(0, total_lines, lines_per_chunk):
        chunk_lines = lines[i:min(i + lines_per_chunk, total_lines)]
        chunks.append('\n'.join(chunk_lines))

    logger.info(f"Split into {len(chunks)} chunks of approximately {lines_per_chunk} lines each")

    # Create chunk directory and metadata
    chunk_dir = get_chunk_dir(file_path)

    metadata = {
        "total_chunks": len(chunks),
        "lines_per_chunk": lines_per_chunk,
        "total_lines": total_lines,
        "model": model,
        "timestamp": time.time(),
        "original_file": str(file_path) if file_path else "stdin"
    }

    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    # Process all chunks
    chunk_paths = [get_chunk_path(chunk_dir, i) for i in range(len(chunks))]
    args = [(chunk, model, system_prompt, path) for chunk, path in zip(chunks, chunk_paths)]

    # Single chunk or multiple chunks processing
    if len(chunks) == 1:
        outputs = [process_chunk(args[0])]
    else:
        outputs = pmap(process_chunk, args, n_jobs=n_jobs, prefer='threads')

    # Mark processing as complete
    (chunk_dir / "complete.flag").touch()

    return '\n'.join(outputs)

def check_completed_chunks(file_path: Path) -> str:
    """Check if all chunks are already processed and return combined result if so."""
    chunk_dir = get_chunk_dir(file_path)

    if not chunk_dir.exists():
        return None

    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
        return None

    with open(metadata_path) as f:
        metadata = json.load(f)

    total_chunks = metadata["total_chunks"]

    # Check if all chunk files exist
    all_exist = True
    chunks = []

    for i in range(total_chunks):
        chunk_path = get_chunk_path(chunk_dir, i)
        if not chunk_path.exists():
            all_exist = False
            break
        chunks.append(chunk_path.read_text())

    if all_exist:
        logger.info(f"All {total_chunks} chunks already processed. Using cached results.")
        return '\n'.join(chunks)

    return None

def load_config(tool: str) -> tuple[str, str]:
    if not AGENT_CONFIG.exists():
        logger.error(f"Config file not found: {AGENT_CONFIG}")
        sys.exit(1)

    config = yaml.safe_load(AGENT_CONFIG.read_text())
    system_prompt = config[tool]['system_prompt']
    model = config[tool].get('model', 'gpt-4')
    return system_prompt, model

def main():
    parser = argparse.ArgumentParser(description="Process text with AI tools")
    parser.add_argument("tool", help="The AI agent tool to use")
    parser.add_argument("file", nargs="?", help="Input file (optional, reads from stdin if not provided)")
    parser.add_argument("--inplace", action="store_true", help="Update file in place")
    parser.add_argument("--n_jobs", type=int, default=10, help="Number of parallel jobs for processing")
    parser.add_argument("--num_chunks", type=int, help="Override default chunking with specified number of chunks")

    args = parser.parse_args()
    logger.info(f"Processing with tool: {args.tool}, file: {args.file}, inplace: {args.inplace}, "
               f"n_jobs: {args.n_jobs}, num_chunks: {args.num_chunks}")

    system_prompt, model = load_config(args.tool)

    # Handle file input
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            logger.error(f"File not found: {args.file}")
            sys.exit(1)

        # Check for cached results first
        output = check_completed_chunks(file_path)
        if output is None:
            content = file_path.read_text()
            logger.info(f"Read {len(content)} characters from {args.file}")
            output = process_content(content, model, system_prompt, file_path,
                                    n_jobs=args.n_jobs, num_chunks=args.num_chunks)
    # Handle stdin input
    else:
        content = sys.stdin.read()
        logger.info(f"Read {len(content)} characters from stdin")
        output = process_content(content, model, system_prompt, None,
                                n_jobs=args.n_jobs, num_chunks=args.num_chunks)

    # Write output
    if args.inplace and args.file:
        backup = f"{args.file}.bak"
        Path(args.file).rename(backup)
        Path(args.file).write_text(output)
        logger.info(f"Updated {args.file} (backup saved as {backup})")
    else:
        print(output)

if __name__ == "__main__":
    main()
