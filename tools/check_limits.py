#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["openai", "rich", "typer"]
# ///
"""Check OpenAI API rate limits by making a minimal API call and inspecting headers."""

from datetime import datetime, timedelta

import typer
from openai import OpenAI
from rich.console import Console
from rich.table import Table

app = typer.Typer()
console = Console()


def parse_reset_time(reset_str: str) -> str:
    """Parse reset time string like '1s' or '2m30s' into human readable format."""
    if not reset_str:
        return "N/A"
    return reset_str


def format_number(val: str | None) -> str:
    """Format number with commas."""
    if val is None:
        return "N/A"
    try:
        return f"{int(val):,}"
    except ValueError:
        return val


@app.command()
def check(
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="Model to check limits for"),
):
    """Check rate limits by making a minimal API call."""
    client = OpenAI()

    console.print(f"\n[bold]Checking rate limits for model: [cyan]{model}[/cyan][/bold]\n")

    # gpt-5 reasoning models need more tokens (min ~1000 for reasoning)
    kwargs = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
    if model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = 1024
    else:
        kwargs["max_tokens"] = 1

    with console.status("Making minimal API call..."):
        response = client.chat.completions.with_raw_response.create(**kwargs)

    headers = response.headers

    table = Table(title="Rate Limit Status", show_header=True, header_style="bold magenta")
    table.add_column("Metric", style="cyan")
    table.add_column("Requests", justify="right")
    table.add_column("Tokens", justify="right")

    limit_req = headers.get("x-ratelimit-limit-requests")
    limit_tok = headers.get("x-ratelimit-limit-tokens")
    remaining_req = headers.get("x-ratelimit-remaining-requests")
    remaining_tok = headers.get("x-ratelimit-remaining-tokens")
    reset_req = headers.get("x-ratelimit-reset-requests")
    reset_tok = headers.get("x-ratelimit-reset-tokens")

    table.add_row("Limit (per minute)", format_number(limit_req), format_number(limit_tok))
    table.add_row("Remaining", format_number(remaining_req), format_number(remaining_tok))
    table.add_row("Resets in", parse_reset_time(reset_req), parse_reset_time(reset_tok))

    if remaining_req and limit_req:
        used_req = int(limit_req) - int(remaining_req)
        used_tok = int(limit_tok) - int(remaining_tok) if remaining_tok and limit_tok else 0
        table.add_row("Used", format_number(str(used_req)), format_number(str(used_tok)))

        pct_req = (int(remaining_req) / int(limit_req)) * 100
        pct_tok = (int(remaining_tok) / int(limit_tok)) * 100 if remaining_tok and limit_tok else 0
        table.add_row("Available %", f"{pct_req:.1f}%", f"{pct_tok:.1f}%")

    console.print(table)

    if remaining_req and limit_req:
        pct = (int(remaining_req) / int(limit_req)) * 100
        if pct < 10:
            console.print("\n[bold red]WARNING: Less than 10% of request quota remaining![/bold red]")
        elif pct < 25:
            console.print("\n[yellow]Note: Less than 25% of request quota remaining[/yellow]")
        else:
            console.print("\n[green]Rate limits look healthy[/green]")

    console.print(f"\n[dim]Timestamp: {datetime.now().isoformat()}[/dim]")


@app.command()
def headers(
    model: str = typer.Option("gpt-4o-mini", "--model", "-m", help="Model to check"),
):
    """Show all rate-limit related headers from the API response."""
    client = OpenAI()

    console.print(f"\n[bold]Raw headers for model: [cyan]{model}[/cyan][/bold]\n")

    kwargs = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
    if model.startswith("gpt-5"):
        kwargs["max_completion_tokens"] = 1024
    else:
        kwargs["max_tokens"] = 1

    with console.status("Making minimal API call..."):
        response = client.chat.completions.with_raw_response.create(**kwargs)

    table = Table(title="All Rate Limit Headers", show_header=True, header_style="bold magenta")
    table.add_column("Header", style="cyan")
    table.add_column("Value", style="green")

    for key, value in sorted(response.headers.items()):
        if "ratelimit" in key.lower() or "retry" in key.lower():
            table.add_row(key, value)

    console.print(table)


if __name__ == "__main__":
    app()
