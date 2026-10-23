#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pytest>=8",
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "google-api-python-client>=2.120",
#   "google-auth>=2.30",
#   "google-auth-httplib2>=0.2",
# ]
# ///
"""freeze_picks timeline construction — run: `uv run --script scripts/test_freeze_picks.py`.

Builds clips from synthetic transcripts and checks them with validate_clip's own invariant
checks (1, 2, 11), so "freeze output validates" is tested against the real validator.
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import freeze_picks
from gdoc import Model, PickMeta
from pslib import Clip, Transcript
from validate_clip import check_1_contiguous, check_2_durations, check_11_dialogue_covers_audio


def word(speaker: str, w: str, start: float, end: float) -> dict:
    return {"w": w, "start": start, "end": end, "speaker": speaker}


def freeze(words: list[dict], fmt: str = "clip", cut: set[int] = frozenset(), owned: set[int] | None = None):
    pid = "C1" if fmt == "clip" else "S1"
    owned = set(range(len(words))) if owned is None else owned
    ctx = SimpleNamespace(
        words=words, cfg={"boundary_pad_s": 0.12},
        data={"media": {"episode_video": "source/ep.mov"},
              "subtitles": {"font": "Inter", "base_color": "#FFD400", "emphasis_color": "#FFFFFF"}})
    model = Model(owner=[pid if i in owned else None for i in range(len(words))],
                  cut=[i in cut for i in range(len(words))],
                  picks={pid: PickMeta(pid, fmt, "#ff0000", "approved", "t")})
    clip, _dur = freeze_picks.build_clip(ctx, model, pid, "t", None)
    return clip


def findings(clip: dict, words: list[dict]) -> list:
    c = Clip.model_validate(clip)
    tr = Transcript.model_validate({"engine": "t", "language": "en", "audio_file": "a.wav", "words": words})
    return check_1_contiguous(c) + check_2_durations(c) + check_11_dialogue_covers_audio(c, tr)


def assert_valid(clip: dict, words: list[dict]) -> None:
    for seg in clip["timeline"]:
        assert seg["source_in"] < seg["source_out"], seg
    assert findings(clip, words) == []


def test_non_overlapping_two_speaker_bounds_unchanged():
    """Golden values from the pre-overlap algorithm: abut at the gap midpoint when gap <= 2*pad,
    pad independently otherwise, never pad into a neighbouring (cut / unowned) word."""
    words = [
        word("A", "hello", 10.00, 10.40), word("A", "there", 10.45, 10.80),
        word("B", "hi", 10.90, 11.20), word("B", "friend", 11.25, 11.60),
        word("A", "cutme", 12.00, 12.30), word("A", "again", 12.50, 12.90),
        word("B", "fine", 13.50, 13.80), word("C", "tail", 14.50, 14.80),
    ]
    clip = freeze(words, cut={4}, owned=set(range(7)))
    got = [(s["speaker"], s["source_in"], s["source_out"], s["dialogue"]) for s in clip["timeline"]]
    assert got == [("A", 9.88, 10.85, "hello there"), ("B", 10.85, 11.72, "hi friend"),
                   ("A", 12.38, 13.02, "again"), ("B", 13.38, 13.92, "fine")]
    assert_valid(clip, words)


def test_overlapping_speakers_segment_in_time_order():
    """Deutsch C2 S22-S24: the host's 'Yeah,' starts before the guest's 'best' ends and spans the
    guest's 'explanation.'. Transcript order g,g,h,g used to yield a reversed segment
    [1700.428, 1700.255]."""
    words = [
        word("guest1", "your", 1699.035, 1699.197), word("guest1", "best", 1699.197, 1699.456),
        word("host1", "Yeah,", 1699.255, 1701.353), word("guest1", "explanation.", 1699.504, 1700.135),
        word("host1", "So", 1701.500, 1701.700), word("host1", "what", 1701.700, 1701.950),
    ]
    clip = freeze(words)
    assert [(s["speaker"], s["dialogue"]) for s in clip["timeline"]] == [
        ("guest1", "your best explanation."), ("host1", "Yeah, So what")]
    assert_valid(clip, words)


def test_stretched_backchannel_is_absorbed_not_a_segment():
    """Deutsch S4 S11: the host's 'Yeah.' is force-aligned across 10 s of the guest's monologue.
    It cannot be majority-inside any host segment without chopping the guest, so it stays in
    the audio uncaptioned and the guest's speech is one segment."""
    words = [
        word("guest1", "is", 3638.52, 3638.66), word("host2", "Yeah.", 3638.52, 3648.62),
        word("guest1", "predictions", 3639.56, 3640.08), word("guest1", "can", 3640.14, 3640.30),
        word("guest1", "never", 3640.30, 3640.53), word("guest1", "be", 3640.54, 3640.80),
        word("guest1", "certain,", 3641.52, 3642.03), word("guest1", "So", 3645.29, 3645.61),
        word("guest1", "they", 3646.64, 3646.72), word("host2", "Right.", 3649.00, 3649.30),
    ]
    clip = freeze(words)
    assert [(s["speaker"], s["dialogue"]) for s in clip["timeline"]] == [
        ("guest1", "is predictions can never be certain, So they"), ("host2", "Right.")]
    assert_valid(clip, words)


def test_turn_exchange_crosstalk_validates():
    """Deutsch C2 1338 s: both speakers talk over a turn change."""
    words = [
        word("guest1", "done.", 1338.22, 1338.42), word("host1", "100%", 1338.24, 1338.76),
        word("guest1", "Well", 1338.60, 1338.65), word("host1", "on", 1338.90, 1339.00),
        word("guest1", "done.", 1338.65, 1339.28), word("host1", "the", 1339.00, 1339.08),
        word("host1", "same", 1339.08, 1339.30), word("host1", "page.", 1339.35, 1339.70),
    ]
    words.sort(key=lambda w: (w["start"], w["end"]))
    clip = freeze(words, fmt="short")
    assert_valid(clip, words)


def test_word_ending_before_it_starts_fails_loud():
    words = [word("A", "ok", 5.0, 5.4), word("B", "bad", 5.6, 5.5)]
    with pytest.raises(SystemExit):
        freeze(words)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
