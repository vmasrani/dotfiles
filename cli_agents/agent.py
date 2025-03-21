#!/usr/bin/env python3
import sys
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

client = OpenAI()

def estimate_tokens(text: str) -> int:
    return len(text) // CHARS_PER_TOKEN

def process_chunk(chunk: str, model: str, system_prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": chunk}
            ],
            timeout=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Error in API call: {str(e)}")
        raise

def process_content(content: str, model: str, system_prompt: str) -> str:
    chunks = [content[i:i + CHUNK_SIZE] for i in range(0, len(content), CHUNK_SIZE)]
    logger.info(f"Split into {len(chunks)} chunks")
    outputs = pmap(lambda chunk: process_chunk(chunk, model, system_prompt), chunks, n_jobs=-1, prefer='threads')
    return '\n'.join(outputs)

def load_config(tool: str) -> tuple[str, str]:
    if not AGENT_CONFIG.exists():
        logger.error(f"Config file not found: {AGENT_CONFIG}")
        sys.exit(1)

    with open(AGENT_CONFIG) as f:
        config = yaml.safe_load(f)

    system_prompt = config[tool]['system_prompt']
    model = config[tool].get('model', 'gpt-4')
    return system_prompt, model

def main():
    try:
        if len(sys.argv) < 2:
            logger.error("Insufficient arguments")
            sys.exit(1)

        tool = sys.argv[1]
        file = sys.argv[2] if len(sys.argv) > 2 else None
        inplace = "--inplace" in sys.argv

        logger.info(f"Processing with tool: {tool}, file: {file}, inplace: {inplace}")

        system_prompt, model = load_config(tool)

        if file:
            file_path = Path(file)
            if not file_path.exists():
                logger.error(f"File not found: {file}")
                sys.exit(1)
            content = file_path.read_text()
            logger.info(f"Read {len(content)} characters from {file}")
        else:
            content = sys.stdin.read()
            logger.info(f"Read {len(content)} characters from stdin")

        output = process_content(content, model, system_prompt)

        if inplace and file:
            backup = f"{file}.bak"
            Path(file).rename(backup)
            Path(file).write_text(output)
            logger.info(f"Updated {file} (backup saved as {backup})")
        else:
            print(output)

    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
