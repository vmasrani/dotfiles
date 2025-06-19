#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "cyclopts",
#     "machine-learning-helpers",
#     "markitdown[all]",
#     "openai",
#     "pdf2image",
#     "pypdf2",
#     "pytesseract",
#     "pyyaml",
#     "rich",
#     "torch",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///
import os

from pathlib import Path
from openai import OpenAI
from cyclopts import App
from types import SimpleNamespace
from rich import print
from cyclopts.types import PositiveInt, ExistingFile
from rich.console import Console
from agent_utils import get_chunk_dir, check_completed_chunks, create_combined_panel, load_config, process_file_content, call_llm
from tools import PROCESS_FUNCTIONS


api_key = os.getenv("OPENAI_API_KEY", "")
client = OpenAI(api_key=api_key)

CHUNK_SIZE = 20  # lines
console = Console()

app = App()

@app.default
def stdio(tool: str,
          stdin: str,
          ):

    args = SimpleNamespace(tool=tool, stdin=stdin, client=client)
    args.system_prompt, args.model, preprocess_fn, postprocess_fn = load_config(args)

    if preprocess_fn:
        stdin_processed = PROCESS_FUNCTIONS[preprocess_fn](stdin)

    result = call_llm(args, stdin_processed)

    if postprocess_fn:
        args.stdin = stdin
        args.stdin_processed = stdin_processed
        args.result = result
        args.overwrite = False
        result = PROCESS_FUNCTIONS[postprocess_fn](args)

    print(result)

@app.command
def process_files(
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
            output = process_file_content(args)

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
    app()
