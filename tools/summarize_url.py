#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "tabstack>=0.1.0",
#     "typer>=0.12.0",
#     "rich>=13.7.1",
#     "pydantic>=2.0.0",
# ]
# ///

import asyncio
import os
import json
from pathlib import Path
from urllib.parse import urlparse
from tabstack import Tabstack
from pydantic import BaseModel
from typing import Optional, Literal
import typer
from rich.console import Console
from url_renderers import render_overview, render_one_pager, render_report
from summarize_url_models import (
    URLSummaryCompact,
    URLSummaryFull,
    SYS_PROMPT,
    get_schema_from_pydantic,
)

console = Console()
app = typer.Typer(add_completion=False)

@app.command()
def quick(
    url: str,
    format: Literal["overview"] = typer.Option("overview", "--format", "-f", help="Output format (only 'overview' available for quick mode)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save JSON output to file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Extract compact summary from URL (fast, essential fields only)."""
    result = asyncio.run(extract_url_async(url, URLSummaryCompact))

    if result is None:
        console.print("[red]Failed to extract content[/red]")
        raise typer.Exit(1)

    if json_output:
        print(json.dumps(result, indent=2))
    elif output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Saved to {output}[/green]")
    else:
        render_overview(result, console)

@app.command()
def full(
    url: str,
    format: Literal["overview", "1-pager", "report"] = typer.Option("overview", "--format", "-f", help="Output format: overview, 1-pager, or report"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save JSON output to file"),
    markdown_only: bool = typer.Option(False, "--markdown-only", "-m", help="Output only the markdown text"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Extract comprehensive structured data from URL (all fields)."""
    result = asyncio.run(extract_url_async(url, URLSummaryFull))

    if result is None:
        console.print("[red]Failed to extract content[/red]")
        raise typer.Exit(1)

    if markdown_only:
        console.print(result.get("markdown_text", ""))
        return

    if json_output:
        print(json.dumps(result, indent=2))
    elif output:
        output.write_text(json.dumps(result, indent=2))
        console.print(f"[green]Saved to {output}[/green]")
    else:
        # Select renderer based on format
        if format == "overview":
            render_overview(result, console)
        elif format == "1-pager":
            render_one_pager(result, console)
        elif format == "report":
            render_report(result, console)

async def extract_url_async(url: str, schema_model: type[BaseModel]) -> Optional[dict]:
    """Fetch URL and extract structured data using Tabstack generate API"""
    instructions = "Extract structured information from this webpage according to the provided schema."
    if schema_model == URLSummaryFull:
        instructions = SYS_PROMPT

    try:
        async with Tabstack(api_key=os.getenv('TABSTACK_API_KEY'), timeout=120.0) as tabs:
            result = await tabs.generate.json(
                url=url,
                schema=get_schema_from_pydantic(schema_model),
                instructions=instructions,
            )
            return result.data
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        return None

def main():
    app()

if __name__ == "__main__":
    main()
