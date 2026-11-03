#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "platformdirs>=4", "pytest>=8", "pydantic>=2.9", "pyyaml>=6.0", "typer>=0.12", "loguru>=0.7", "rich>=13.7"]
# ///
"""episode.yaml show/layout_timeline + intro_overlays generation — run: `uv run --script scripts/test_intro_overlays.py`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from pydantic import ValidationError

from intro_overlays import build_intro_overlays
from pslib import Clip, Episode, ClipReview

SPEAKERS = [
    {"id": "host1", "name": "Eneasz", "full_name": "Eneasz Brodsky", "role": "co-host, Bayesian Conspiracy"},
    {"id": "host2", "name": "Steven", "full_name": "Steven Zuber", "role": "co-host, Bayesian Conspiracy"},
    {"id": "guest1", "name": "Vaden", "full_name": "Vaden Masrani", "role": "Increments Podcast"},
]
LAYOUT = [
    {"from_s": 0, "tiles": {"left": "host1", "mid": "guest1", "right": "host2"}},
    {"from_s": 2800, "tiles": {"left": "guest1", "mid": "host2", "right": "host1"}},
]


def episode(layout=LAYOUT, show=True) -> Episode:
    return Episode.model_validate({
        "episode": {"id": "e", "title": "t", "source_url": "u", "authorized": True, "created": "2026-11-02"},
        "platform_profiles": [], "speakers": SPEAKERS,
        "media": {"episode_video": "source/episode.mp4"},
        "transcript": {"json": "t.json", "md": "t.md", "engine": "assemblyai", "language": "en", "word_count": 1},
        "status": {"stage": "frozen"},
        "show": {"name": "The Bayesian Conspiracy", "hosts": ["Eneasz Brodsky", "Steven Zuber"],
                 "guest": "Vaden Masrani"} if show else None,
        "layout_timeline": layout,
    })


def seg(sid, src_in, out_in, dur, speaker) -> dict:
    return {
        "id": sid, "source_file": "source/episode.mp4", "source_in": src_in, "source_out": src_in + dur,
        "output_in": out_in, "output_out": out_in + dur, "dialogue": "x", "speaker": speaker, "audio": "as-recorded",
        "visual": {"kind": "aroll", "treatment": "source-frame"}, "transition": "cut",
    }


def clip(segs) -> Clip:
    return Clip.model_validate({
        "clip": {"id": "c", "pick": "C1", "format": "clip", "title": "t", "status": "frozen", "why": "w", "ends_on": "e"},
        "timeline": segs,
        "subtitles": {"font": "Inter Semibold", "base_color": "#FFFFFF", "emphasis_palette": ["#FFFFFF"],
                      "position_default": "bottom-center", "lines": []},
        "broll": {"protected_tail_s": 10.0},
        "output": {"aspect": "16:9", "resolution": "1920x1080", "fps": 30.0, "duration_s": segs[-1]["output_out"]},
        "render": {"versions": []},
    })


def test_card_and_tags_early_layout():
    c = clip([seg("S01", 2014.0, 0.0, 60.0, "host1"), seg("S02", 2074.0, 60.0, 30.0, "guest1")])
    ov = {o.id: o for o in build_intro_overlays(episode(), c, intro_s=5.0)}
    assert [r.text for ln in ov["T0"].lines for r in ln.runs] == [
        "THE BAYESIAN CONSPIRACY", "Eneasz Brodsky & Steven Zuber", "with Vaden Masrani"]
    assert ov["T0"].placement == "title-center" and ov["T0"].reveal == "words"
    assert (ov["T1"].start, ov["T1"].placement) == (5.3, "tile-left")        # Eneasz, early layout
    assert ov["T1"].lines[1].runs[0].text == "co-host, Bayesian Conspiracy"
    assert (ov["T3"].start, ov["T3"].placement) == (60.5, "tile-mid")        # Vaden at his first line, early layout
    assert (ov["T2"].start, ov["T2"].placement) == (9.6, "tile-right")       # Steven never speaks: tagged after Eneasz


def test_tile_follows_the_layout_change():
    c = clip([seg("S01", 3586.0, 0.0, 30.0, "guest1"), seg("S02", 3616.0, 30.0, 30.0, "host1")])
    tags = [o for o in build_intro_overlays(episode(), c, intro_s=0) if o.mode == "lowerthird"]
    assert [(t.lines[0].runs[0].text, t.placement) for t in tags] == [
        ("Vaden Masrani", "tile-left"), ("Steven Zuber", "tile-mid"), ("Eneasz Brodsky", "tile-right")]


def test_tags_never_overlap_in_the_text_layer():
    c = clip([seg("S01", 100.0, 0.0, 5.0, "host1"), seg("S02", 105.0, 5.0, 5.0, "host2"), seg("S03", 110.0, 10.0, 5.0, "guest1")])
    made = build_intro_overlays(episode(), c, intro_s=5.0)
    for a, b in zip(made, made[1:]):
        assert b.start >= a.end


def test_missing_layout_or_show_fails_loud():
    c = clip([seg("S01", 100.0, 0.0, 5.0, "host1")])
    with pytest.raises(ValueError, match="layout_timeline"):
        build_intro_overlays(episode(layout=[]), c, intro_s=5.0)
    with pytest.raises(ValueError, match="show:"):
        build_intro_overlays(episode(show=False), c, intro_s=5.0)


def test_own_show_has_no_with_line():
    ep = episode()
    ep.show.own_show = True
    ov = build_intro_overlays(ep, clip([seg("S01", 100.0, 0.0, 5.0, "host1")]), intro_s=5.0)[0]
    assert len(ov.lines) == 2


def test_existing_overlay_id_is_refused():
    c = clip([seg("S01", 100.0, 0.0, 5.0, "host1")])
    first = build_intro_overlays(episode(), c, intro_s=5.0)
    c.overlays = first
    with pytest.raises(ValueError, match="already has overlay id"):
        build_intro_overlays(episode(), c, intro_s=5.0)


@pytest.mark.parametrize("bad", [
    [{"from_s": 5, "tiles": {"left": "host1"}}],
    [{"from_s": 0, "tiles": {"left": "host1"}}, {"from_s": 0, "tiles": {"left": "host2"}}],
    [{"from_s": 0, "tiles": {"left": "nobody"}}],
])
def test_bad_layout_timeline_rejected(bad):
    with pytest.raises(ValidationError):
        episode(layout=bad)


def test_review_youtube_url_roundtrips():
    r = ClipReview.model_validate({"final_url": "d", "youtube_url": "https://youtu.be/x"})
    assert r.youtube_url == "https://youtu.be/x"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
