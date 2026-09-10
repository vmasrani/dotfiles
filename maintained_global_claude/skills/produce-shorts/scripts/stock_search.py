#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "httpx>=0.27",
#   "pydantic>=2.7",
#   "PyYAML>=6.0",
# ]
# ///
"""Search a configured stock-footage provider for licensable B-roll.

Cardinal rule (references/assets.md): every result here comes from a real,
live API response. There is no offline/mock mode and no invented assets —
an unconfigured provider or a missing API key is a loud failure, never a
plausible-looking empty or fabricated result. A genuine zero-hit search is
a legitimate (and separately signalled) empty result, not an error.

Usage:
    stock_search.py PROVIDER QUERY [--min-width 1920] [--min-duration 4]
                     [--max-results 15] [--json]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx
import typer
import yaml
from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

SCRIPT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = SCRIPT_DIR.parent / "config" / "defaults.yaml"

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

logger.remove()
logger.add(sys.stderr, format="<level>{level: <8}</level> {message}", level="INFO")


class SearchResult(BaseModel):
    provider: str
    provider_asset_id: str
    width: int
    height: int
    fps: float | None
    duration_s: float
    url: str
    license: str
    best_file_url: str


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_providers() -> dict:
    if not CONFIG_PATH.is_file():
        console.print(f"[bold red]ERROR[/] missing provider config: {CONFIG_PATH}")
        raise typer.Exit(1)
    raw = yaml.safe_load(CONFIG_PATH.read_text())
    providers = raw.get("providers")
    if not providers:
        console.print(f"[bold red]ERROR[/] {CONFIG_PATH} has no `providers` block")
        raise typer.Exit(1)
    return providers


def require_api_key(provider: str, cfg: dict) -> str:
    env_var = cfg["api_key_env"]
    key = os.environ.get(env_var)
    if not key:
        console.print(
            f"[bold red]ERROR[/] provider [cyan]{provider}[/] requires env var "
            f"[yellow]{env_var}[/], which is not set. Export it and retry — "
            "never search without it."
        )
        raise typer.Exit(1)
    return key


# ---------------------------------------------------------------------------
# Provider search implementations — each returns UNFILTERED normalized results
# ---------------------------------------------------------------------------


def search_pexels(query: str, api_key: str, max_results: int, license_name: str) -> list[SearchResult]:
    resp = httpx.get(
        "https://api.pexels.com/videos/search",
        params={"query": query, "per_page": min(max(max_results, 1), 80)},
        headers={"Authorization": api_key},
        timeout=30.0,
    )
    if resp.status_code != 200:
        console.print(f"[bold red]ERROR[/] Pexels API returned {resp.status_code}: {resp.text}")
        raise typer.Exit(1)
    data = resp.json()
    results: list[SearchResult] = []
    for v in data.get("videos", []):
        files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link")]
        if not files:
            continue
        best = max(files, key=lambda f: f.get("width") or 0)
        results.append(
            SearchResult(
                provider="pexels",
                provider_asset_id=str(v["id"]),
                width=v["width"],
                height=v["height"],
                fps=best.get("fps"),
                duration_s=float(v["duration"]),
                url=v["url"],
                license=license_name,
                best_file_url=best["link"],
            )
        )
    return results


def search_pixabay(
    query: str, api_key: str, max_results: int, license_name: str, min_width: int
) -> list[SearchResult]:
    # Pixabay's video search accepts min_width/min_height server-side; duration
    # has no server-side filter so it is always applied client-side below.
    resp = httpx.get(
        "https://pixabay.com/api/videos/",
        params={
            "key": api_key,
            "q": query,
            "per_page": min(max(max_results, 3), 200),
            "min_width": min_width,
        },
        timeout=30.0,
    )
    if resp.status_code != 200:
        console.print(f"[bold red]ERROR[/] Pixabay API returned {resp.status_code}: {resp.text}")
        raise typer.Exit(1)
    data = resp.json()
    results: list[SearchResult] = []
    for v in data.get("hits", []):
        tiers = v.get("videos", {})
        tier = tiers.get("large") or tiers.get("medium") or tiers.get("small") or tiers.get("tiny")
        if not tier or not tier.get("url"):
            continue
        results.append(
            SearchResult(
                provider="pixabay",
                provider_asset_id=str(v["id"]),
                width=tier["width"],
                height=tier["height"],
                fps=None,  # Pixabay's search response carries no fps; the probe at
                #             download time is the fps of record for the manifest.
                duration_s=float(v["duration"]),
                url=v.get("pageURL") or f"https://pixabay.com/videos/id-{v['id']}/",
                license=license_name,
                best_file_url=tier["url"],
            )
        )
    return results


PROVIDER_SEARCH = {"pexels": search_pexels, "pixabay": search_pixabay}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    provider: str = typer.Argument(..., help="Configured provider key, e.g. pexels or pixabay"),
    query: str = typer.Argument(..., help="Search query"),
    min_width: int = typer.Option(1920, "--min-width", help="Minimum native width in pixels"),
    min_duration: float = typer.Option(4.0, "--min-duration", help="Minimum clip duration in seconds"),
    max_results: int = typer.Option(15, "--max-results", help="Maximum results to return"),
    json_output: bool = typer.Option(False, "--json", help="Emit a JSON array instead of a table"),
) -> None:
    """Search PROVIDER for QUERY and print real, API-verified B-roll candidates."""
    providers = load_providers()
    if provider not in providers:
        console.print(
            f"[bold red]ERROR[/] unknown provider [cyan]{provider}[/]. "
            f"Configured providers: {', '.join(sorted(providers))}"
        )
        raise typer.Exit(1)
    cfg = providers[provider]
    search_fn = PROVIDER_SEARCH.get(provider)
    if search_fn is None:
        console.print(f"[bold red]ERROR[/] provider [cyan]{provider}[/] is configured but has no search implementation")
        raise typer.Exit(1)
    api_key = require_api_key(provider, cfg)
    license_name = cfg["license"]

    logger.info(f"searching {provider} for {query!r} (min_width={min_width}, min_duration={min_duration}s)")
    if provider == "pixabay":
        raw_results = search_pixabay(query, api_key, max_results, license_name, min_width)
    else:
        raw_results = search_fn(query, api_key, max_results, license_name)

    filtered = [r for r in raw_results if r.width >= min_width and r.duration_s >= min_duration][:max_results]

    if json_output:
        print(json.dumps([r.model_dump() for r in filtered], indent=2))
        return

    if not filtered:
        console.print(
            f"[yellow]No results[/] for {provider} query {query!r} meeting "
            f"min_width={min_width}, min_duration={min_duration}s "
            f"({len(raw_results)} raw hit(s) before filtering). "
            "This is an honest empty result, not an error."
        )
        return

    table = Table(title=f"{provider} — {query!r} ({len(filtered)} result(s))")
    table.add_column("provider_asset_id")
    table.add_column("dimensions")
    table.add_column("fps")
    table.add_column("duration")
    table.add_column("url", overflow="fold")
    table.add_column("license")
    for r in filtered:
        table.add_row(
            r.provider_asset_id,
            f"{r.width}x{r.height}",
            f"{r.fps:.2f}" if r.fps is not None else "—",
            f"{r.duration_s:.1f}s",
            r.url,
            r.license,
        )
    console.print(table)


if __name__ == "__main__":
    app()
