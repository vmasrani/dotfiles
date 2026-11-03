#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "static-ffmpeg>=2.7",
#   "platformdirs>=4",
#   "pytest>=8",
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""B-roll overlays + insert segments — run: `uv run --script scripts/test_broll.py`.

Covers the timeline remap an insert causes (broll.insert_segment) and the overlay / insert
invariants validate_clip enforces (12, 13), checked with the real validator functions.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import broll
from broll import MediaInfo
from pslib import Clip, Overlay, TimelineSegment, Transcript
from validate_clip import (
    check_1_contiguous,
    check_2_durations,
    check_4_output_duration_value,
    check_11_dialogue_covers_audio,
    check_12_inserts,
    check_13_overlays,
)

SLUG = "c1"
BROLL = f"clips/{SLUG}/broll"


def word(w: str, start: float, end: float, speaker: str = "host1") -> dict:
    return {"w": w, "start": start, "end": end, "speaker": speaker}


# Episode words: "one two three four five" over source 100-110, "six seven" over 110-115 (host2).
WORDS = [
    word("One", 100.2, 100.8), word("two", 101.0, 101.6), word("three", 102.0, 102.9),
    word("four", 105.0, 105.5), word("five.", 108.0, 109.5),
    word("Six", 110.5, 111.0, "host2"), word("seven.", 112.0, 113.0, "host2"),
]


def seg(sid, src_in, src_out, out_in, out_out, dialogue, speaker="host1", transition="cut") -> dict:
    return {
        "id": sid, "source_file": "source/episode.mp4", "source_in": src_in, "source_out": src_out,
        "output_in": out_in, "output_out": out_out, "dialogue": dialogue, "speaker": speaker,
        "audio": "as-recorded",
        "visual": {"kind": "aroll", "treatment": "source-frame", "speakers": None, "locked": False,
                   "reason": None, "asset_id": None, "motion": None, "crop": None},
        "transition": transition,
    }


def make_clip(overlays: list[dict] | None = None, timeline: list[dict] | None = None) -> Clip:
    timeline = timeline or [
        seg("S01", 100.0, 110.0, 0.0, 10.0, "One two three four five."),
        seg("S02", 110.0, 115.0, 10.0, 15.0, "Six seven.", speaker="host2"),
    ]
    return Clip.model_validate({
        "clip": {"id": SLUG, "pick": "C1", "format": "clip", "title": "t", "status": "frozen",
                 "why": "w", "ends_on": "seven."},
        "timeline": timeline,
        "subtitles": {"font": "Inter Semibold", "base_color": "#FFFFFF", "emphasis_palette": ["#FFD34D"],
                      "position_default": "bottom-center", "lines": []},
        "broll": {"provenance": "broll/provenance.json", "protected_tail_s": 3.0},
        "overlays": overlays or [],
        "output": {"aspect": "16:9", "resolution": "1920x1080", "fps": 30.0,
                   "duration_s": timeline[-1]["output_out"] if timeline else 15.0},
        "render": {"versions": []},
    })


def insert_seg(dur: float = 3.0) -> TimelineSegment:
    return TimelineSegment.model_validate({
        "id": "I01", "source_file": f"{BROLL}/talk_insert.mp4", "source_in": 0.0, "source_out": dur,
        "output_in": 0.0, "output_out": dur, "dialogue": "That's not a dog.", "speaker": "guest",
        "audio": "as-recorded",
        "visual": {"kind": "insert", "treatment": "letterbox", "crop": None},
        "transition": "dip-6f",
        "insert": {"speaker_name": "David Deutsch", "words": "broll/talk_insert.words.json"},
    })


def transcript() -> Transcript:
    return Transcript.model_validate({"engine": "t", "language": "en", "audio_file": "a.wav", "words": WORDS})


def pip(oid: str, start: float, end: float, asset: str = "hero.png", **kw) -> dict:
    return {"id": oid, "mode": "pip", "start": start, "end": end,
            "box": {"x": 1300, "y": 60, "w": 560, "h": 316},
            "shots": [{"asset": asset}], **kw}


def lt(oid: str, start: float, end: float) -> dict:
    return {"id": oid, "mode": "lowerthird", "start": start, "end": end,
            "lines": [{"runs": [{"text": "David Deutsch"}]}]}


def index(**extra: MediaInfo) -> dict[str, MediaInfo]:
    base = {
        "hero.png": MediaInfo(exists=True, duration=None, has_audio=False, provenance={"license": "x"}),
        "build.mp4": MediaInfo(exists=True, duration=9.0, has_audio=False, provenance={"license": "x"}),
        "talk_insert.mp4": MediaInfo(exists=True, duration=23.0, has_audio=True, provenance={"license": "x"}),
    }
    return {**base, **extra}


# ---------------------------------------------------------------------------
# insert_segment: timeline remap
# ---------------------------------------------------------------------------


def test_insert_splits_containing_segment_and_shifts_everything_after():
    out = broll.insert_segment(make_clip(), at=4.0, insert=insert_seg(3.0), words=transcript().words,
                               transition_in="dip-6f")
    ids = [s.id for s in out.timeline]
    assert ids == ["S01", "I01", "S03", "S02"]
    s01, i01, s03, s02 = out.timeline
    assert (s01.source_in, s01.source_out, s01.output_in, s01.output_out) == (100.0, 104.0, 0.0, 4.0)
    assert (i01.output_in, i01.output_out) == (4.0, 7.0)
    assert (s03.source_in, s03.source_out, s03.output_in, s03.output_out) == (104.0, 110.0, 7.0, 13.0)
    assert (s02.output_in, s02.output_out) == (13.0, 18.0)
    assert out.output.duration_s == 18.0
    assert s01.transition == "dip-6f" and i01.transition == "dip-6f" and s03.transition == "cut"


def test_insert_splits_dialogue_on_the_word_gap_and_still_validates():
    out = broll.insert_segment(make_clip(), at=4.0, insert=insert_seg(3.0), words=transcript().words,
                               transition_in="dip-6f")
    s01, _, s03, _ = out.timeline
    assert s01.dialogue == "One two three"
    assert s03.dialogue == "four five."
    assert check_1_contiguous(out) == []
    assert check_2_durations(out) == []
    assert check_4_output_duration_value(out) == []
    assert check_11_dialogue_covers_audio(out, transcript()) == []


def test_insert_shifts_overlays_after_the_insert_point_and_keeps_earlier_ones():
    clip = make_clip(overlays=[pip("B1", 1.0, 3.5), pip("B2", 5.0, 9.0), lt("B3", 11.0, 12.0)])
    out = broll.insert_segment(clip, at=4.0, insert=insert_seg(3.0), words=transcript().words,
                               transition_in="dip-6f")
    windows = {o.id: (o.start, o.end) for o in out.overlays}
    assert windows == {"B1": (1.0, 3.5), "B2": (8.0, 12.0), "B3": (14.0, 15.0)}


def test_insert_refuses_an_overlay_that_straddles_the_insert_point():
    clip = make_clip(overlays=[pip("B1", 3.0, 5.0)])
    with pytest.raises(ValueError, match="B1.*straddles"):
        broll.insert_segment(clip, at=4.0, insert=insert_seg(), words=transcript().words, transition_in="cut")


def test_insert_refuses_a_split_inside_a_word():
    with pytest.raises(ValueError, match="inside the word 'three'"):
        broll.insert_segment(make_clip(), at=2.5, insert=insert_seg(), words=transcript().words,
                             transition_in="cut")


def test_insert_at_an_existing_boundary_does_not_split():
    out = broll.insert_segment(make_clip(), at=10.0, insert=insert_seg(3.0), words=transcript().words,
                               transition_in="cut")
    assert [s.id for s in out.timeline] == ["S01", "I01", "S02"]
    assert out.timeline[2].output_in == 13.0
    assert check_1_contiguous(out) == [] and check_2_durations(out) == []


def test_shift_for_insert_is_identity_before_and_shifted_after():
    assert broll.shift_for_insert(3.9, at=4.0, dur=23.0) == 3.9
    assert broll.shift_for_insert(4.0, at=4.0, dur=23.0) == 27.0
    assert broll.shift_for_insert(9.0, at=4.0, dur=23.0) == 32.0


def test_remapped_words_skip_episode_words_for_an_insert_and_use_its_own():
    out = broll.insert_segment(make_clip(), at=4.0, insert=insert_seg(3.0), words=transcript().words,
                               transition_in="cut")
    insert_words = {"I01": [{"w": "That's", "start": 0.1, "end": 0.4}, {"w": "dog.", "start": 1.0, "end": 1.4}]}
    words = broll.remapped_words(out, transcript().words, insert_words)
    texts = [w["w"] for w in words]
    assert texts == ["One", "two", "three", "That's", "dog.", "four", "five.", "Six", "seven."]
    by = {w["w"]: w for w in words}
    assert by["That's"]["start"] == pytest.approx(4.1)
    assert by["four"]["start"] == pytest.approx(8.0)   # 105.0 - 104 + 7


# ---------------------------------------------------------------------------
# validate_clip invariant 13: overlays
# ---------------------------------------------------------------------------


def inv13(clip: Clip, idx: dict[str, MediaInfo] | None = None) -> list:
    return check_13_overlays(clip, index() if idx is None else idx)


def test_valid_overlays_pass():
    clip = make_clip(overlays=[
        pip("B1", 0.5, 4.0, label="Deutsch's picture of the problem"),
        lt("B1c", 1.5, 3.0),
        {"id": "B2", "mode": "fullscreen", "start": 4.0, "end": 11.0, "fade_out_frames": 6,
         "shots": [{"asset": "build.mp4", "src_in": 0.4, "src_out": 5.4},
                   {"asset": "hero.png", "at": 5.0, "zoom": [1.0, 1.05], "dissolve_frames": 0}]},
    ])
    assert inv13(clip) == []


def test_missing_asset_is_a_finding():
    clip = make_clip(overlays=[pip("B1", 1.0, 4.0, asset="nope.png")])
    found = inv13(clip)
    assert any("nope.png" in f.where and "exists" in f.expected for f in found)


def test_asset_without_provenance_is_a_finding():
    idx = index(**{"stock.jpg": MediaInfo(exists=True, duration=None, has_audio=False, provenance=None)})
    found = inv13(make_clip(overlays=[pip("B1", 1.0, 4.0, asset="stock.jpg")]), idx)
    assert any("provenance" in f.expected for f in found)


def test_overlay_outside_the_clip_is_a_finding():
    found = inv13(make_clip(overlays=[lt("B1", 14.0, 16.0)]))
    assert any(f.where == "B1" and "within" in f.expected for f in found)


def test_overlap_within_a_layer_is_a_finding_but_across_layers_is_fine():
    found = inv13(make_clip(overlays=[pip("B1", 1.0, 4.0), pip("B2", 3.5, 6.0), lt("B3", 1.0, 6.0)]))
    assert [f.where for f in found if "overlap" in f.expected] == ["B1/B2"]


def test_abutting_windows_in_one_layer_do_not_overlap():
    assert inv13(make_clip(overlays=[pip("B1", 1.0, 4.0), pip("B2", 4.0, 6.0)])) == []


def test_fullscreen_inside_the_protected_tail_is_a_finding():
    clip = make_clip(overlays=[{"id": "B9", "mode": "fullscreen", "start": 11.0, "end": 12.5,
                                "shots": [{"asset": "hero.png"}]}])
    found = inv13(clip)
    assert any(f.where == "B9" and "protected tail" in f.expected for f in found)


def test_video_range_beyond_the_file_is_a_finding():
    clip = make_clip(overlays=[{"id": "B2", "mode": "fullscreen", "start": 1.0, "end": 4.0,
                                "shots": [{"asset": "build.mp4", "src_in": 7.0, "src_out": 10.0}]}])
    assert any("build.mp4" in f.actual or "9.000" in f.expected for f in inv13(clip))


def test_short_video_range_without_hold_last_is_a_finding():
    clip = make_clip(overlays=[{"id": "B2", "mode": "fullscreen", "start": 1.0, "end": 6.0,
                                "shots": [{"asset": "build.mp4", "src_in": 0.0, "src_out": 2.0}]}])
    found = inv13(clip)
    assert any("hold_last" in f.expected for f in found)
    clip_ok = make_clip(overlays=[{"id": "B2", "mode": "fullscreen", "start": 1.0, "end": 6.0,
                                   "shots": [{"asset": "build.mp4", "src_in": 0.0, "src_out": 2.0,
                                              "hold_last": True}]}])
    assert inv13(clip_ok) == []


def test_pip_needs_a_box_and_text_needs_lines():
    clip = make_clip(overlays=[{"id": "B1", "mode": "pip", "start": 1.0, "end": 2.0, "shots": [{"asset": "hero.png"}]},
                               {"id": "B2", "mode": "card", "start": 1.0, "end": 2.0}])
    wheres = {f.where for f in inv13(clip)}
    assert {"B1", "B2"} <= wheres


def test_odd_box_dimensions_are_a_finding():
    # 4:2:0 video has no odd sizes: a 528x297 pip box made the grid canvas and the stills disagree
    # by a pixel and xfade refused them at render time (C1 v2, B15). The validator catches it first.
    clip = make_clip(overlays=[pip("B1", 1.0, 2.0, box={"x": 1352, "y": 660, "w": 528, "h": 297})])
    found = inv13(clip)
    assert any(f.where == "B1" and "even" in f.expected for f in found)
    moved = pip("B2", 1.0, 2.0, from_box={"x": 0, "y": 0, "w": 1919, "h": 1080}, move_frames=10)
    assert any(f.where == "B2" and "even" in f.expected for f in inv13(make_clip(overlays=[moved])))


def test_picture_overlay_over_an_insert_is_a_finding():
    clip = broll.insert_segment(make_clip(), at=4.0, insert=insert_seg(3.0), words=transcript().words,
                                transition_in="cut")
    clip.overlays = [Overlay.model_validate(pip("B1", 4.5, 6.0))]
    found = inv13(clip)
    assert any(f.where == "B1" and "insert" in f.expected for f in found)


def test_duplicate_overlay_ids_are_a_finding():
    found = inv13(make_clip(overlays=[lt("B1", 1.0, 2.0), lt("B1", 3.0, 4.0)]))
    assert any("unique" in f.expected for f in found)


# ---------------------------------------------------------------------------
# validate_clip invariant 12: inserts
# ---------------------------------------------------------------------------


def with_insert() -> Clip:
    return broll.insert_segment(make_clip(), at=4.0, insert=insert_seg(3.0), words=transcript().words,
                                transition_in="dip-6f")


INSERT_WORDS = {"I01": [{"w": "That's", "start": 0.1, "end": 0.4}, {"w": "not", "start": 0.5, "end": 0.6},
                        {"w": "a", "start": 0.6, "end": 0.7}, {"w": "dog.", "start": 1.0, "end": 1.4}]}


def test_valid_insert_passes():
    assert check_12_inserts(with_insert(), index(), INSERT_WORDS) == []


def test_insert_outside_broll_dir_is_a_finding():
    clip = with_insert()
    clip.timeline[1].source_file = "source/other.mp4"
    found = check_12_inserts(clip, index(), INSERT_WORDS)
    assert any("broll/" in f.expected for f in found)


def test_insert_without_audio_or_provenance_is_a_finding():
    idx = index()
    idx["talk_insert.mp4"] = MediaInfo(exists=True, duration=23.0, has_audio=False, provenance=None)
    found = check_12_inserts(with_insert(), idx, INSERT_WORDS)
    expected = " ".join(f.expected for f in found)
    assert "audio" in expected and "provenance" in expected


def test_insert_range_beyond_file_is_a_finding():
    idx = index()
    idx["talk_insert.mp4"] = MediaInfo(exists=True, duration=2.0, has_audio=True, provenance={"l": 1})
    assert any("2.000" in f.expected for f in check_12_inserts(with_insert(), idx, INSERT_WORDS))


def test_insert_dialogue_must_match_its_words_file():
    bad = {"I01": [{"w": "That's", "start": 0.1, "end": 0.4}, {"w": "a", "start": 0.6, "end": 0.7}]}
    found = check_12_inserts(with_insert(), index(), bad)
    assert any(f.where == "I01" and "words" in f.expected for f in found)


def test_insert_inside_the_protected_tail_is_a_finding():
    # tail is the last 3.0 s of an 18 s clip -> an insert ending after 15.0 is inside it
    base = make_clip()
    clip = broll.insert_segment(base, at=15.0, insert=insert_seg(3.0), words=transcript().words,
                                transition_in="cut")
    found = check_12_inserts(clip, index(), INSERT_WORDS)
    assert any("protected tail" in f.expected for f in found)


def test_insert_kind_and_block_must_agree():
    clip = with_insert()
    clip.timeline[1].insert = None
    assert any("insert block" in f.expected for f in check_12_inserts(clip, index(), INSERT_WORDS))


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))


# ---------------------------------------------------------------------------
# overlay_text: Card runs must be able to wrap inside the plate
# ---------------------------------------------------------------------------


def test_text_runs_are_split_per_word_so_long_lines_wrap():
    # A Card run is an unbreakable inline-block: a 90-character run overflowed the plate (C1 v2 credit).
    from overlay_text import text_layer
    from psmedia import load_config

    cfg = load_config().broll
    ov = Overlay.model_validate({
        "id": "C", "mode": "lowerthird", "start": 0.0, "end": 2.0,
        "lines": [{"runs": [{"text": "In conversation with David Deutsch: musing about statements"},
                            {"text": "unambiguously stated", "color": "accent", "underline_at": 1.0}]}],
    })
    runs = text_layer(ov, cfg, 1920, 1080, 30.0).props["elements"][0]["lines"][0]["runs"]
    assert all(r["text"] == " " or " " not in r["text"] for r in runs)
    words = [r["text"] for r in runs if r["text"] != " "]
    assert words == "In conversation with David Deutsch: musing about statements unambiguously stated".split()
    underlined = [r["text"] for r in runs if r["underline"] is not None]
    assert underlined == ["unambiguously", " ", "stated"]   # the rule spans its run, never past it


# ---------------------------------------------------------------------------
# splice_segments: prepend a lead-in of episode segments
# ---------------------------------------------------------------------------


def test_prepended_lead_in_shifts_timeline_overlays_and_inserts():
    clip = broll.insert_segment(make_clip(overlays=[lt("B1", 0.5, 2.0), pip("B2", 12.0, 14.0)]), at=10.0,
                                insert=insert_seg(3.0), words=transcript().words, transition_in="cut")
    lead = [TimelineSegment.model_validate(seg("S03", 50.0, 54.0, 0.0, 4.0, "Lead one.", speaker="host2")),
            TimelineSegment.model_validate(seg("S04", 60.0, 62.0, 0.0, 2.0, "Lead two."))]
    out = broll.splice_segments(clip, at=0.0, segments=lead, words=transcript().words, transition_in="cut")
    assert [s.id for s in out.timeline] == ["S03", "S04", "S01", "I01", "S02"]
    assert [(s.output_in, s.output_out) for s in out.timeline] == [
        (0.0, 4.0), (4.0, 6.0), (6.0, 16.0), (16.0, 19.0), (19.0, 24.0)]
    assert {o.id: (o.start, o.end) for o in out.overlays} == {"B1": (6.5, 8.0), "B2": (21.0, 23.0)}  # 12-14, +3 insert, +6 lead-in
    assert out.output.duration_s == 24.0


def test_splice_refuses_an_id_already_in_the_timeline():
    dup = TimelineSegment.model_validate(seg("S01", 50.0, 54.0, 0.0, 4.0, "Lead."))
    with pytest.raises(ValueError, match="S01"):
        broll.splice_segments(make_clip(), at=0.0, segments=[dup], words=transcript().words, transition_in="cut")


def test_removing_lead_in_segments_shifts_everything_back():
    clip = make_clip(overlays=[lt("B1", 11.0, 12.0)], timeline=[
        seg("S03", 50.0, 54.0, 0.0, 4.0, "Lead one.", speaker="host2"),
        seg("S04", 60.0, 62.0, 4.0, 6.0, "Lead two.", speaker="host2"),
        seg("S01", 100.0, 110.0, 6.0, 16.0, "One two three four five."),
        seg("S02", 110.0, 115.0, 16.0, 21.0, "Six seven.", speaker="host2"),
    ])
    out = broll.remove_segments(clip, ["S03", "S04"])
    assert [(s.id, s.output_in, s.output_out) for s in out.timeline] == [("S01", 0.0, 10.0), ("S02", 10.0, 15.0)]
    assert {o.id: (o.start, o.end) for o in out.overlays} == {"B1": (5.0, 6.0)}
    assert out.output.duration_s == 15.0


def test_removing_segments_refuses_an_overlay_over_them():
    clip = make_clip(overlays=[lt("B1", 1.0, 2.0)], timeline=[
        seg("S03", 50.0, 54.0, 0.0, 4.0, "Lead one.", speaker="host2"),
        seg("S01", 100.0, 110.0, 4.0, 14.0, "One two three four five."),
    ])
    with pytest.raises(ValueError, match="B1"):
        broll.remove_segments(clip, ["S03"])
