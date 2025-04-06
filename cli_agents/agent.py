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
console = Console()

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

def process_content(args) -> str:
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

    # # Temporarily disable live display during pmap
    # if live_display:
    #     live_display.stop()

    outputs = pmap(helper,
                  range(len(chunks)),
                  n_jobs=args.n_jobs,
                  prefer='threads',
                  desc=args.file_path.name,
                  )

    return '\n'.join(outputs)
def create_status_panel(files, current_file=None):
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
        ),
        padding=(0, 1)
    )

def create_system_prompt_panel(system_prompt):
    """Create a panel displaying the system prompt."""
    return Panel(
        f"[italic][cyan]{system_prompt}[/][/]",
        title="[bold]System Prompt[/]",
        border_style="green",
        padding=(1, 2)
    )

def create_combined_panel(global_args) -> Panel:
    # Load system prompt for the selected tool
    system_prompt, _ = load_config(global_args)

    return Panel(
        Group(
            # Arguments section
            Panel(
                Columns([
                    f"[bold]Tool:[/] [cyan]{global_args.tool}[/]",
                    f"[bold]Files:[/] [cyan]{len(global_args.files)} file(s)[/]",
                    f"[bold]In-place edit:[/] [{'green' if global_args.inplace else 'red'}]{global_args.inplace}[/]",
                    f"[bold]Parallel jobs:[/] [cyan]{global_args.n_jobs}[/]",
                    f"[bold]Chunk size:[/] [cyan]{global_args.chunk_size}[/]",
                    f"[bold]Clear backups:[/] [{'green' if global_args.clear_bkup else 'red'}]{global_args.clear_bkup}[/]",
                    f"[bold]API key:[/] [cyan]{global_args.api_key[:8]}...[/]"
                ], equal=True, expand=True),
                title="[bold]Arguments[/]",
                border_style="blue"
            ),
            # Files section
            create_status_panel(global_args.files),
            # System prompt section
            create_system_prompt_panel(system_prompt) if global_args.show_prompt else "",
        ),
        title="[bold]Processing Configuration[/]",
        border_style="cyan"
    )

def main(
    tool: str,
    *files: ExistingFile,
    inplace: bool = True,
    n_jobs: PositiveInt = 10,
    chunk_size: PositiveInt = CHUNK_SIZE,
    clear_bkup: bool = False,
    show_prompt: bool = False
):
    """Process multiple files with the specified tool."""
    if not files:
        raise ValueError("At least one input file is required")

    api_key = os.getenv("OPENAI_API_KEY", "")
    client = OpenAI(api_key=api_key)
    global_args = SimpleNamespace(
        tool=tool,
        files=files,
        inplace=inplace,
        n_jobs=n_jobs,
        chunk_size=chunk_size,
        clear_bkup=clear_bkup,
        show_prompt=show_prompt,
        api_key=api_key,
    )
    combined_panel = create_combined_panel(global_args)
    console.print(combined_panel)
    console.print(f"[bold]Processing {len(files)} files with {tool}[/]")

    for file in files:
        args = SimpleNamespace(
            tool=tool,
            file=file,
            inplace=inplace,
            n_jobs=n_jobs,
            chunk_size=chunk_size,
            client=client,
            clear_bkup=clear_bkup
        )
        args.system_prompt, args.model = load_config(args)
        args.file_path = Path(file)

        if (output := check_completed_chunks(args)) is None:
            output = process_content(args)

        if args.inplace:
            backup = f"{args.file}.bak"
            # First create the backup

            Path(backup).write_bytes(Path(args.file).read_bytes())
            # Then write the new content to the original file
            Path(args.file).write_text(output)

        if clear_bkup:
            Path(backup).unlink()
            get_chunk_dir(args).rmdir()

    console.print("[bold green]All files processed successfully![/]")

if __name__ == "__main__":
    run(main)
