#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "httpx>=0.27",
#   "numpy>=1.26",
#   "mlx-whisper>=0.4; sys_platform == 'darwin' and platform_machine == 'arm64'",
# ]
# ///
"""Stage 1 transcription — word-level transcript with real speaker labels.

Two engines, chosen explicitly (config/defaults.yaml `transcription.engine`, or --engine).
They never substitute for one another:

  assemblyai   cloud ASR with diarization. Requires ASSEMBLYAI_API_KEY.
  mlx-whisper  local ASR on Apple Silicon. Carries no diarizer, so speaker labels come
               from per-camera audio activity and REQUIRE every speaker to have a
               verified, synced isolated camera file.

Diarization labels are never guessed into speaker ids: without --map the script prints
sample lines per label and exits, asking to be re-run with the mapping.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import numpy as np
import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    Episode,
    Transcript,
    TranscriptRef,
    TranscriptSegment,
    Word,
    fmt_mmss,
    load_episode,
    save_episode,
    save_transcript,
)

console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=True)

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"
ENGINES = ("assemblyai", "mlx-whisper")

AAI_BASE = "https://api.assemblyai.com/v2"
AAI_KEY_ENV = "ASSEMBLYAI_API_KEY"

SEGMENT_MAX_GAP_S = 0.8          # a longer silence starts a new readable segment
SEGMENT_MAX_DURATION_S = 25.0
TURN_MAX_GAP_S = 0.5             # words closer than this belong to the same speaking turn

SAMPLE_RATE = 16_000
HOP_S = 0.005
HOP = int(SAMPLE_RATE * HOP_S)
WORD_PAD_S = 0.05                # widen each word window slightly before measuring energy
DECISIVE_RATIO = 1.3             # winner must beat the runner-up by this to count as decisive
DECISIVE_FRACTION = 0.60         # ... on at least this fraction of words, or the tracks aren't isolated
SILENT_TRACK_ENERGY = 1e-3       # below this on every track, a turn has no attribution evidence


@dataclass
class RawWord:
    w: str
    start: float
    end: float
    conf: float | None
    label: str | None      # diarization label (assemblyai) or None (mlx-whisper)


# ---------------------------------------------------------------------------
# Config / inputs
# ---------------------------------------------------------------------------


def load_defaults(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise typer.BadParameter(
            f"config file not found: {path} — pass --config pointing at config/defaults.yaml"
        )
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise typer.BadParameter(f"{path} did not parse as a YAML mapping")
    return data


def resolve_engine(cli_engine: str | None, defaults: dict[str, Any], config: Path) -> tuple[str, str]:
    block = defaults.get("transcription") or {}
    engine = cli_engine or block.get("engine")
    language = block.get("language")
    if not engine:
        raise typer.BadParameter(
            f"no engine: pass --engine ({'|'.join(ENGINES)}) or set transcription.engine in {config}"
        )
    if engine not in ENGINES:
        raise typer.BadParameter(f"unknown engine {engine!r} — choose one of {', '.join(ENGINES)}")
    if not language:
        raise typer.BadParameter(f"{config} `transcription.language` is required")
    return engine, str(language)


def audio_for_transcription(root: Path, episode: Episode) -> tuple[Path, str]:
    rel = episode.media.episode_audio or episode.media.episode_video
    path = root / rel
    if not path.is_file():
        raise typer.BadParameter(
            f"episode audio not found: {path} (episode.yaml points at {rel}) — run `ingest.py init` first"
        )
    return path, rel


# ---------------------------------------------------------------------------
# Raw-ASR cache — so a re-run purely to supply --map never re-transcribes
# ---------------------------------------------------------------------------


def cache_path(root: Path, engine: str) -> Path:
    return root / "transcript" / f".raw-{engine}.json"


def read_cache(path: Path, audio_rel: str, size: int) -> list[RawWord] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text())
    if payload.get("audio") != audio_rel or payload.get("size") != size:
        logger.warning(
            f"{path.name} was produced from different audio ({payload.get('audio')}, "
            f"{payload.get('size')} bytes) — ignoring it and transcribing again"
        )
        return None
    logger.info(f"reusing cached ASR output {path.name} ({len(payload['words'])} words) — --no-cache to redo")
    return [RawWord(**w) for w in payload["words"]]


def write_cache(path: Path, audio_rel: str, size: int, engine: str, words: list[RawWord]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "engine": engine,
                "audio": audio_rel,
                "size": size,
                "words": [w.__dict__ for w in words],
            },
            indent=2,
        )
        + "\n"
    )


# ---------------------------------------------------------------------------
# Engine: assemblyai
# ---------------------------------------------------------------------------


def assemblyai_key() -> str:
    key = os.environ.get(AAI_KEY_ENV, "").strip()
    if not key:
        raise typer.BadParameter(
            f"{AAI_KEY_ENV} is not set. The assemblyai engine cannot run without it.\n"
            "  • get a key at https://www.assemblyai.com/dashboard/signup\n"
            f"  • export {AAI_KEY_ENV}=... (or put it in your shell's secrets file)\n"
            "  • or transcribe locally with --engine mlx-whisper (needs verified isolated "
            "camera audio for speaker labels)"
        )
    return key


def assemblyai_transcribe(audio: Path, language: str, poll_timeout_s: float) -> list[RawWord]:
    key = assemblyai_key()
    headers = {"authorization": key}

    logger.info(f"uploading {audio.name} ({audio.stat().st_size:,} bytes) to AssemblyAI")
    with httpx.Client(timeout=httpx.Timeout(None)) as client, audio.open("rb") as fh:
        upload = client.post(f"{AAI_BASE}/upload", headers=headers, content=fh)
    if upload.status_code != 200:
        raise RuntimeError(f"AssemblyAI upload failed ({upload.status_code}): {upload.text[:500]}")
    audio_url = upload.json()["upload_url"]

    body = {
        "audio_url": audio_url,
        "speaker_labels": True,
        "punctuate": True,
        "format_text": True,
        "language_code": language,
    }
    with httpx.Client(timeout=60.0) as client:
        created = client.post(f"{AAI_BASE}/transcript", headers=headers, json=body)
        if created.status_code not in (200, 201):
            raise RuntimeError(
                f"AssemblyAI rejected the transcription request ({created.status_code}): "
                f"{created.text[:500]}"
            )
        transcript_id = created.json()["id"]
        logger.info(f"AssemblyAI transcript {transcript_id} queued; polling")

        deadline = time.monotonic() + poll_timeout_s
        while True:
            polled = client.get(f"{AAI_BASE}/transcript/{transcript_id}", headers=headers)
            if polled.status_code != 200:
                raise RuntimeError(f"AssemblyAI poll failed ({polled.status_code}): {polled.text[:500]}")
            data = polled.json()
            status = data.get("status")
            if status == "completed":
                break
            if status == "error":
                raise RuntimeError(f"AssemblyAI transcription failed: {data.get('error')}")
            if time.monotonic() > deadline:
                raise RuntimeError(
                    f"AssemblyAI transcript {transcript_id} still {status} after "
                    f"{poll_timeout_s / 60:.0f} min — raise --poll-timeout-min or check "
                    "https://status.assemblyai.com"
                )
            logger.info(f"  status={status}")
            time.sleep(5.0)

    words = data.get("words") or []
    if not words:
        raise RuntimeError(
            f"AssemblyAI returned no words for {audio.name} — is the audio silent or music-only?"
        )
    missing_speaker = sum(1 for w in words if not w.get("speaker"))
    if missing_speaker:
        raise RuntimeError(
            f"{missing_speaker}/{len(words)} words came back without a diarization label — "
            "speaker_labels did not run; re-submit or use --engine mlx-whisper with isolated cameras"
        )
    return [
        RawWord(
            w=w["text"],
            start=round(w["start"] / 1000.0, 3),
            end=round(w["end"] / 1000.0, 3),
            conf=round(float(w["confidence"]), 4) if w.get("confidence") is not None else None,
            label=str(w["speaker"]),
        )
        for w in words
    ]


# ---------------------------------------------------------------------------
# Engine: mlx-whisper
# ---------------------------------------------------------------------------


def mlx_whisper_transcribe(audio: Path, language: str, model: str) -> list[RawWord]:
    try:
        import mlx_whisper  # noqa: PLC0415 — optional, Apple-Silicon-only dependency
    except ImportError as exc:
        raise RuntimeError(
            "mlx-whisper is not installed in this environment (it is declared for "
            "darwin/arm64 only). Run this engine on Apple Silicon, or use "
            f"--engine assemblyai. Import error: {exc}"
        ) from exc

    logger.info(f"transcribing {audio.name} locally with {model} (word timestamps on)")
    result = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=model,
        word_timestamps=True,
        language=language,
        verbose=False,
        # See align_subtitles.py: the default (True) lets the decoder silently drop a passage
        # it judges redundant. A transcript that quietly omits speech is worse than no
        # transcript — every downstream stage trusts this as ground truth.
        condition_on_previous_text=False,
    )
    words: list[RawWord] = []
    for segment in result.get("segments", []):
        for w in segment.get("words", []):
            text = str(w["word"]).strip()
            if not text:
                continue
            words.append(
                RawWord(
                    w=text,
                    start=round(float(w["start"]), 3),
                    end=round(float(w["end"]), 3),
                    conf=round(float(w["probability"]), 4) if w.get("probability") is not None else None,
                    label=None,
                )
            )
    if not words:
        raise RuntimeError(
            f"mlx-whisper produced no words for {audio.name} — the audio may be silent, or the "
            "model returned segments without word timestamps"
        )
    return words


# ---------------------------------------------------------------------------
# Speaker attribution from isolated camera audio (mlx-whisper path)
# ---------------------------------------------------------------------------


def decode_mono(path: Path) -> np.ndarray:
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed decoding audio from {path} (exit {proc.returncode}): "
            f"{proc.stderr.decode(errors='replace').strip()}"
        )
    samples = np.frombuffer(proc.stdout, dtype=np.int16)
    if samples.size == 0:
        raise RuntimeError(f"{path} has no audio stream — it cannot carry a speaker's voice activity")
    return samples.astype(np.float32) / 32768.0


def energy_envelope(signal: np.ndarray) -> np.ndarray:
    n = signal.size // HOP
    frames = signal[: n * HOP].reshape(n, HOP).astype(np.float64)
    rms = np.sqrt((frames * frames).mean(axis=1))
    reference = float(np.percentile(rms, 90))
    if reference <= 0.0:
        raise RuntimeError("camera track is digital silence — it carries no voice activity")
    return rms / reference


def require_isolated_tracks(episode: Episode) -> list[tuple[str, str, float]]:
    """[(speaker_id, camera rel path, offset_s)] — or a loud refusal explaining the alternatives."""
    problems: list[str] = []
    tracks: list[tuple[str, str, float]] = []
    if not episode.speakers:
        problems.append("episode.yaml lists no speakers at all")
    for speaker in episode.speakers:
        if not speaker.camera_file:
            problems.append(f"speaker {speaker.id} ({speaker.name}) has no camera_file")
            continue
        entry = next((e for e in episode.sync if e.file == speaker.camera_file), None)
        if entry is None:
            problems.append(f"{speaker.camera_file} has no sync entry")
        elif not entry.verified:
            problems.append(f"{speaker.camera_file} sync is not verified (confidence {entry.confidence})")
        else:
            tracks.append((speaker.id, speaker.camera_file, entry.offset_s))
    if problems:
        raise typer.BadParameter(
            "mlx-whisper has no diarizer, so speaker labels must come from isolated camera audio, "
            "and every speaker needs a verified sync entry. Blocking problems:\n  - "
            + "\n  - ".join(problems)
            + "\n\nFix by either:\n"
            "  (a) re-running with --engine assemblyai (cloud diarization, needs "
            f"{AAI_KEY_ENV}); or\n"
            "  (b) `ingest.py register-camera` for each speaker, then `sync_cameras.py compute`, "
            "`verify` and `mark-verified`.\n"
            "This script will not guess who is speaking."
        )
    return tracks


def turns(words: list[RawWord]) -> list[tuple[int, int]]:
    """Contiguous [start, end) word ranges separated by more than TURN_MAX_GAP_S."""
    spans: list[tuple[int, int]] = []
    start = 0
    for i in range(1, len(words)):
        if words[i].start - words[i - 1].end > TURN_MAX_GAP_S:
            spans.append((start, i))
            start = i
    spans.append((start, len(words)))
    return spans


def attribute_speakers(root: Path, episode: Episode, words: list[RawWord]) -> list[str]:
    """Speaker id per word, from which isolated track carries the energy at that moment."""
    tracks = require_isolated_tracks(episode)
    if len(tracks) == 1:
        speaker_id = tracks[0][0]
        logger.info(f"single registered speaker — every word attributed to {speaker_id}")
        return [speaker_id] * len(words)

    envelopes: dict[str, tuple[np.ndarray, float]] = {}
    for speaker_id, rel, offset_s in tracks:
        path = root / rel
        if not path.is_file():
            raise typer.BadParameter(f"camera file missing on disk: {path}")
        logger.info(f"measuring voice activity on {rel} (offset {offset_s:+.3f}s)")
        envelopes[speaker_id] = (energy_envelope(decode_mono(path)), offset_s)

    def energy(speaker_id: str, start_s: float, end_s: float) -> float:
        env, offset = envelopes[speaker_id]
        lo = int(max(0.0, start_s - WORD_PAD_S - offset) / HOP_S)
        hi = int(max(0.0, end_s + WORD_PAD_S - offset) / HOP_S) + 1
        lo, hi = min(lo, env.size), min(max(hi, lo + 1), env.size)
        if hi <= lo:
            return 0.0
        return float(np.mean(env[lo:hi]))

    ids = [t[0] for t in tracks]
    assigned = ["" for _ in words]
    decisive_words = 0
    silent_spans: list[tuple[float, float]] = []

    for lo, hi in turns(words):
        span_start, span_end = words[lo].start, words[hi - 1].end
        scores = {sid: energy(sid, span_start, span_end) for sid in ids}
        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        winner, best = ordered[0]
        runner_up = ordered[1][1]
        if best < SILENT_TRACK_ENERGY:
            silent_spans.append((span_start, span_end))
            continue
        for i in range(lo, hi):
            assigned[i] = winner
        if runner_up <= 0.0 or best / runner_up >= DECISIVE_RATIO:
            decisive_words += hi - lo

    if silent_spans:
        shown = ", ".join(f"{fmt_mmss(a)}-{fmt_mmss(b)}" for a, b in silent_spans[:5])
        raise RuntimeError(
            f"{len(silent_spans)} speaking turn(s) have no energy on ANY isolated track "
            f"(e.g. {shown}) — nobody can be attributed there. Either the sync offsets are wrong, "
            "a camera file is truncated, or a speaker is missing a camera. Re-run "
            "`sync_cameras.py compute`/`verify`, or transcribe with --engine assemblyai. "
            "Refusing to write a transcript with guessed speakers."
        )

    fraction = decisive_words / len(words)
    logger.info(f"speaker attribution decisive on {fraction:.1%} of words (threshold {DECISIVE_FRACTION:.0%})")
    if fraction < DECISIVE_FRACTION:
        raise RuntimeError(
            f"only {fraction:.1%} of words have a clearly dominant track (needed "
            f"{DECISIVE_FRACTION:.0%}). The camera tracks are not isolated enough — heavy bleed "
            "between microphones, or a track that is a copy of the room mix. Use "
            "--engine assemblyai, or supply genuinely isolated per-speaker audio. "
            "Refusing to write a transcript with guessed speakers."
        )
    return assigned


# ---------------------------------------------------------------------------
# Diarization label → speaker id
# ---------------------------------------------------------------------------


def parse_map(pairs: list[str], episode: Episode) -> dict[str, str]:
    mapping: dict[str, str] = {}
    known = episode.speaker_ids()
    for pair in pairs:
        if pair.count("=") != 1:
            raise typer.BadParameter(f"--map {pair!r} must look like SPEAKER_00=host1")
        label, speaker_id = (part.strip() for part in pair.split("="))
        if not label or not speaker_id:
            raise typer.BadParameter(f"--map {pair!r} has an empty side")
        if speaker_id not in known:
            raise typer.BadParameter(
                f"--map {pair!r} targets speaker id {speaker_id!r} which is not in episode.yaml "
                f"speakers (known: {sorted(known) or 'none — register speakers first'})"
            )
        if label in mapping:
            raise typer.BadParameter(f"--map lists label {label!r} twice")
        mapping[label] = speaker_id
    return mapping


def demand_mapping(words: list[RawWord], mapping: dict[str, str], episode: Episode) -> dict[str, str]:
    labels = sorted({w.label for w in words if w.label})
    unmapped = [label for label in labels if label not in mapping]
    extra = [label for label in mapping if label not in labels]
    if extra:
        raise typer.BadParameter(
            f"--map mentions label(s) {extra} that the diarizer never produced; it produced {labels}"
        )
    if not unmapped:
        return mapping

    console.print(
        f"[bold yellow]Speaker mapping required[/] — the diarizer found {len(labels)} label(s): "
        f"{', '.join(labels)}"
    )
    provisional = build_segments(words, {label: label for label in labels})
    for label in labels:
        table = RichTable(title=f"label {label}", header_style="bold cyan", show_lines=False)
        table.add_column("time")
        table.add_column("text", overflow="fold")
        for segment in [s for s in provisional if s.speaker == label][:3]:
            table.add_row(fmt_mmss(segment.start), segment.text[:200])
        console.print(table)

    known = sorted(episode.speaker_ids())
    suggestion = " ".join(
        f"--map {label}={known[i] if i < len(known) else '<speaker-id>'}"
        for i, label in enumerate(labels)
    )
    console.print(
        "[bold]Read the samples, then re-run with the mapping[/] "
        f"(episode.yaml speakers: {known or 'none registered yet'}):\n  "
        f"transcribe.py <episode-root> {suggestion}"
    )
    raise typer.Exit(2)


# ---------------------------------------------------------------------------
# Transcript assembly
# ---------------------------------------------------------------------------


def build_words(words: list[RawWord], speakers: list[str]) -> list[Word]:
    return [
        Word(w=r.w, start=r.start, end=r.end, speaker=speaker, conf=r.conf)
        for r, speaker in zip(words, speakers)
    ]


def build_segments(words: list[RawWord], mapping: dict[str, str]) -> list[TranscriptSegment]:
    speakers = [mapping[w.label] if w.label else "" for w in words]
    return segments_from(build_words(words, speakers))


def segments_from(words: list[Word]) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    buffer: list[Word] = []

    def flush() -> None:
        if not buffer:
            return
        segments.append(
            TranscriptSegment(
                start=buffer[0].start,
                end=buffer[-1].end,
                speaker=buffer[0].speaker,
                text=" ".join(w.w for w in buffer).strip(),
            )
        )
        buffer.clear()

    for word in words:
        if buffer:
            same_speaker = word.speaker == buffer[0].speaker
            gap = word.start - buffer[-1].end
            length = word.end - buffer[0].start
            if not same_speaker or gap > SEGMENT_MAX_GAP_S or length > SEGMENT_MAX_DURATION_S:
                flush()
        buffer.append(word)
    flush()
    return segments


def transcript_markdown(episode: Episode, transcript: Transcript) -> str:
    names = {s.id: s.name for s in episode.speakers}
    header = [
        f"# {episode.episode.title} — transcript",
        "",
        f"- engine: `{transcript.engine}`",
        f"- language: `{transcript.language}`",
        f"- audio: `{transcript.audio_file}`",
        f"- words: {len(transcript.words)}",
        f"- segments: {len(transcript.segments)}",
        "- speakers: " + ", ".join(f"`{sid}` ({name})" for sid, name in names.items()),
        "",
        "---",
        "",
    ]
    body = [
        f"[{fmt_mmss(s.start)}] {s.speaker}: {s.text}" for s in transcript.segments
    ]
    return "\n".join(header + body) + "\n"


def render_summary(transcript: Transcript, episode: Episode) -> None:
    per_speaker: dict[str, tuple[int, float]] = {}
    for segment in transcript.segments:
        count, seconds = per_speaker.get(segment.speaker, (0, 0.0))
        per_speaker[segment.speaker] = (count + len(segment.text.split()), seconds + segment.end - segment.start)
    names = {s.id: s.name for s in episode.speakers}
    table = RichTable(title="Transcript", header_style="bold cyan")
    for col in ("speaker", "name", "words", "speaking time"):
        table.add_column(col)
    for speaker, (count, seconds) in sorted(per_speaker.items()):
        table.add_row(speaker, names.get(speaker, "?"), str(count), fmt_mmss(seconds))
    console.print(table)


def assert_monotonic(words: list[Word]) -> None:
    bad = [
        f"#{i} {w.w!r} {w.start:.3f}-{w.end:.3f} after {words[i - 1].end:.3f}"
        for i, w in enumerate(words)
        if w.end < w.start or (i > 0 and w.start < words[i - 1].start)
    ]
    if bad:
        raise RuntimeError(
            f"{len(bad)} word timestamp(s) are not monotonic — the transcript cannot drive "
            f"alignment. First offenders: {bad[:5]}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@app.command()
def main(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    engine: str | None = typer.Option(None, "--engine", help=f"One of: {', '.join(ENGINES)}"),
    map_: list[str] = typer.Option(
        None, "--map", help="Diarization label to speaker id, e.g. --map A=host1 --map B=guest1"
    ),
    model: str = typer.Option(
        "mlx-community/whisper-large-v3-turbo", "--model", help="mlx-whisper model repo"
    ),
    poll_timeout_min: float = typer.Option(
        120.0, "--poll-timeout-min", help="How long to wait for a cloud transcription"
    ),
    no_cache: bool = typer.Option(False, "--no-cache", help="Ignore any cached raw ASR output"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", help="Pipeline defaults YAML"),
) -> None:
    """Transcribe EPISODE_ROOT's audio to transcript.json + transcript.md with speaker labels."""
    root = episode_root.resolve()
    defaults = load_defaults(config.resolve())
    engine_name, language = resolve_engine(engine, defaults, config)
    episode = load_episode(root / "episode.yaml")
    audio, audio_rel = audio_for_transcription(root, episode)

    if engine_name == "mlx-whisper":
        if map_:
            raise typer.BadParameter(
                "--map applies to diarization engines only; mlx-whisper derives speakers from "
                "isolated camera audio, so there are no labels to map"
            )
        require_isolated_tracks(episode)  # fail before spending minutes on ASR, not after
    else:
        assemblyai_key()  # same: refuse before uploading anything

    cache = cache_path(root, engine_name)
    size = audio.stat().st_size
    raw = None if no_cache else read_cache(cache, audio_rel, size)
    if raw is None:
        if engine_name == "assemblyai":
            raw = assemblyai_transcribe(audio, language, poll_timeout_min * 60.0)
        else:
            raw = mlx_whisper_transcribe(audio, language, model)
        write_cache(cache, audio_rel, size, engine_name, raw)
        logger.info(f"cached raw ASR output at {cache}")

    if engine_name == "assemblyai":
        mapping = demand_mapping(raw, parse_map(list(map_ or []), episode), episode)
        speakers = [mapping[w.label] for w in raw]
    else:
        speakers = attribute_speakers(root, episode, raw)

    words = build_words(raw, speakers)
    assert_monotonic(words)
    segments = segments_from(words)

    transcript = Transcript(
        engine=engine_name,
        language=language,
        audio_file=audio_rel,
        words=words,
        segments=segments,
    )
    json_rel, md_rel = "transcript/transcript.json", "transcript/transcript.md"
    save_transcript(root / json_rel, transcript)
    (root / md_rel).write_text(transcript_markdown(episode, transcript))

    episode.transcript = TranscriptRef(
        json_file=json_rel,
        md=md_rel,
        engine=engine_name,
        language=language,
        word_count=len(words),
    )
    save_episode(root / "episode.yaml", episode)

    render_summary(transcript, episode)
    console.print(
        f"[bold green]OK[/] {len(words)} words / {len(segments)} segments via {engine_name} → "
        f"{json_rel}, {md_rel}"
    )


def cli() -> None:
    """CLI entry point — the one place operational failures become a clean exit."""
    try:
        app()
    except (RuntimeError, FileNotFoundError) as exc:  # deliberate, actionable failures
        console.print(f"[bold red]error[/] {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    cli()
