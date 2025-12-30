#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "dspy",
#     "python-dotenv",
#     "typer",
#     "rich>=13.7.1",
#     "httpx",
#     "pydantic>=2.0.0",
# ]
# ///

import os
import json
from pathlib import Path
from typing import Optional, Literal
import dspy
import typer
import httpx
from rich.console import Console
from dotenv import load_dotenv

# Import models and utilities from shared module
from summarize_url_models import (
    URLSummaryCompact,
    URLSummaryFull,
    SYS_PROMPT,
    get_schema_from_pydantic,
)
from url_renderers import render_overview, render_one_pager, render_report

console = Console()
app = typer.Typer(add_completion=False)


def fetch_markdown_content(url: str) -> Optional[str]:
    """Fetch markdown content by prepending https://markdown.new/ to the URL"""
    markdown_url = f"https://markdown.new/{url}"
    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as client:
            response = client.get(markdown_url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        console.print(f"[red]Error fetching markdown: {e}[/red]")
        return None


def extract_structured_data(
    markdown_content: str,
    url: str,
    schema_model: type,
    instructions: str,
) -> Optional[dict]:
    """Use dspy to extract structured data from markdown content"""
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        console.print("[red]OPENAI_API_KEY is not set[/red]")
        return None

    # Configure dspy with OpenAI
    lm = dspy.LM("openai/gpt-4o-mini", api_key=api_key)
    dspy.configure(lm=lm)

    # Define the extraction signature
    class ExtractionSignature(dspy.Signature):
        """Extract comprehensive structured information from webpage markdown content."""

        url: str = dspy.InputField(desc="The original URL")
        markdown: str = dspy.InputField(desc="Markdown content from the webpage")
        result: schema_model = dspy.OutputField(desc=instructions)

    # Create predictor
    predictor = dspy.Predict(ExtractionSignature)

    try:
        # Extract structured data
        response = predictor(url=url, markdown=markdown_content[:50000])

        # The result field contains the Pydantic model instance
        return response.result.model_dump()

    except Exception as e:
        console.print(f"[red]Error extracting structured data: {e}[/red]")
        import traceback
        console.print(f"[red]{traceback.format_exc()}[/red]")
        return None


@app.command()
def quick(
    url: str,
    format: Literal["overview"] = typer.Option(
        "overview", "--format", "-f", help="Output format (only 'overview' available for quick mode)"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save JSON output to file"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Extract compact summary from URL (fast, essential fields only)."""
    # Fetch markdown content
    markdown_content = fetch_markdown_content(url)
    if not markdown_content:
        console.print("[red]Failed to fetch markdown content[/red]")
        raise typer.Exit(1)

    # Extract structured data
    instructions = "Extract structured information from this webpage according to the provided schema."
    result = extract_structured_data(markdown_content, url, URLSummaryCompact, instructions)

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
    format: Literal["overview", "1-pager", "report"] = typer.Option(
        "overview", "--format", "-f", help="Output format: overview, 1-pager, or report"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Save JSON output to file"),
    markdown_only: bool = typer.Option(False, "--markdown-only", "-m", help="Output only the markdown text"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output raw JSON"),
):
    """Extract comprehensive structured data from URL (all fields)."""
    # Fetch markdown content
    markdown_content = fetch_markdown_content(url)
    if not markdown_content:
        console.print("[red]Failed to fetch markdown content[/red]")
        raise typer.Exit(1)

    # Extract structured data
    result = extract_structured_data(markdown_content, url, URLSummaryFull, SYS_PROMPT)

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


def main():
    app()


if __name__ == "__main__":
    main()
