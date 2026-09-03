#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "yt-dlp>=2024.8.6",
# ]
# ///
"""Stage 1 ingest — download an authorized source episode, probe it, write episode.yaml.

Rights gate: `init` refuses to run without `--authorized`; the attestation is recorded
as `episode.authorized: true` (schema in ../references/schemas.md) and is what every
later stage relies on. Nothing here guesses: a missing tool, an unreadable media file
or an unattested run stops the pipeline with an actionable error.
"""

from __future__ import annotations

import datetime as dt
import re
import shutil
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    Episode,
    EpisodeMeta,
    EpisodeStatus,
    MediaSpec,
    MediaProbe,
    PlatformProfile,
    Speaker,
    TranscriptRef,
    ffprobe_media,
    load_episode,
    save_episode,
    sha256_file,
)

console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"

MEDIA_SUFFIXES = {
    ".mp4", ".m4a", ".mkv", ".webm", ".mov", ".avi", ".mts", ".m4v",
    ".wav", ".mp3", ".aac", ".flac", ".opus", ".ogg", ".mxf",
}

VIDEO_STEM = "episode"
AUDIO_STEM = "episode"

AUTHORIZATION_NOTICE = (
    "refusing to ingest without a rights attestation.\n\n"
    "This pipeline only edits material you own or are licensed to edit. Re-run with "
    "--authorized to attest that you own, or hold written authorization to edit and "
    "publish, the source at the given --url. The attestation is recorded in episode.yaml "
    "as `episode.authorized: true` and is carried into every clip's provenance.json. "
    "There is no way to proceed without it."
)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def load_defaults(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise typer.BadParameter(
            f"config file not found: {path} — pass --config pointing at the skill's "
            "config/defaults.yaml"
        )
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise typer.BadParameter(f"{path} did not parse as a YAML mapping")
    return data


def config_platform_profiles(defaults: dict[str, Any], config_path: Path) -> list[PlatformProfile]:
    raw = defaults.get("platform_profiles")
    if not raw:
        raise typer.BadParameter(
            f"{config_path} has no `platform_profiles` block — every episode needs at least "
            "one target profile (see references/schemas.md)"
        )
    return [PlatformProfile.model_validate(p) for p in raw]


def config_transcription(defaults: dict[str, Any], config_path: Path) -> tuple[str, str]:
    block = defaults.get("transcription") or {}
    engine, language = block.get("engine"), block.get("language")
    if not engine or not language:
        raise typer.BadParameter(
            f"{config_path} `transcription` must set both `engine` and `language`"
        )
    return str(engine), str(language)


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    if not slug:
        raise typer.BadParameter(
            f"cannot derive a slug from title {text!r} — pass --slug explicitly"
        )
    return slug[:60].strip("-")


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def video_opts(out_stem: Path) -> dict[str, Any]:
    """yt-dlp options for the merged best video+audio mp4."""
    return {
        "format": "bestvideo*+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": {"default": f"{out_stem}.%(ext)s"},
        "continuedl": True,
        "noprogress": False,
        "retries": 5,
        "fragment_retries": 10,
        "noplaylist": True,
        "windowsfilenames": False,
    }


def audio_opts(out_stem: Path) -> dict[str, Any]:
    """yt-dlp options for the separate best-audio m4a used by transcription."""
    return {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": {"default": f"{out_stem}.%(ext)s"},
        "postprocessors": [
            {"key": "FFmpegExtractAudio", "preferredcodec": "m4a", "preferredquality": "0"}
        ],
        "continuedl": True,
        "noprogress": False,
        "retries": 5,
        "fragment_retries": 10,
        "noplaylist": True,
    }


def run_ydl(url: str, opts: dict[str, Any], expect: Path) -> None:
    from yt_dlp import YoutubeDL  # imported here so --help works without touching the network stack

    with YoutubeDL(opts) as ydl:
        code = ydl.download([url])
    if code != 0:
        raise RuntimeError(f"yt-dlp exited {code} downloading {url} — see its output above")
    if not expect.is_file():
        raise RuntimeError(
            f"yt-dlp reported success but {expect} does not exist — the requested format "
            f"({opts['format']}) may not be available for {url}; re-run with "
            "`yt-dlp -F <url>` to inspect available formats"
        )


def download_if_missing(url: str, target: Path, opts: dict[str, Any], what: str) -> bool:
    """Returns True when a download ran, False when the completed file was already there."""
    if target.is_file() and target.stat().st_size > 0:
        logger.info(f"{what}: {target.name} already present ({target.stat().st_size:,} bytes) — skipping download")
        return False
    logger.info(f"{what}: downloading to {target}")
    run_ydl(url, opts, target)
    return True


# ---------------------------------------------------------------------------
# Probing
# ---------------------------------------------------------------------------


def media_files(source_dir: Path) -> list[Path]:
    return sorted(
        p
        for p in source_dir.iterdir()
        if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in MEDIA_SUFFIXES
    )


def probe_source_dir(root: Path, source_dir: Path) -> dict[str, MediaProbe]:
    files = media_files(source_dir)
    if not files:
        raise RuntimeError(
            f"no media files in {source_dir} — nothing to probe. Expected suffixes: "
            f"{', '.join(sorted(MEDIA_SUFFIXES))}"
        )
    probes: dict[str, MediaProbe] = {}
    for path in files:
        key = str(path.relative_to(root))
        probes[key] = ffprobe_media(path)
        logger.info(f"probed {key}: {probes[key].duration_s:.3f}s")
    return probes


def render_probes(probes: dict[str, MediaProbe]) -> None:
    table = RichTable(title="source/ probes", header_style="bold cyan")
    table.add_column("file", overflow="fold")
    for col in ("duration_s", "w×h", "fps", "video", "audio", "ch", "sr"):
        table.add_column(col)
    for key, probe in probes.items():
        size = f"{probe.width}×{probe.height}" if probe.width else "—"
        table.add_row(
            key,
            f"{probe.duration_s:.3f}",
            size,
            f"{probe.fps:.3f}" if probe.fps else "—",
            probe.video_codec or "—",
            probe.audio_codec or "—",
            str(probe.audio_channels or "—"),
            str(probe.sample_rate or "—"),
        )
    console.print(table)


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


@app.command()
def init(
    episode_root: Path = typer.Argument(..., help="Episode directory to create/refresh"),
    url: str = typer.Option(..., "--url", help="Source video URL (yt-dlp supported site)"),
    title: str = typer.Option(..., "--title", help="Human episode title"),
    slug: str | None = typer.Option(None, "--slug", help="Episode id; derived from --title when omitted"),
    authorized: bool = typer.Option(
        False, "--authorized", help="Attest you own or are authorized to edit this source"
    ),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", help="Pipeline defaults YAML"),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print the resolved yt-dlp invocations and exit; touches nothing"
    ),
) -> None:
    """Download the source episode, probe source/, and write episode.yaml."""
    if not authorized:
        raise typer.BadParameter(AUTHORIZATION_NOTICE, param_hint="--authorized")

    defaults = load_defaults(config.resolve())
    profiles = config_platform_profiles(defaults, config)
    engine, language = config_transcription(defaults, config)

    root = episode_root.resolve()
    source_dir = root / "source"
    video_target = source_dir / f"{VIDEO_STEM}.mp4"
    audio_target = source_dir / f"{AUDIO_STEM}.m4a"

    if dry_run:
        console.print("[bold yellow]--dry-run[/]: nothing downloaded, nothing written.")
        console.print(f"episode root : {root}")
        console.print(f"video target : {video_target}")
        console.print(yaml.safe_dump(video_opts(source_dir / VIDEO_STEM), sort_keys=False), markup=False)
        console.print(f"audio target : {audio_target}")
        console.print(yaml.safe_dump(audio_opts(source_dir / AUDIO_STEM), sort_keys=False), markup=False)
        console.print(f"url          : {url}")
        raise typer.Exit(0)

    source_dir.mkdir(parents=True, exist_ok=True)
    download_if_missing(url, video_target, video_opts(source_dir / VIDEO_STEM), "video")
    download_if_missing(url, audio_target, audio_opts(source_dir / AUDIO_STEM), "audio")

    probes = probe_source_dir(root, source_dir)
    render_probes(probes)

    episode_path = root / "episode.yaml"
    created = dt.date.today().isoformat()
    if episode_path.is_file():
        existing = load_episode(episode_path)
        episode = Episode(
            episode=EpisodeMeta(
                id=slug or existing.episode.id,
                title=title,
                source_url=url,
                authorized=True,
                created=existing.episode.created,
            ),
            platform_profiles=profiles,
            speakers=existing.speakers,
            media=MediaSpec(
                episode_video=str(video_target.relative_to(root)),
                episode_audio=str(audio_target.relative_to(root)),
                probes=probes,
            ),
            sync=existing.sync,
            transcript=existing.transcript,
            status=existing.status,
        )
        logger.info(
            f"refreshed existing episode.yaml (kept {len(existing.speakers)} speaker(s), "
            f"{len(existing.sync)} sync entr(ies), stage={existing.status.stage})"
        )
    else:
        episode = Episode(
            episode=EpisodeMeta(
                id=slug or slugify(title),
                title=title,
                source_url=url,
                authorized=True,
                created=created,
            ),
            platform_profiles=profiles,
            speakers=[],
            media=MediaSpec(
                episode_video=str(video_target.relative_to(root)),
                episode_audio=str(audio_target.relative_to(root)),
                probes=probes,
            ),
            sync=[],
            transcript=TranscriptRef(
                json_file="transcript/transcript.json",
                md="transcript/transcript.md",
                engine=engine,
                language=language,
                word_count=0,
            ),
            status=EpisodeStatus(stage="ingested"),
        )
        logger.warning(
            "transcript block is a placeholder (word_count 0) until transcribe.py runs"
        )

    save_episode(episode_path, episode)
    console.print(f"[bold green]OK[/] {episode_path} — id={episode.episode.id} stage={episode.status.stage}")
    console.print(
        "[dim]next:[/] register camera files with `ingest.py register-camera`, then run "
        "`transcribe.py` and `sync_cameras.py compute`"
    )


# ---------------------------------------------------------------------------
# register-camera
# ---------------------------------------------------------------------------


@app.command("register-camera")
def register_camera(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    file: Path = typer.Option(..., "--file", help="Isolated camera file to copy into source/"),
    speaker_id: str = typer.Option(..., "--speaker-id", help="Stable speaker id, e.g. host1"),
    speaker_name: str = typer.Option(..., "--speaker-name", help="Display name, e.g. Vaden"),
    force: bool = typer.Option(
        False, "--force", help="Overwrite an existing, different file of the same name in source/"
    ),
) -> None:
    """Copy an isolated camera file into source/ and register its speaker + probe."""
    root = episode_root.resolve()
    episode_path = root / "episode.yaml"
    if not episode_path.is_file():
        raise typer.BadParameter(
            f"no episode.yaml in {root} — run `ingest.py init` first"
        )
    src = file.resolve()
    if not src.is_file():
        raise typer.BadParameter(f"camera file does not exist: {src}")
    if not speaker_id.strip():
        raise typer.BadParameter("--speaker-id must be non-empty")

    episode = load_episode(episode_path)
    source_dir = root / "source"
    source_dir.mkdir(parents=True, exist_ok=True)
    dest = source_dir / src.name

    if dest.resolve() == src:
        logger.info(f"{src.name} is already inside source/ — no copy needed")
    elif dest.is_file():
        if sha256_file(dest) == sha256_file(src):
            logger.info(f"{dest.name} already in source/ with identical contents — no copy needed")
        elif force:
            logger.warning(f"overwriting {dest} (--force)")
            shutil.copy2(src, dest)
        else:
            raise typer.BadParameter(
                f"{dest} already exists with different contents than {src} — rename the input "
                "or pass --force to overwrite"
            )
    else:
        shutil.copy2(src, dest)
        logger.info(f"copied {src} -> {dest}")

    rel = str(dest.relative_to(root))
    probe = ffprobe_media(dest)
    episode.media.probes[rel] = probe

    speakers = {s.id: s for s in episode.speakers}
    if speaker_id in speakers:
        previous = speakers[speaker_id].camera_file
        speakers[speaker_id].name = speaker_name
        speakers[speaker_id].camera_file = rel
        if previous and previous != rel:
            logger.warning(f"speaker {speaker_id}: camera_file {previous} -> {rel}")
        stale = [e for e in episode.sync if e.file == previous and previous != rel]
        for entry in stale:
            episode.sync.remove(entry)
            logger.warning(f"dropped stale sync entry for {entry.file}; re-run sync_cameras.py compute")
    else:
        episode.speakers.append(
            Speaker(id=speaker_id, name=speaker_name, camera_file=rel, preferred_crop=None)
        )

    conflicting = [s for s in episode.speakers if s.camera_file == rel and s.id != speaker_id]
    if conflicting:
        raise typer.BadParameter(
            f"{rel} is already registered to speaker(s) {[s.id for s in conflicting]} — "
            "one camera file belongs to exactly one speaker"
        )

    save_episode(episode_path, episode)
    render_probes({rel: probe})
    console.print(
        f"[bold green]OK[/] {rel} registered to speaker {speaker_id} ({speaker_name}); "
        f"{len(episode.speakers)} speaker(s) on file"
    )
    console.print("[dim]next:[/] `sync_cameras.py compute` to measure its offset")


def cli() -> None:
    """CLI entry point — the one place operational failures become a clean exit."""
    try:
        app()
    except (RuntimeError, FileNotFoundError) as exc:  # deliberate, actionable failures
        console.print(f"[bold red]error[/] {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    cli()
