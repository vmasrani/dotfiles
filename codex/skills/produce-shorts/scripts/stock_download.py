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
"""Download a synthesis-selected stock asset and append it to clip.yaml.

Fetches the asset's metadata from the provider API (verifying it really
exists), downloads the best-quality file variant to
`<clip-dir>/assets/<asset-id>-<slug>.mp4`, hashes and ffprobes the downloaded
file, and appends a schema-complete `Asset` entry to `<clip-dir>/clip.yaml`
(see references/schemas.md). Round-trips clip.yaml through pslib's
load_clip/save_clip so nothing else in the manifest is touched.

Asset IDs are stable/append-only (references/schemas.md): this script refuses
to overwrite an existing asset id in the manifest.

Usage:
    stock_download.py PROVIDER PROVIDER_ID --clip-dir DIR --asset-id A03
                       [--creator NAME] [--used-in S03,S04]
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
from pathlib import Path

import httpx
import typer
import yaml
from loguru import logger
from rich.console import Console

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import pslib  # noqa: E402 (script dir must be on sys.path first)

CONFIG_PATH = SCRIPT_DIR.parent / "config" / "defaults.yaml"

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

logger.remove()
logger.add(sys.stderr, format="<level>{level: <8}</level> {message}", level="INFO")


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
            "never download without it."
        )
        raise typer.Exit(1)
    return key


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "asset"


def suggest_next_id(asset_id: str, existing_ids: set[str]) -> str:
    m = re.match(r"^([A-Za-z]+)(\d+)$", asset_id)
    if not m:
        return "a new, unused ID"
    prefix, digits = m.group(1), m.group(2)
    width = len(digits)
    nums = []
    for i in existing_ids:
        im = re.match(rf"^{re.escape(prefix)}(\d+)$", i)
        if im:
            nums.append(int(im.group(1)))
    nxt = (max(nums) + 1) if nums else 1
    return f"{prefix}{nxt:0{width}d}"


# ---------------------------------------------------------------------------
# Provider metadata fetch — verifies the asset really exists, never guesses
# ---------------------------------------------------------------------------


def fetch_pexels_metadata(provider_id: str, api_key: str) -> dict:
    resp = httpx.get(
        f"https://api.pexels.com/videos/videos/{provider_id}",
        headers={"Authorization": api_key},
        timeout=30.0,
    )
    if resp.status_code == 404:
        console.print(
            f"[bold red]ERROR[/] Pexels asset [cyan]{provider_id}[/] does not exist (404) — "
            "verify the provider_asset_id from stock_search.py output"
        )
        raise typer.Exit(1)
    if resp.status_code != 200:
        console.print(f"[bold red]ERROR[/] Pexels API returned {resp.status_code}: {resp.text}")
        raise typer.Exit(1)
    v = resp.json()
    files = [f for f in v.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("link")]
    if not files:
        console.print(f"[bold red]ERROR[/] Pexels asset {provider_id} has no downloadable mp4 file variants")
        raise typer.Exit(1)
    best = max(files, key=lambda f: f.get("width") or 0)
    tail = v["url"].rstrip("/").rsplit("/", 1)[-1]
    return {
        "source_url": v["url"],
        "creator": v["user"]["name"],
        "download_url": best["link"],
        "slug": slugify(tail) or f"pexels-{provider_id}",
    }


def fetch_pixabay_metadata(provider_id: str, api_key: str) -> dict:
    resp = httpx.get(
        "https://pixabay.com/api/videos/",
        params={"key": api_key, "id": provider_id},
        timeout=30.0,
    )
    if resp.status_code != 200:
        console.print(f"[bold red]ERROR[/] Pixabay API returned {resp.status_code}: {resp.text}")
        raise typer.Exit(1)
    hits = resp.json().get("hits", [])
    if not hits:
        console.print(
            f"[bold red]ERROR[/] Pixabay asset [cyan]{provider_id}[/] does not exist or is not "
            "visible to this API key — verify the provider_asset_id from stock_search.py output"
        )
        raise typer.Exit(1)
    v = hits[0]
    tiers = v.get("videos", {})
    tier = tiers.get("large") or tiers.get("medium") or tiers.get("small") or tiers.get("tiny")
    if not tier or not tier.get("url"):
        console.print(f"[bold red]ERROR[/] Pixabay asset {provider_id} has no downloadable file variants")
        raise typer.Exit(1)
    tags = v.get("tags", "")
    slug_source = tags.split(",")[0].strip() if tags else ""
    return {
        "source_url": v.get("pageURL") or f"https://pixabay.com/videos/id-{provider_id}/",
        "creator": v.get("user") or "unknown",
        "download_url": tier["url"],
        "slug": slugify(slug_source) or f"pixabay-{provider_id}",
    }


PROVIDER_FETCH = {"pexels": fetch_pexels_metadata, "pixabay": fetch_pixabay_metadata}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@app.command()
def main(
    provider: str = typer.Argument(..., help="Configured provider key, e.g. pexels or pixabay"),
    provider_id: str = typer.Argument(..., help="Provider's asset ID, from stock_search.py output"),
    clip_dir: Path = typer.Option(..., "--clip-dir", help="Clip directory containing clip.yaml"),
    asset_id: str = typer.Option(..., "--asset-id", help="New stable asset ID, e.g. A04 (append-only)"),
    creator: str = typer.Option(None, "--creator", help="Override creator name if API metadata is missing/wrong"),
    used_in: str = typer.Option(None, "--used-in", help="Comma-separated segment IDs, e.g. S03,S04"),
) -> None:
    """Download PROVIDER's PROVIDER_ID into --clip-dir and append it to clip.yaml."""
    providers = load_providers()
    if provider not in providers:
        console.print(
            f"[bold red]ERROR[/] unknown provider [cyan]{provider}[/]. "
            f"Configured providers: {', '.join(sorted(providers))}"
        )
        raise typer.Exit(1)
    cfg = providers[provider]
    fetch_fn = PROVIDER_FETCH.get(provider)
    if fetch_fn is None:
        console.print(f"[bold red]ERROR[/] provider [cyan]{provider}[/] is configured but has no download implementation")
        raise typer.Exit(1)

    clip_dir = clip_dir.resolve()
    clip_path = clip_dir / "clip.yaml"
    if not clip_path.is_file():
        console.print(f"[bold red]ERROR[/] no clip.yaml at {clip_path}")
        raise typer.Exit(1)
    clip = pslib.load_clip(clip_path)

    existing_ids = {a.id for a in clip.assets}
    if asset_id in existing_ids:
        console.print(
            f"[bold red]ERROR[/] asset id [cyan]{asset_id}[/] already exists in {clip_path} — "
            "asset IDs are stable/append-only; pick a new, unused ID "
            f"(e.g. {suggest_next_id(asset_id, existing_ids)}), never overwrite one"
        )
        raise typer.Exit(1)

    # Cheap local checks (config, duplicate ID) happen before any network call
    # or API-key requirement, so this refusal works even without credentials.
    api_key = require_api_key(provider, cfg)

    logger.info(f"fetching {provider} metadata for asset {provider_id}")
    meta = fetch_fn(provider_id, api_key)

    assets_dir = clip_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    dest = assets_dir / f"{asset_id}-{meta['slug']}.mp4"
    if dest.exists():
        console.print(f"[bold red]ERROR[/] {dest} already exists on disk — remove it or pick a different asset id")
        raise typer.Exit(1)

    logger.info(f"downloading {meta['download_url']} -> {dest}")
    with httpx.stream("GET", meta["download_url"], timeout=120.0, follow_redirects=True) as resp:
        if resp.status_code != 200:
            console.print(f"[bold red]ERROR[/] download failed with HTTP {resp.status_code}: {meta['download_url']}")
            raise typer.Exit(1)
        with dest.open("wb") as fh:
            for chunk in resp.iter_bytes():
                fh.write(chunk)

    sha = pslib.sha256_file(dest)
    probe = pslib.ffprobe_media(dest)
    if probe.width is None or probe.height is None or probe.fps is None:
        console.print(f"[bold red]ERROR[/] downloaded file {dest} has no video stream (ffprobe found none)")
        raise typer.Exit(1)

    used_in_segments = [s.strip() for s in used_in.split(",") if s.strip()] if used_in else []

    asset = pslib.Asset(
        id=asset_id,
        provider=provider,
        provider_asset_id=provider_id,
        source_url=meta["source_url"],
        license=cfg["license"],
        entitlement="free",
        download_date=dt.date.today().isoformat(),
        creator=creator or meta["creator"],
        credit_required=bool(cfg["credit_required"]),
        width=probe.width,
        height=probe.height,
        fps=probe.fps,
        duration_s=probe.duration_s,
        file=f"assets/{dest.name}",
        sha256=sha,
        used_in_segments=used_in_segments,
    )

    clip.assets.append(asset)
    pslib.save_clip(clip_path, clip)

    console.print(
        f"[bold green]OK[/] appended asset [cyan]{asset_id}[/] to {clip_path} "
        f"({dest.name}, {probe.width}x{probe.height}@{probe.fps}fps, {probe.duration_s}s, "
        f"sha256={sha[:12]}…)"
    )


if __name__ == "__main__":
    app()
