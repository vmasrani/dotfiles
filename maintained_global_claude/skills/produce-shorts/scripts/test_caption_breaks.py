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
#   "pysubs2>=1.7",
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Caption breaks at a speaker change — run: `uv run --script scripts/test_caption_breaks.py -q`.

A caption card must never carry words from two timeline segments with different speakers: the viewer reads one
person's half-line and the next person's first word as one sentence ("Hmm. And so you think that maybe Actually,").
A speaker change is always a caption break; a break between two segments of the SAME speaker is still free.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import align_subtitles as asub
import validate_subtitles as vs
from psmedia import load_config
from pslib import Clip, tokenize
from test_quote_layout import aroll, short_clip

CFG = load_config().subtitles


def _clip(segments: list[tuple[str, float, float, str, str]]) -> Clip:
    """segments: (id, out_in, out_out, speaker, dialogue)."""
    base = short_clip([])
    timeline = [aroll(sid, a, b, spk) | {"dialogue": text} for sid, a, b, spk, text in segments]
    data = base.model_dump(mode="json") | {"timeline": timeline}
    data["output"] = data["output"] | {"duration_s": segments[-1][2] + 1.0}
    return Clip.model_validate(data)


def _hyp(clip: Clip) -> list[asub.HypWord]:
    """Each segment's words spread evenly over its output window — a stand-in for the transcribed audio."""
    out: list[asub.HypWord] = []
    for seg in clip.timeline:
        words = seg.dialogue.split()
        step = (seg.output_out - seg.output_in) / len(words)
        for k, raw in enumerate(words):
            for tok in tokenize(raw):
                out.append(asub.HypWord(tok, seg.output_in + k * step, seg.output_in + (k + 1) * step - 0.02, raw))
    return out


def _speaker_of_each_word(clip: Clip) -> list[str]:
    return [seg.speaker for seg in clip.timeline for _ in seg.dialogue.split()]


# The real bug (you-can-judge-an-idea-by-the-crazy-people-it-produces v3, 124.8 s): S28 host2 "Hmm. And so you think
# that maybe" then S05 host1 "Actually, I don't disagree with that at all."
HALF_LINE = [
    ("S28", 0.0, 1.05, "guest1", "Hmm. And so you think that maybe"),
    ("S05", 1.05, 2.35, "host1", "Actually, I don't disagree with that at all."),
]


def _card_speakers(clip: Clip, cards: list[asub.SubtitleLine]) -> list[set[str]]:
    speakers = _speaker_of_each_word(clip)
    out, k = [], 0
    for card in cards:
        n = len(card.text.split())
        out.append(set(speakers[k:k + n]))
        k += n
    return out


def test_a_speaker_change_is_always_a_caption_break() -> None:
    clip = _clip(HALF_LINE)
    cards = asub.derive_caption_lines(clip, _hyp(clip), CFG)
    assert [c.text for c in cards] == ["Hmm. And so you think that maybe", "Actually, I don't disagree with that at all."]
    assert all(len(s) == 1 for s in _card_speakers(clip, cards))


def test_cards_cover_every_dialogue_word_in_order_after_the_forced_break() -> None:
    clip = _clip(HALF_LINE)
    cards = asub.derive_caption_lines(clip, _hyp(clip), CFG)
    assert " ".join(c.text for c in cards).split() == " ".join(s.dialogue for s in clip.timeline).split()


def test_a_break_between_segments_of_the_same_speaker_is_still_free() -> None:
    clip = _clip([("S01", 0.0, 1.0, "host1", "So I think"), ("S02", 1.0, 2.0, "host1", "that is right")])
    cards = asub.derive_caption_lines(clip, _hyp(clip), CFG)
    assert [c.text for c in cards] == ["So I think that is right"]


def test_a_forced_break_that_leaves_a_short_card_still_meets_the_minimum_display() -> None:
    # Steven's "Hmm." is only 0.5 s of audio: the break stays, and the card is held to the configured minimum
    # (the next card starts after it) rather than the minimum being loosened.
    clip = _clip([("S28", 0.0, 0.5, "guest1", "Hmm."), ("S05", 0.5, 2.5, "host1", "Actually, I don't disagree with that at all.")])
    hyp = _hyp(clip)
    cards = asub.derive_caption_lines(clip, hyp, CFG)
    assert [c.text for c in cards][0] == "Hmm."
    clip = clip.model_copy(update={"subtitles": clip.subtitles.model_copy(update={"lines": cards})})
    aligned, _, _ = asub.align(clip, hyp)
    asub.clamp_windows(aligned, CFG.min_display_seconds, clip.output.duration_s, CFG.max_chars_per_second)
    assert all(a.end - a.start >= CFG.min_display_seconds - asub.EPSILON for a in aligned)
    assert all(a.end <= b.start + asub.EPSILON for a, b in zip(aligned, aligned[1:]))


# --- the validator invariant --------------------------------------------------------------------------------------


def _event(index: int, text: str) -> vs.Event:
    return vs.Event(index=index, start=float(index), end=float(index) + 1.0, lines=text.split("\\N"), style_name="Default",
                    font_size=60.0, alignment=5, margin_v=0.0, margin_l=0.0, margin_r=0.0, pos=None,
                    legacy_alignment_tag=None)


def test_validator_flags_an_event_that_spans_two_speakers() -> None:
    clip = _clip(HALF_LINE)
    script = vs.Script(1080, 1920, [_event(0, "Hmm. And so you think that\\Nmaybe Actually,"), _event(1, "I don't disagree with that at all.")])
    found = vs.check_speaker_breaks(script, clip)
    assert [f.check for f in found] == ["speaker_break"]
    assert "event 0" in found[0].where


def test_validator_passes_events_that_break_at_the_speaker_change() -> None:
    clip = _clip(HALF_LINE)
    script = vs.Script(1080, 1920, [_event(0, "Hmm. And so you think that\\Nmaybe"), _event(1, "Actually, I don't disagree\\Nwith that at all.")])
    assert vs.check_speaker_breaks(script, clip) == []


def test_validator_reports_an_event_it_cannot_locate_in_the_dialogue() -> None:
    clip = _clip(HALF_LINE)
    script = vs.Script(1080, 1920, [_event(0, "words that nobody says")])
    assert [f.check for f in vs.check_speaker_breaks(script, clip)] == ["speaker_break"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, *sys.argv[1:]]))
