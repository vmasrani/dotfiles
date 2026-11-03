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
"""Render, encode, record and QC one prepped short (references/render-qc.md § Shorts).

Run `prep_short.py CLIP_DIR` first. This script then does, in order:

1. refuse to start while a `chrome-headless-shell` from an earlier render is alive;
2. render the Remotion `Short` composition through `queue` -> `renders/v<N>-master.mp4`
   (the visual master, never a deliverable);
3. encode the profile final: master video + the assembled wav, two-pass linear loudnorm
   (true-peak margin below the profile ceiling), yuv420p bt709 tv range, `-t` manifest duration
   -> `renders/v<N>-<profile>.mp4`;
4. append `render.versions` v<N> (real `rendered_at`), status `rendered`;
5. run `qc_render.py`, which records `render.versions[N].qc` and, on green, status `qc_passed`.

Any red exits nonzero with the log to read. A failed QC leaves v<N> recorded (versions are
append-only); fix upstream, re-run prep_short.py, which targets v<N+1>.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console

from pslib import Clip, RenderVersion, load_clip, load_episode, save_clip
from psmedia import (
    TRUE_PEAK_MARGIN_DB,
    episode_root_for,
    ff_time,
    loudnorm_filter,
    resolve_profile,
    run_ffmpeg,
)

SCRIPTS_DIR = Path(__file__).resolve().parent
console = Console()
app = typer.Typer(add_completion=False)

REMOTION_FLAGS = ("--timeout=1800000", "--offthreadvideo-cache-size-in-bytes=209715200", "--concurrency=3")


# ---------------------------------------------------------------------------
# pure parts (tested in test_render_short.py)
# ---------------------------------------------------------------------------


def missing_prep(clip_dir: Path, v: int) -> list[str]:
    """Files prep_short.py must have written for version v; empty when prep is complete."""
    needed = [f"renders/v{v}-audio.wav", f"subtitles/v{v}.ass", "remotion/props.json"]
    missing = [rel for rel in needed if not (clip_dir / rel).is_file()]
    props = clip_dir / "remotion" / "props.json"
    if props.is_file() and json.loads(props.read_text()).get("audioSrc") != f"renders/v{v}-audio.wav":
        missing.append(f"remotion/props.json audioSrc (it was generated for another version than v{v})")
    return missing


def remotion_shell(workspace: Path, v: int) -> str:
    """The ONE shell string handed to `queue` (the gate takes a single quoted string)."""
    return " ".join([
        f"cd {shlex.quote(str(workspace))} &&",
        "npx remotion render Short", f"../renders/v{v}-master.mp4", "--props=props.json", *REMOTION_FLAGS,
    ])


def headless_pids(pgrep_stdout: str, own_pid: int) -> list[int]:
    """PIDs listed by `pgrep -f chrome-headless-shell`, minus this process."""
    return [p for p in (int(x) for x in pgrep_stdout.split()) if p != own_pid]


def encode_args(master: Path, wav: Path, out: Path, af: str, fps: float, duration_s: float) -> list[str]:
    """ffmpeg arguments (after the base) for the profile final. Ported from the owner's encode_short.sh."""
    return [
        "-i", str(master), "-i", str(wav), "-map", "0:v", "-map", "1:a",
        "-vf", "scale=out_range=tv:out_color_matrix=bt709,format=yuv420p",
        "-color_range", "tv", "-colorspace", "bt709", "-r", f"{fps:g}",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-movflags", "+faststart",
        "-af", af, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-t", ff_time(duration_s), str(out),
    ]


def record_version(clip: Clip, v: int, profile: str, now: datetime) -> RenderVersion:
    """Append render.versions v and move the clip to `rendered`. Versions are append-only and contiguous."""
    expected = len(clip.render.versions) + 1
    if v != expected:
        raise ValueError(f"render.versions has {len(clip.render.versions)} entries, so the next version is v{expected}, not v{v}")
    entry = RenderVersion(
        version=v, preview=f"renders/v{v}-master.mp4", finals={profile: f"renders/v{v}-{profile}.mp4"},
        rendered_at=now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), qc=None,
    )
    clip.render.versions.append(entry)
    clip.clip.status = "rendered"
    return entry


# ---------------------------------------------------------------------------
# side-effecting steps
# ---------------------------------------------------------------------------


def perf_cores() -> int | None:
    proc = subprocess.run(["sysctl", "-n", "hw.perflevel0.logicalcpu"], capture_output=True, text=True)
    return int(proc.stdout) if proc.returncode == 0 and proc.stdout.strip() else None


def preflight() -> None:
    proc = subprocess.run(["pgrep", "-f", "chrome-headless-shell"], capture_output=True, text=True)
    if proc.returncode not in (0, 1):  # 1 = no match (the clean case)
        raise RuntimeError(f"pgrep failed (exit {proc.returncode}): {proc.stderr.strip()}")
    live = headless_pids(proc.stdout, os.getpid())
    if live:
        raise RuntimeError(
            f"{len(live)} chrome-headless-shell process(es) are alive ({live[:6]}…) — a previous render is still "
            "running or was orphaned. Wait for it, or `pkill -f chrome-headless-shell` if you are sure it is dead, "
            "then re-run. Never start a render on top of another."
        )
    load, cores = os.getloadavg()[0], perf_cores()
    if cores is not None and load >= cores:
        logger.warning(f"1-min load average {load:.1f} >= {cores} performance cores — the machine is not idle; "
                       "the render will be slow and may starve")


def render_master(workspace: Path, v: int, log: Path) -> None:
    logger.info(f"remotion render v{v} through queue (log: {log})")
    with log.open("w") as fh:
        proc = subprocess.run(["queue", remotion_shell(workspace, v)], stdout=fh, stderr=subprocess.STDOUT)
    if proc.returncode != 0:
        tail = "\n".join(log.read_text().strip().splitlines()[-25:])
        raise RuntimeError(
            f"remotion render failed (exit {proc.returncode}); full log {log}\n{tail}\n"
            "exit 144 = the shell was reaped mid-render: just re-run this script."
        )


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml (format: short), already prepped"),
    profile: str = typer.Option("youtube-shorts", "--profile", help="Platform profile to encode and QC against"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root (default: CLIP_DIR/../..)"),
) -> None:
    """Render CLIP_DIR's prepped short, encode the profile final, record render.versions, run QC."""
    clip_dir = clip_dir.expanduser().resolve()
    root = episode_root_for(clip_dir, episode_root)
    clip = load_clip(clip_dir / "clip.yaml")
    if clip.clip.format != "short":
        raise typer.BadParameter(f"{clip.clip.id} is format {clip.clip.format!r}; clips render with render_horizontal.py")
    target = resolve_profile(load_episode(root / "episode.yaml"), profile)
    v = len(clip.render.versions) + 1
    if missing := missing_prep(clip_dir, v):
        raise RuntimeError(f"prep for v{v} is incomplete — run prep_short.py {clip_dir} first. Missing: {missing}")

    preflight()
    renders = clip_dir / "renders"
    master, wav, final = renders / f"v{v}-master.mp4", renders / f"v{v}-audio.wav", renders / f"v{v}-{profile}.mp4"
    render_master(clip_dir / "remotion", v, renders / f"v{v}-render.log")
    if not master.is_file():
        raise RuntimeError(f"remotion exited 0 but {master} does not exist")

    af = loudnorm_filter(wav, target.loudness_lufs, target.true_peak_dbtp - TRUE_PEAK_MARGIN_DB)
    run_ffmpeg(encode_args(master, wav, final, af, target.fps, clip.output.duration_s), what=f"encoding {final.name}")
    logger.info(f"wrote {final}")

    record_version(clip, v, profile, datetime.now(timezone.utc))
    save_clip(clip_dir / "clip.yaml", clip)

    qc_log = clip_dir / f"qc-v{v}.log"
    qc = subprocess.run(
        ["uv", "run", "--quiet", str(SCRIPTS_DIR / "qc_render.py"), str(clip_dir), "--version", str(v),
         "--profile", profile, "--episode-root", str(root)],
        capture_output=True, text=True,
    )
    qc_log.write_text(qc.stdout + qc.stderr)
    if qc.returncode != 0:
        tail = "\n".join((qc.stdout + qc.stderr).strip().splitlines()[-25:])
        console.print(f"[bold red]QC FAILED[/] v{v} — full log {qc_log}\n{tail}")
        raise typer.Exit(1)
    console.print(f"[bold green]rendered + QC passed[/] {clip.clip.id} v{v}: {final}\n"
                  f"contact sheet: {renders / f'v{v}-contact-sheet.png'} — LOOK at the frames before delivering")


if __name__ == "__main__":
    app()
