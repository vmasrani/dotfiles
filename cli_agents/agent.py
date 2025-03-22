#!/usr/bin/env python3
import os
import random
import time
import json
from pathlib import Path
import yaml
from openai import OpenAI
from parallel import pmap
from cyclopts import run
from types import SimpleNamespace
from rich import print
from cyclopts.types import PositiveInt, ExistingFile
from rich.console import Console
from rich.panel import Panel
from rich.columns import Columns
from rich.console import Group
from rich.live import Live
from rich.layout import Layout

AGENT_CONFIG = Path.home() / "dotfiles" / "cli_agents" / "agent.yaml"
CHUNK_SIZE = 20  # lines

def make_chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

def estimate_llm_tokens(text: str) -> int:
    CHARS_PER_TOKEN = 4  # approximate
    return len(text) // CHARS_PER_TOKEN

def load_config(args) -> SimpleNamespace:
    config = yaml.safe_load(AGENT_CONFIG.read_text())
    system_prompt = config[args.tool]['system_prompt']
    model = config[args.tool].get('model', 'gpt-4')
    return system_prompt, model


def get_chunk_dir(args) -> Path:
    """Get the directory for storing chunk results."""
    chunk_dir = args.file_path.parent / f"{args.file_path.stem}_chunks"
    chunk_dir.mkdir(exist_ok=True)
    return chunk_dir

def get_chunk_path(chunk_dir: Path, chunk_index: int) -> Path:
    """Generate a path for saving a specific chunk result."""
    return chunk_dir / f"chunk_{chunk_index:04d}.txt"

def check_completed_chunks(args) -> str:
    """Check if all chunks are already processed and return combined result if so."""
    chunk_dir = get_chunk_dir(args)
    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
        return None

    total_chunks = json.loads(metadata_path.read_text())["total_chunks"]
    all_exist = all(get_chunk_path(chunk_dir, i).exists() for i in range(total_chunks))
    if all_exist:
        return '\n'.join(get_chunk_path(chunk_dir, i).read_text() for i in range(total_chunks))

    return None


def process_chunk(args, chunk, chunk_path:Path = None) -> str:
    """Process a single chunk with optional caching."""

    if chunk_path is not None and chunk_path.exists():
        return chunk_path.read_text()

    # Random delay between 0 and 2 seconds to avoid rate limiting
    time.sleep(random.uniform(0, 2))

    response = args.client.chat.completions.create(
        model=args.model,
        messages=[
            {"role": "system", "content": args.system_prompt},
            {"role": "user", "content": "\n".join(chunk)}
        ],
        timeout=300
    )
    result = response.choices[0].message.content

    # Save the result
    if chunk_path is not None:
        chunk_path.write_text(result)

    return result

def process_content(args, live_display=None) -> str:
    """Process content in chunks with fault tolerance."""
    lines = args.file_path.read_text().splitlines()
    total_lines = len(lines)

    if not lines:
        return ""

    chunks = list(make_chunks(lines, args.chunk_size))

    if len(chunks) == 1:
        return process_chunk(args, chunks[0])

    chunk_dir = get_chunk_dir(args)

    metadata = {
        "total_chunks": len(chunks),
        "lines_per_chunk": args.chunk_size,
        "total_lines": total_lines,
        "model": args.model,
        "timestamp": time.time(),
        "original_file": str(args.file_path)
    }

    metadata_path = chunk_dir / "metadata.json"
    if not metadata_path.exists():
         metadata_path.write_text(json.dumps(metadata, indent=2))

    helper = lambda i: (process_chunk(args, chunks[i], get_chunk_path(chunk_dir, i)))

    # Temporarily disable live display during pmap
    if live_display:
        live_display.stop()

    outputs = pmap(helper,
                  range(len(chunks)),
                  n_jobs=args.n_jobs,
                  prefer='threads',
                  desc=args.file_path.name,
                  transient=False)  # Changed to False to keep progress visible

    # Re-enable live display
    if live_display:
        live_display.start()

    return '\n'.join(outputs)

def create_status_panel(files, tool, api_key, n_jobs, chunk_size, current_file=None):
    """Create a status panel showing processed and pending files."""
    def get_file_status(file):
        if Path(f"{file}.bak").exists():
            return f"[green]✓ {file}[/]"  # Processed
        elif file == current_file:
            return f"[yellow]⋯ {file}[/]"  # Currently processing
        else:
            return f"[dim]• {file}[/]"     # Pending

    return Panel(
        Group(
            f"[bold]Processing {len(files)} files[/]",
            Columns(
                [get_file_status(file) for file in files],
                column_first=True,
                equal=True,
                expand=True
            ),
            f"Tool: [bold]{tool}[/] | Model: [green]gpt-4[/] | Chunk size: [yellow]{chunk_size}[/] | Jobs: [blue]{n_jobs}[/] | API Key: [dim]{api_key[:10]}{'*' * 10}[/]"
        ),
        padding=(0, 1)
    )

def main(
    tool: str,
    *files: ExistingFile,
    inplace: bool = True,
    n_jobs: PositiveInt = 10,
    chunk_size: PositiveInt = CHUNK_SIZE
):
    """Process multiple files with the specified tool."""
    if not files:
        raise ValueError("At least one input file is required")

    api_key = os.getenv("OPENAI_API_KEY", "")
    client = OpenAI(api_key=api_key)
    console = Console()

    console.print(f"[bold]Processing {len(files)} files with {tool}[/]")

    for file in files:
        console.print(f"[yellow]Processing[/] {file}...")

        args = SimpleNamespace(
            tool=tool,
            file=file,
            inplace=inplace,
            n_jobs=n_jobs,
            chunk_size=chunk_size,
            client=client
        )
        args.system_prompt, args.model = load_config(args)
        args.file_path = Path(file)

        if (output := check_completed_chunks(args)) is None:
            output = process_content(args)

        if args.inplace:
            backup = f"{args.file}.bak"
            Path(args.file).rename(backup)
            Path(args.file).write_text(output)

        console.print(f"[green]✓[/] Completed {file}")

    console.print("[bold green]All files processed successfully![/]")

if __name__ == "__main__":
    run(main)
