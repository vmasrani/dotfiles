#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["rich", "pandas"]
# ///
import sys
import pickle
from pathlib import Path

from rich import print
from rich.panel import Panel
from rich.console import Console

console = Console(force_terminal=True)

file_path = Path(sys.argv[1])

with open(file_path, 'rb') as f:
    data = pickle.load(f)

console.print(Panel(f"[bold]{file_path.name}[/bold] | Type: [cyan]{type(data).__name__}[/cyan]", expand=False))

# Handle pandas objects specially
if hasattr(data, 'to_string'):
    console.print(data)
elif isinstance(data, dict):
    console.print(data)
elif isinstance(data, (list, tuple)) and len(data) > 0:
    console.print(f"Length: {len(data)}")
    console.print(data[:10] if len(data) > 10 else data)
else:
    console.print(data)
