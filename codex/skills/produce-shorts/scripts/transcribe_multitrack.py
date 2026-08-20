#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["typer", "loguru", "rich", "pyyaml", "pydantic", "httpx", "numpy"]
# ///
"""Transcribe an aligned multitrack episode — one isolated track per speaker.

Why this exists alongside `transcribe.py`:

`transcribe.py` transcribes ONE mixed file and then has to work out who spoke, either
from cloud diarization (which can be wrong) or by comparing camera audio energy (which
needs verified sync). Both are inferences.

Here there is nothing to infer. Each track contains exactly one speaker, so attribution
is exact BY CONSTRUCTION: every word from `track_host1.mov` is host1's, full stop. No
diarizer runs, no `--map` step exists to get backwards, and a diarization mistake is not
a failure mode this command has.

Each track is transcribed independently, its words are stamped with that track's speaker
id and shifted by that track's sync offset, and the results are merged into one
timeline-ordered transcript.

Two real hazards are handled explicitly rather than hoped away:

* **Bleed.** If two speakers shared a room, quiet copies of one voice appear on the
  other's track and would be transcribed twice. `--min-conf` drops low-confidence words;
  the summary prints per-track word counts so a track transcribing far more than its
  speaker actually said is visible rather than silent.
* **Silence hallucination.** ASR on a mostly-silent track can invent text. Same defence:
  confidence floor, plus a printed count of what each track contributed.

Requires ASSEMBLYAI_API_KEY. Raw ASR output is cached per track, so re-running after a
change costs nothing extra.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

sys.path.insert(0, str(Path(__file__).resolve().parent))

from pslib import (  # noqa: E402
    Transcript,
    TranscriptSegment,
    Word,
    load_episode,
    save_episode,
    save_transcript,
)
from transcribe import (  # noqa: E402
    RawWord,
    assemblyai_transcribe,
    assert_monotonic,
    read_cache,
    segments_from,
    transcript_markdown,
    write_cache,
)

app = typer.Typer(add_completion=False, help=__doc__)
console = Console()

ENGINE = "assemblyai"


def track_cache(root: Path, speaker_id: str) -> Path:
    return root / "transcript" / f".raw-{ENGINE}-{speaker_id}.json"


@app.command()
def main(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    language: str = typer.Option(None, "--language", help="Override episode language"),
    min_conf: float = typer.Option(
        0.30, "--min-conf",
        help="Drop words below this ASR confidence (guards silence hallucination and bleed)",
    ),
    poll_timeout_min: float = typer.Option(120.0, "--poll-timeout-min", help="Cloud wait budget"),
    no_cache: bool = typer.Option(False, "--no-cache", help="Ignore cached raw ASR output"),
) -> None:
    """Transcribe every speaker's isolated track and merge into one transcript."""
    root = Path(episode_root)
    episode = load_episode(root / "episode.yaml")
    lang = language or episode.transcript.language

    tracks = [s for s in episode.speakers if s.camera_file]
    if not tracks:
        raise RuntimeError(
            "no speaker in episode.yaml has a camera_file — this command needs one isolated "
            "track per speaker. For a single mixed recording use transcribe.py instead."
        )
    missing = [s.id for s in tracks if not (root / s.camera_file).is_file()]
    if missing:
        raise RuntimeError(f"camera_file missing on disk for speaker(s): {missing}")

    offsets = {e.file: e.offset_s for e in episode.sync}
    unsynced = [s.id for s in tracks if s.camera_file not in offsets]
    if unsynced:
        raise RuntimeError(
            f"no sync entry for speaker(s) {unsynced} — every track needs a known offset "
            "before its words can be placed on the episode timeline"
        )
    unverified = [e.file for e in episode.sync if not e.verified]
    if unverified:
        raise RuntimeError(
            f"sync is unverified for {unverified} — refusing to build a transcript whose "
            "word timings would be unreliable. Verify alignment first."
        )

    all_words: list[Word] = []
    stats: list[tuple[str, str, int, int, float]] = []

    for spk in tracks:
        audio = root / spk.camera_file
        offset = offsets[spk.camera_file]
        cache = track_cache(root, spk.id)
        size = audio.stat().st_size

        raw: list[RawWord] | None = None
        if not no_cache:
            raw = read_cache(cache, spk.camera_file, size)
            if raw:
                logger.info(f"{spk.id}: reusing cached ASR ({len(raw)} words)")
        if raw is None:
            logger.info(f"{spk.id} ({spk.name}): transcribing {audio.name}")
            raw = assemblyai_transcribe(audio, lang, poll_timeout_min * 60)
            write_cache(cache, spk.camera_file, size, ENGINE, raw)

        kept = [w for w in raw if w.conf is None or w.conf >= min_conf]
        dropped = len(raw) - len(kept)
        for w in kept:
            all_words.append(
                Word(w=w.w, start=w.start + offset, end=w.end + offset,
                     speaker=spk.id, conf=w.conf)
            )
        spoken = sum(w.end - w.start for w in kept)
        stats.append((spk.id, spk.name, len(kept), dropped, spoken))
        logger.info(
            f"{spk.id}: kept {len(kept)} words, dropped {dropped} below conf {min_conf}"
        )

    if not all_words:
        raise RuntimeError("every track produced zero usable words — check the audio and the key")

    all_words.sort(key=lambda w: (w.start, w.end))
    assert_monotonic(all_words)
    segments: list[TranscriptSegment] = segments_from(all_words)

    transcript = Transcript(
        engine=ENGINE,
        language=lang,
        audio_file=episode.media.episode_audio or episode.media.episode_video,
        words=all_words,
        segments=segments,
    )
    save_transcript(root / episode.transcript.json_file, transcript)
    (root / episode.transcript.md).write_text(transcript_markdown(episode, transcript))

    episode.transcript.engine = ENGINE
    episode.transcript.language = lang
    episode.transcript.word_count = len(all_words)
    save_episode(root / "episode.yaml", episode)

    table = RichTable(title="multitrack transcription", header_style="bold cyan")
    for col in ("speaker", "name", "words", "dropped", "speech_s", "share"):
        table.add_column(col)
    total_speech = sum(s[4] for s in stats) or 1.0
    for sid, name, kept, dropped, spoken in stats:
        table.add_row(sid, name, str(kept), str(dropped), f"{spoken:.0f}",
                      f"{spoken / total_speech * 100:.1f}%")
    console.print(table)
    console.print(
        f"\nmerged [bold]{len(all_words)}[/] words into [bold]{len(segments)}[/] segments "
        f"spanning {all_words[0].start:.1f}s–{all_words[-1].end:.1f}s"
    )
    console.print(f"wrote {root / episode.transcript.json_file}")
    console.print(f"wrote {root / episode.transcript.md}")
    console.print(
        "\n[dim]Speaker attribution is exact — one track per speaker, no diarization.[/]"
    )


if __name__ == "__main__":
    app()
