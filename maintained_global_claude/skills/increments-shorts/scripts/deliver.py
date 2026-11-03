#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "httpx>=0.27", "platformdirs>=4", "pillow>=10"]
# ///
"""Assemble deliverables for one QC-passed clip: <slug>.mp4 (+ end tag), <slug>-thumbnail.jpg, <slug>.txt.

  deliver.py CLIP_DIR --title "..." --thumbnail path.jpg [--blog URL] [--hashtag X ...] [--tag t ...]

Reads the newest QC-passed final from clip.yaml render.versions, adds the end tag (endtag.py), copies the
thumbnail, writes the metadata txt (title, description, tags). Output: EPISODE/deliverables/.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
import yaml
from loguru import logger
from PIL import Image

from endtag import add_end_tag

app = typer.Typer(add_completion=False)
CHANNEL_URL = "https://www.incrementspodcast.com"
DEFAULT_TAGS = ["Increments Podcast", "podcast", "Bayesian", "philosophy"]
MAX_TITLE = 100


def build_description(episode_url: str, hashtags: list[str], blog_url: str | None = None) -> str:
    """Links + hashtags only, no commentary."""
    if len(hashtags) != 3:
        raise ValueError(f"exactly 3 hashtags expected, got {len(hashtags)}: {hashtags}")
    tags = [h if h.startswith("#") else f"#{h}" for h in hashtags]
    lines = [f"Full episode: {episode_url}"]
    if blog_url:
        lines.append(f"Blog post: {blog_url}")
    lines.append(f"Increments Podcast: {CHANNEL_URL}")
    return "\n".join(lines) + "\n\n" + " ".join(tags)


def check_title(title: str) -> str:
    t = title.strip()
    if not t or len(t) > MAX_TITLE:
        raise ValueError(f"title must be 1-{MAX_TITLE} characters, got {len(t)}")
    return t


def metadata_txt(title: str, description: str, tags: list[str]) -> str:
    return f"TITLE:\n{title}\n\nDESCRIPTION:\n{description}\n\nTAGS:\n{', '.join(tags)}\n"


def newest_passed_final(clip: dict, clip_dir: Path, profile: str) -> Path:
    versions = (clip.get("render") or {}).get("versions") or []
    passed = [v for v in versions if v.get("qc")]
    if clip["clip"].get("status") != "qc_passed" or not passed:
        raise RuntimeError(f"{clip_dir.name}: status is {clip['clip'].get('status')!r}, not qc_passed — render and QC first")
    rel = passed[-1]["finals"].get(profile)
    if not rel:
        raise RuntimeError(f"{clip_dir.name}: no final for profile {profile!r} in {passed[-1]['finals']}")
    return clip_dir / rel


@app.command()
def main(
    clip_dir: Path = typer.Argument(...),
    title: str = typer.Option(..., "--title"),
    thumbnail: Path = typer.Option(..., "--thumbnail", help="Chosen thumbnail jpg (1080x1920)"),
    hashtag: list[str] = typer.Option(..., "--hashtag", help="Exactly 3"),
    blog: str = typer.Option(None, "--blog", help="Blog post URL when the short quotes it"),
    tag: list[str] = typer.Option(None, "--tag", help="YouTube tags (default set if omitted)"),
    profile: str = typer.Option(None, "--profile", help="youtube-shorts (short) | youtube (clip)"),
) -> None:
    """Write deliverables for CLIP_DIR."""
    clip_dir = clip_dir.expanduser().resolve()
    root = clip_dir.parent.parent
    clip = yaml.safe_load((clip_dir / "clip.yaml").read_text())
    ep = yaml.safe_load((root / "episode.yaml").read_text())
    prof = profile or ("youtube-shorts" if clip["clip"]["format"] == "short" else "youtube")
    final = newest_passed_final(clip, clip_dir, prof)
    if not final.is_file():
        raise FileNotFoundError(final)
    if not thumbnail.is_file():
        raise FileNotFoundError(thumbnail)
    title = check_title(title)
    desc = build_description(ep["episode"]["source_url"], hashtag, blog)
    slug = clip["clip"]["id"]
    out = root / "deliverables"
    out.mkdir(exist_ok=True)
    add_end_tag(final, out / f"{slug}.mp4")
    Image.open(thumbnail).convert("RGB").save(out / f"{slug}-thumbnail.jpg", quality=92)
    (out / f"{slug}.txt").write_text(metadata_txt(title, desc, list(tag or DEFAULT_TAGS)))
    logger.info(f"deliverables for {slug} in {out}")
    print(out / f"{slug}.mp4")


if __name__ == "__main__":
    app()
