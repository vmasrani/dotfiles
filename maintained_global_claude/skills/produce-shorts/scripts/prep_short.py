#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""Render prep for one frozen short (references/render-qc.md § Shorts).

Runs, in order, everything the Remotion render needs and nothing else:
assemble_audio -> frame_segments -> align_subtitles -> validate_subtitles -> template workspace
(`CLIP_DIR/remotion/`, npm ci when the lockfile changed) -> gen-props.mjs.

It stops at `CLIP_DIR/remotion/props.json`; the render itself is the queued `npx remotion render`
command in render-qc.md. Prep targets the next unpublished version v<N> (render.versions is
append-only, so --force on the unpublished audio is correct). A subtitle-validation finding is
printed and the script exits 2 after props are written — the render must not proceed on it.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console

from cliplib import SCRIPTS_DIR, SKILL_DIR, load_ctx, load_words, place_words, run
from pslib import load_clip

console = Console()
app = typer.Typer(add_completion=False)

TEMPLATE_DIR = SKILL_DIR / "remotion"


def template_hash() -> str:
    files = [p for d in ("src", "lib", "public") for p in sorted((TEMPLATE_DIR / d).rglob("*")) if p.is_file()]
    files += [TEMPLATE_DIR / n for n in ("gen-props.mjs", "package.json", "remotion.config.ts")]
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(TEMPLATE_DIR).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


def uv_script(name: str, *args: str) -> str:
    return run(["uv", "run", "--quiet", str(SCRIPTS_DIR / name), *args], what=name)


def sync_workspace(clip_dir: Path) -> Path:
    """One template copy per clip, refreshed only when the skill's template changed (stamp file)."""
    ws = clip_dir / "remotion"
    ws.mkdir(exist_ok=True)
    stamp, current = ws / ".template-hash", template_hash()
    if not stamp.exists() or stamp.read_text().strip() != current:
        run(["rsync", "-a", "--exclude=node_modules", "--exclude=props.json", "--exclude=out", "--exclude=public/clip", "--exclude=public/episode",
             f"{TEMPLATE_DIR}/", f"{ws}/"], what="syncing the Remotion template")
        stamp.write_text(current)
    # Reinstall whenever the lockfile differs from the one node_modules was installed from — a template
    # that gained a dependency must not render against stale node_modules.
    lock_stamp, lock = ws / ".lock-hash", hashlib.sha256((ws / "package-lock.json").read_bytes()).hexdigest()[:16]
    if not (ws / "node_modules" / ".bin" / "remotion").exists() or not lock_stamp.exists() or lock_stamp.read_text().strip() != lock:
        logger.info("npm ci in the clip's Remotion workspace (first run, or the template's lockfile changed)")
        log = ws / "npm-ci.log"
        proc = subprocess.run(["queue", f"cd {ws} && npm ci --no-audit --no-fund"], capture_output=True, text=True)
        log.write_text(proc.stdout + proc.stderr)
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
            raise RuntimeError(f"npm ci failed (exit {proc.returncode}); full log {log}\n{tail}")
        lock_stamp.write_text(lock)
    return ws


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml (format: short)"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root (default: CLIP_DIR/../..)"),
) -> None:
    """Stage audio, segments, captions and Remotion props for CLIP_DIR's next render version."""
    clip = load_clip(clip_dir / "clip.yaml")  # validates the manifest and normalizes legacy statuses
    if clip.clip.format != "short":
        raise typer.BadParameter(f"{clip.clip.id} is format {clip.clip.format!r}; prep_short.py is for shorts "
                                 "(clips render with render_horizontal.py)")
    ctx = load_ctx(clip_dir, episode_root)
    v = len(clip.render.versions) + 1
    placed = place_words(ctx, load_words(ctx))
    audio, ass = f"renders/v{v}-audio.wav", f"subtitles/v{v}.ass"
    root = ["--episode-root", str(ctx.root)]
    (ctx.clip_dir / "subtitles").mkdir(exist_ok=True)
    words_out = ctx.clip_dir / "subtitles" / f"v{v}-words-output-time.json"
    words_out.write_text(json.dumps({"words": [
        {"w": w.text, "start": round(w.start, 3), "end": round(w.end, 3), "speaker": w.speaker} for w in placed]}))
    uv_script("assemble_audio.py", str(ctx.clip_dir), "--version", str(v), "--force", *root)
    # frame_segments first: it decides the framing (assets/framing.json) and measures where each mouth is, which caption placement needs
    uv_script("frame_segments.py", str(ctx.clip_dir), *root)
    uv_script("align_subtitles.py", str(ctx.clip_dir), "--audio", str(ctx.clip_dir / audio), "--version", str(v),
              "--words-json", str(words_out), *root)
    check = subprocess.run(["uv", "run", "--quiet", str(SCRIPTS_DIR / "validate_subtitles.py"), str(ctx.clip_dir),
                            "--ass", str(ctx.clip_dir / ass), *root], capture_output=True, text=True)
    log = ctx.clip_dir / "subtitles" / f"v{v}-validate_subtitles.log"
    log.write_text(check.stdout + check.stderr)
    ws = sync_workspace(ctx.clip_dir)
    run(["node", "gen-props.mjs", str(ctx.clip_dir), "--audio", audio, "--ass", ass,
         "--episode", str(ctx.root / "episode.yaml"), "--defaults", str(SKILL_DIR / "config" / "defaults.yaml")],
        what="gen-props.mjs", cwd=ws)
    console.print(f"[green]prep v{v}[/] {clip.clip.id}: {ctx.clip_dir / audio}, {ctx.clip_dir / ass}, {ws / 'props.json'}")
    if check.returncode != 0:
        summary = (check.stdout + check.stderr).strip().splitlines()[-1]
        console.print(f"[bold red]SUBTITLE VALIDATION FAILED[/] ({summary}) — see {log}; do not render these captions")
        raise typer.Exit(2)


if __name__ == "__main__":
    app()
