#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "loguru", "rich", "pyyaml", "pydantic", "numpy"]
# ///
"""Stage 1 ingest for REMOTE MULTITRACK recordings — N isolated per-speaker tracks
that a recorder (Riverside, Zoom, Squadcast…) started on one common clock.

Why this exists alongside `ingest.py`:

`ingest.py` assumes one mixed episode file, with isolated cameras as an optional extra
that must be aligned to it by `sync_cameras.py`. That is the wrong shape for a remote
podcast, where the natural input is N tracks that are ALREADY aligned and each contain
exactly one speaker. In that shape:

  * speaker attribution is exact BY CONSTRUCTION — one track, one speaker. No diarizer
    is involved and none can be wrong.
  * cross-correlation cannot work anyway. Remote participants are in different rooms,
    so the tracks share no acoustic signal to correlate. `sync_cameras.py` is not merely
    unnecessary here, it is inapplicable.

So this command takes the tracks directly, verifies the common-clock assumption instead
of trusting it, mixes a reference master, and writes an `episode.yaml` whose `sync`
block records offset 0 with an honest method name.

The common-clock assumption is CHECKED, not assumed: `check-alignment` measures how
often exactly one track dominates the others. Genuine turn-taking in aligned isolated
tracks is highly exclusive — one person speaks at a time. Misaligned tracks smear that
exclusivity. A low score stops ingest with an actionable error rather than producing a
manifest whose timings are quietly wrong.

Nothing here downloads anything: these are local files you already own.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import numpy as np
import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pslib import (  # noqa: E402
    Episode,
    EpisodeMeta,
    EpisodeStatus,
    MediaSpec,
    Speaker,
    SyncEntry,
    TranscriptRef,
    load_episode,
    save_episode,
)
from pslib import PlatformProfile  # noqa: E402
from psmedia import DEFAULT_CONFIG, load_config, parse_crop, validate_crop_within  # noqa: E402

app = typer.Typer(add_completion=False, help=__doc__)
console = Console()

SR = 16000
HOP_S = 0.05
METHOD = "common-recorder-clock"
# Fraction of *speech* frames in which one track must lead the runner-up by
# DOMINANCE_DB for the common-clock assumption to be considered corroborated.
EXCLUSIVITY_FLOOR = 0.80
DOMINANCE_DB = 6.0
SILENCE_FLOOR_DB = -55.0


def require_tools() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if shutil.which(tool) is None:
            raise typer.BadParameter(f"{tool} not found on PATH — install it and re-run")


def ffprobe_field(path: Path, entries: str, stream: str | None = None) -> str:
    cmd = ["ffprobe", "-v", "error"]
    if stream:
        cmd += ["-select_streams", stream]
    cmd += ["-show_entries", entries, "-of", "csv=p=0", str(path)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {path}: {r.stderr.strip()}")
    return r.stdout.strip()


def probe_one(path: Path):
    from pslib import MediaProbe

    dur = ffprobe_field(path, "format=duration")
    if not dur:
        raise RuntimeError(f"{path} has no readable duration — is it a media file?")
    v = ffprobe_field(path, "stream=width,height,r_frame_rate,codec_name", "v:0")
    a = ffprobe_field(path, "stream=codec_name,channels,sample_rate", "a:0")

    width = height = fps = None
    video_codec = None
    if v:
        parts = v.split(",")
        if len(parts) >= 4:
            video_codec, width, height, rate = parts[0], int(parts[1]), int(parts[2]), parts[3]
            num, _, den = rate.partition("/")
            fps = float(num) / float(den) if den and float(den) else float(num)
    audio_codec = channels = sample_rate = None
    if a:
        parts = a.split(",")
        if len(parts) >= 3:
            audio_codec, channels, sample_rate = parts[0], int(parts[1]), int(parts[2])

    return MediaProbe(
        duration_s=float(dur),
        width=width,
        height=height,
        fps=fps,
        video_codec=video_codec,
        audio_codec=audio_codec,
        audio_channels=channels,
        sample_rate=sample_rate,
    )


def parse_track(spec: str) -> tuple[str, str, Path]:
    parts = spec.split("|")
    if len(parts) != 3:
        raise typer.BadParameter(
            f"--track must be 'speaker_id|Display Name|/path/to/file', got {spec!r}"
        )
    sid, name, raw = (p.strip() for p in parts)
    if not sid or not name or not raw:
        raise typer.BadParameter(f"--track has an empty field: {spec!r}")
    path = Path(raw).expanduser()
    if not path.exists():
        raise typer.BadParameter(f"track file does not exist: {path}")
    return sid, name, path


def parse_crop_opt(spec: str) -> tuple[str, str]:
    sid, sep, crop = spec.partition("|")
    if not sep or not sid.strip() or not crop.strip():
        raise typer.BadParameter(
            f"--crop must be 'speaker_id|x=..:y=..:w=..:h=..', got {spec!r}"
        )
    return sid.strip(), crop.strip()


def envelope_db(path: Path, limit_s: float | None) -> np.ndarray:
    """Per-hop RMS in dBFS for one track, decoded mono at SR."""
    cmd = ["ffmpeg", "-nostdin", "-v", "error"]
    if limit_s:
        cmd += ["-t", str(limit_s)]
    cmd += ["-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"decode failed for {path}: {r.stderr.decode()[-400:]}")
    a = np.frombuffer(r.stdout, dtype=np.float32).astype(np.float64)
    hop = int(SR * HOP_S)
    n = (a.size // hop) * hop
    if n == 0:
        raise RuntimeError(f"{path} decoded to less than one {HOP_S}s hop")
    rms = np.sqrt((a[:n].reshape(-1, hop) ** 2).mean(axis=1) + 1e-12)
    return 20.0 * np.log10(rms + 1e-12)


def exclusivity(envs: list[np.ndarray]) -> tuple[float, int]:
    """Fraction of speech frames where one track leads the runner-up by DOMINANCE_DB.

    Aligned isolated tracks of a real conversation are highly exclusive: one person
    talks at a time and only their mic is hot. Misalignment destroys that structure.
    """
    length = min(e.size for e in envs)
    stack = np.vstack([e[:length] for e in envs])
    loudest = stack.max(axis=0)
    speech = loudest > SILENCE_FLOOR_DB
    if speech.sum() == 0:
        raise RuntimeError("every sampled frame is below the silence floor — no speech found")
    sub = stack[:, speech]
    ordered = np.sort(sub, axis=0)
    lead = ordered[-1] - ordered[-2]
    return float((lead >= DOMINANCE_DB).mean()), int(speech.sum())


@app.command("check-alignment")
def check_alignment(
    track: list[str] = typer.Option(..., "--track", help="'speaker_id|Name|path'; repeatable"),
    minutes: float = typer.Option(20.0, "--minutes", help="How much of each track to analyse"),
) -> None:
    """Test the common-clock assumption without writing anything."""
    require_tools()
    parsed = [parse_track(t) for t in track]
    if len(parsed) < 2:
        raise typer.BadParameter("need at least two tracks to check alignment")

    envs, names = [], []
    for sid, name, path in parsed:
        envs.append(envelope_db(path, minutes * 60))
        names.append(f"{name} ({sid})")
        logger.info(f"analysed {path.name} for {name}")

    score, frames = exclusivity(envs)
    console.print(
        f"\nspeech frames analysed: [bold]{frames}[/] "
        f"({frames * HOP_S / 60:.1f} min of speech)"
    )
    console.print(
        f"exclusivity: [bold]{score:.3f}[/] "
        f"(one track leads the next by >= {DOMINANCE_DB:g} dB in this fraction of speech)"
    )
    if score >= EXCLUSIVITY_FLOOR:
        console.print(
            f"[green]consistent with a common clock[/] — at or above {EXCLUSIVITY_FLOOR:g}"
        )
    else:
        console.print(
            f"[red]NOT consistent with a common clock[/] — below {EXCLUSIVITY_FLOOR:g}.\n"
            "Either the tracks are misaligned, or two speakers share a room and bleed into "
            "each other's mics. Verify by transcribing the same window from two tracks and "
            "checking they read as one coherent conversation."
        )
        raise typer.Exit(1)


@app.command()
def init(
    episode_root: Path = typer.Argument(..., help="Episode directory to create/refresh"),
    track: list[str] = typer.Option(..., "--track", help="'speaker_id|Name|path'; repeatable"),
    title: str = typer.Option(..., "--title", help="Human episode title"),
    slug: str = typer.Option(None, "--slug", help="Episode id; derived from --title when omitted"),
    crop: list[str] = typer.Option(
        None, "--crop", help="'speaker_id|x=..:y=..:w=..:h=..' preferred crop; repeatable"
    ),
    source_url: str = typer.Option("", "--source-url", help="Reference URL, if published"),
    authorized: bool = typer.Option(
        False, "--authorized", help="Attest you own or are authorized to edit this source"
    ),
    master: str = typer.Option(
        None, "--master", help="Speaker id whose video is the master timeline; default = longest"
    ),
    skip_check: bool = typer.Option(
        False, "--skip-alignment-check", help="Skip the common-clock check (records it as unverified)"
    ),
    check_minutes: float = typer.Option(20.0, "--check-minutes", help="Audio analysed for the check"),
    config: Path = typer.Option(None, "--config", help="Pipeline defaults YAML"),
) -> None:
    """Ingest N aligned isolated tracks and write episode.yaml."""
    require_tools()
    if not authorized:
        raise typer.BadParameter(
            "refusing to ingest without --authorized: you must attest that you own or are "
            "authorized to edit this source"
        )
    parsed = [parse_track(t) for t in track]
    if len(parsed) < 2:
        raise typer.BadParameter("multitrack ingest needs at least two --track entries")
    ids = [sid for sid, _, _ in parsed]
    if len(set(ids)) != len(ids):
        raise typer.BadParameter(f"duplicate speaker ids in --track: {ids}")

    crops = dict(parse_crop_opt(c) for c in (crop or []))
    unknown = set(crops) - set(ids)
    if unknown:
        raise typer.BadParameter(f"--crop names speaker(s) with no --track: {sorted(unknown)}")

    cfg = load_config(config)
    # platform_profiles live in the raw defaults YAML, not in the typed PipelineConfig —
    # same source ingest.py reads.
    import yaml as _yaml

    defaults_path = Path(config) if config is not None else DEFAULT_CONFIG
    raw_defaults = _yaml.safe_load(defaults_path.read_text()) or {}
    raw_profiles = raw_defaults.get("platform_profiles")
    if not raw_profiles:
        raise RuntimeError(
            f"{defaults_path} has no `platform_profiles` block — every episode needs at "
            "least one target profile"
        )
    profiles = [PlatformProfile.model_validate(p) for p in raw_profiles]

    episode_id = slug or "".join(
        ch if ch.isalnum() else "-" for ch in title.lower()
    ).strip("-").replace("--", "-")

    root = Path(episode_root)
    source = root / "source"
    source.mkdir(parents=True, exist_ok=True)

    # --- verify the common clock before committing anything to disk -------------
    if skip_check:
        logger.warning("skipping the common-clock check — sync will be recorded as unverified")
        verified = False
        score = None
    else:
        envs = [envelope_db(p, check_minutes * 60) for _, _, p in parsed]
        score, frames = exclusivity(envs)
        logger.info(f"exclusivity {score:.3f} over {frames} speech frames")
        if score < EXCLUSIVITY_FLOOR:
            raise RuntimeError(
                f"exclusivity {score:.3f} is below {EXCLUSIVITY_FLOOR:g} — these tracks do not "
                "look like they share a clock. Refusing to write a manifest with offset 0, "
                "which would silently misplace every cut. Re-run `check-alignment` and confirm "
                "manually, or pass --skip-alignment-check if you have verified alignment yourself."
            )
        verified = True

    # --- copy tracks in and probe ---------------------------------------------
    probes = {}
    speakers = []
    sync = []
    for sid, name, path in parsed:
        dest = source / f"track_{sid}{path.suffix}"
        if dest.exists() and dest.stat().st_size == path.stat().st_size:
            logger.info(f"{dest.name} already present with matching size — reusing")
        else:
            logger.info(f"copying {path.name} -> {dest.name} ({path.stat().st_size / 1e9:.2f} GB)")
            shutil.copy2(path, dest)
        rel = str(dest.relative_to(root))
        probes[rel] = probe_one(dest)

        crop_spec = crops.get(sid)
        if crop_spec:
            box = parse_crop(crop_spec)
            p = probes[rel]
            if p.width is None or p.height is None:
                raise RuntimeError(f"--crop given for {sid} but {rel} has no video stream")
            validate_crop_within(box, p.width, p.height, f"--crop for {sid}")
        speakers.append(Speaker(id=sid, name=name, camera_file=rel, preferred_crop=crop_spec))
        sync.append(
            SyncEntry(file=rel, offset_s=0.0, confidence=1.0 if verified else 0.0,
                      method=METHOD, gaps=[], verified=verified)
        )

    # --- master timeline + reference mixdown ----------------------------------
    if master and master not in ids:
        raise typer.BadParameter(f"--master {master!r} is not one of {ids}")
    if master:
        master_rel = next(s.camera_file for s in speakers if s.id == master)
    else:
        master_rel = max(probes, key=lambda k: probes[k].duration_s)
    logger.info(f"master timeline: {master_rel} ({probes[master_rel].duration_s:.1f}s)")

    mix = source / "episode_mix.m4a"
    inputs = []
    for s in speakers:
        inputs += ["-i", str(root / s.camera_file)]
    n = len(speakers)
    # normalize=0 keeps each speaker at their recorded level (amix's default divides by
    # N and makes everyone quiet); alimiter catches the rare simultaneous-speech peak.
    filt = f"amix=inputs={n}:duration=longest:normalize=0,alimiter=limit=0.95[mix]"
    # -map + -vn are load-bearing: without them ffmpeg also auto-maps a video stream from
    # one of the .mov inputs into the "audio" file, quietly multiplying its size.
    cmd = ["ffmpeg", "-nostdin", "-y", *inputs, "-filter_complex", filt,
           "-map", "[mix]", "-vn", "-c:a", "aac", "-b:a", "192k", str(mix)]
    logger.info(f"mixing {n} tracks -> {mix.name}")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not mix.exists():
        raise RuntimeError(f"mixdown failed:\n{r.stderr[-1200:]}")
    mix_rel = str(mix.relative_to(root))
    probes[mix_rel] = probe_one(mix)

    episode = Episode(
        episode=EpisodeMeta(
            id=episode_id,
            title=title,
            source_url=source_url,
            authorized=True,
            created=date.today().isoformat(),
        ),
        platform_profiles=profiles,
        speakers=speakers,
        media=MediaSpec(episode_video=master_rel, episode_audio=mix_rel, probes=probes),
        sync=sync,
        transcript=TranscriptRef(
            json="transcript/transcript.json",
            md="transcript/transcript.md",
            engine=cfg.transcription.engine,
            language=cfg.transcription.language,
            word_count=0,
        ),
        status=EpisodeStatus(stage="ingested"),
    )
    save_episode(root / "episode.yaml", episode)

    table = RichTable(title="multitrack ingest", header_style="bold cyan")
    for col in ("speaker", "name", "file", "duration_s", "w×h", "crop"):
        table.add_column(col, overflow="fold")
    for s in speakers:
        p = probes[s.camera_file]
        table.add_row(s.id, s.name, s.camera_file, f"{p.duration_s:.1f}",
                      f"{p.width}×{p.height}" if p.width else "—", s.preferred_crop or "—")
    console.print(table)
    console.print(f"master timeline : [bold]{master_rel}[/]")
    console.print(f"reference mix   : [bold]{mix_rel}[/] ({probes[mix_rel].duration_s:.1f}s)")
    if score is not None:
        console.print(f"common clock    : verified (exclusivity {score:.3f})")
    else:
        console.print("common clock    : [yellow]UNVERIFIED[/] (--skip-alignment-check)")
    console.print(f"\nwrote {root / 'episode.yaml'}")


@app.command("set-crop")
def set_crop(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    speaker: str = typer.Option(..., "--speaker", help="Speaker id"),
    crop: str = typer.Option(..., "--crop", help="'x=..:y=..:w=..:h=..', or 'none' to clear"),
) -> None:
    """Set or clear a speaker's preferred_crop after previewing it with sample_frame.py."""
    root = Path(episode_root)
    episode = load_episode(root / "episode.yaml")
    target = next((s for s in episode.speakers if s.id == speaker), None)
    if target is None:
        raise typer.BadParameter(
            f"no speaker {speaker!r} in episode.yaml; known: {sorted(episode.speaker_ids())}"
        )
    if crop.lower() == "none":
        target.preferred_crop = None
        console.print(f"cleared preferred_crop for {speaker}")
    else:
        box = parse_crop(crop)
        if target.camera_file is None:
            raise RuntimeError(f"speaker {speaker} has no camera_file to validate the crop against")
        probe = episode.media.probes.get(target.camera_file)
        if probe is None or probe.width is None or probe.height is None:
            raise RuntimeError(f"no video probe for {target.camera_file}")
        validate_crop_within(box, probe.width, probe.height, f"--crop for {speaker}")
        target.preferred_crop = crop
        console.print(f"set preferred_crop for {speaker}: {crop}")
    save_episode(root / "episode.yaml", episode)


if __name__ == "__main__":
    app()
