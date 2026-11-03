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
"""Quote layout of a short — run: `uv run --script scripts/test_quote_layout.py -q`.

While a fullscreen picture overlay is on, the frame is a split: the screenshot on a 1080x960 top panel, the CURRENT
speaker (whoever the timeline segment says) on a 1080x960 bottom panel cropped inside their own tile. Captions go
on the top of the bottom panel / the seam and never over the screenshot or a mouth.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

import capplace
import quotelayout
import test_framing as tf
import validate_subtitles
from pslib import Clip

FPS = 30.0


def aroll(sid: str, out_in: float, out_out: float, speaker: str, treatment: str = "closeup-host1") -> dict:
    return {
        "id": sid, "source_file": "source/episode.mp4", "source_in": 100.0 + out_in, "source_out": 100.0 + out_out,
        "output_in": out_in, "output_out": out_out, "dialogue": "words words", "speaker": speaker, "audio": "as-recorded",
        "visual": {"kind": "aroll", "treatment": treatment, "speakers": ["host1", "guest1"] if treatment == "splitscreen" else None,
                   "locked": False, "reason": None, "asset_id": None, "motion": None, "crop": None},
        "transition": "cut",
    }


def shot(asset: str, at: float, **kw) -> dict:
    return {"asset": asset, "at": at, "zoom": [1.0, 1.02], **kw}


def overlay(oid: str = "B1", start: float = 4.0, end: float = 16.0, **kw) -> dict:
    base = {"id": oid, "mode": "fullscreen", "start": start, "end": end, "fade_in_frames": 8, "fade_out_frames": 10,
            "shots": [shot("a.png", 0.0), shot("b.png", 6.0, dissolve_frames=6)]}
    return base | kw


def short_clip(overlays: list[dict] | None = None) -> Clip:
    timeline = [
        aroll("S01", 0.0, 6.0, "host1", "closeup-host1"),
        aroll("S02", 6.0, 10.0, "guest1", "splitscreen"),
        aroll("S03", 10.0, 14.0, "host1", "closeup-guest1"),      # host1 speaks over guest1's reaction shot
        aroll("S04", 14.0, 20.0, "guest1", "closeup-guest1"),
    ]
    return Clip.model_validate({
        "clip": {"id": "q1", "pick": "P1", "format": "short", "title": "t", "status": "frozen", "why": "w", "ends_on": "x"},
        "timeline": timeline,
        "subtitles": {"font": "Inter Semibold", "base_color": "#FFFFFF", "emphasis_palette": ["#FFD34D"],
                      "position_default": "bottom-center", "lines": []},
        "broll": {"provenance": "broll/provenance.json", "protected_tail_s": 3.0},
        "overlays": [overlay()] if overlays is None else overlays,
        "output": {"aspect": "9:16", "resolution": "1080x1920", "fps": FPS, "duration_s": 20.0},
        "render": {"versions": []},
    })


# --- the screenshot panel ------------------------------------------------------------------------------------------


@pytest.mark.parametrize("dims", [(1912, 870), (1696, 624), (2000, 569), (2000, 78), (1666, 1486), (872, 684), (600, 1400)])
def test_screenshot_fits_the_panel_inside_the_margin_even_at_full_push_in(dims: tuple[int, int]) -> None:
    x, y, w, h = quotelayout.fit_rect(*dims, 1080, 960)
    m = quotelayout.QUOTE_MARGIN_PX
    assert x >= m and y >= m - 1 and x + w <= 1080 - m and y + h <= 960 - m + 1, (x, y, w, h)
    assert abs(w * dims[1] - h * dims[0]) <= dims[0] + dims[1], "the screenshot must not be stretched"
    assert abs((x + w / 2) - 540) <= 1 and abs((y + h / 2) - 480) <= 1, "centred on the panel"
    zx, zy, zw, zh = quotelayout.zoomed_rect((x, y, w, h), 1.02)
    assert zx >= 0 and zy >= 0 and zx + zw <= 1080 and zy + zh <= 960, "the push-in stays inside the panel"


def test_a_wide_screenshot_is_fitted_to_the_panel_width() -> None:
    _, _, w, _ = quotelayout.fit_rect(1912, 870, 1080, 960)
    assert w == 1080 - 2 * quotelayout.QUOTE_MARGIN_PX


# --- what a short can show -----------------------------------------------------------------------------------------


@pytest.mark.parametrize("patch", [
    {"mode": "pip", "box": {"x": 0, "y": 0, "w": 400, "h": 300}},
    {"mode": "lowerthird", "shots": [], "lines": [{"runs": [{"text": "hi"}]}]},
    {"mode": "card", "shots": [], "lines": [{"runs": [{"text": "hi"}]}]},
    {"label": "caption"},
    {"shots": [shot("clip.mp4", 0.0, src_in=0.0, src_out=3.0)]},
    {"shots": [{"grid": {"cols": 1, "rows": 1, "tiles": [{"asset": "a.png"}]}, "at": 0.0}]},
    {"shots": [shot("a.png", 0.0, crop="x=0:y=0:w=10:h=10")]},
])
def test_unsupported_overlays_refuse_loudly(patch: dict) -> None:
    clip = short_clip([overlay(**patch)])
    with pytest.raises(NotImplementedError, match="not implemented for shorts"):
        quotelayout.quote_overlays(clip)
    assert quotelayout.unsupported(clip.overlays[0])


def test_a_still_fullscreen_overlay_is_supported() -> None:
    clip = short_clip()
    assert [ov.id for ov in quotelayout.quote_overlays(clip)] == ["B1"]


# --- the speaker below ---------------------------------------------------------------------------------------------


def test_the_bottom_panel_shows_whoever_the_segment_says_speaks() -> None:
    clip = short_clip()
    slices = quotelayout.quote_slices(clip, clip.overlays[0])
    assert [(s.id, s.speaker, round(t0, 3), round(t1, 3)) for s, t0, t1 in slices] == [
        ("S01", "host1", 4.0, 6.0), ("S02", "guest1", 6.0, 10.0), ("S03", "host1", 10.0, 14.0), ("S04", "guest1", 14.0, 16.0)]


def test_a_speaker_outside_the_splitscreen_pair_is_refused() -> None:
    clip = short_clip()
    clip.timeline[1].speaker = "host3"
    with pytest.raises(ValueError, match="S02.*host3"):
        quotelayout.quote_slices(clip, clip.overlays[0])


@pytest.mark.parametrize("tile_name", ["left", "middle", "right"])
def test_bottom_panel_crop_stays_inside_the_speakers_tile(tile_name: str) -> None:
    track = tf.track_in(tile_name, tf.gallery_frame())
    shots = quotelayout.speaker_panel_shots(track, (tf.W, tf.H), 1080, 960, tf.MAX_UPSCALE, "test")
    tile = tf.TILES[tile_name]
    assert shots
    for crop in tf.crops(shots):
        assert tf.inside(crop, tile), f"{tile_name}: crop {crop} leaves tile {tile}"
    assert all(s.dst is None or (s.dst[2] <= 1080 and s.dst[3] <= 960) for s in shots)


def test_a_bottom_panel_crop_that_leaves_the_tile_is_refused() -> None:
    track = tf.track_in("middle", tf.gallery_frame())
    shots = quotelayout.speaker_panel_shots(track, (tf.W, tf.H), 1080, 960, tf.MAX_UPSCALE, "test")
    shots[0].keys[0] = (shots[0].keys[0][0], 100, shots[0].keys[0][2])        # x=100: inside the left tile
    with pytest.raises(ValueError, match="leaves the speaker's tile"):
        quotelayout.check_inside_tile(shots, "S01 quote")


# --- the layout runs the captions follow ---------------------------------------------------------------------------


def test_layout_runs_switch_to_quote_on_the_overlay_frames() -> None:
    clip = short_clip()
    runs = capplace.layout_runs(clip, 2.0, 18.0, FPS)
    assert [(r.layout, round(r.t0 * FPS), round(r.t1 * FPS)) for r in runs] == [
        ("solo", 60, 120), ("quote", 120, 480), ("solo", 480, 540)]


def test_layout_key_changes_with_the_overlay_window() -> None:
    a, b = short_clip(), short_clip([overlay(start=5.0)])
    assert capplace.layout_key(a) != capplace.layout_key(b)
    assert capplace.layout_key(short_clip([])) == capplace.layout_key(short_clip([]))


# --- mouths and screenshots on the framing -------------------------------------------------------------------------


def write_framing(tmp_path: Path, clip: Clip) -> None:
    def panel(slot: str, y: float, mouth: list[float], t0: float, t1: float) -> dict:
        return {"slot": slot, "shots": [{"t0": t0, "t1": t1, "mouth": mouth}]}
    segments = {
        "S01": {"treatment": "closeup-host1", "panels": [panel("full", 0, [1200.0, 1300.0], 0.0, 6.0)],
                "quote": panel("bottom", 960, [1500.0, 1600.0], 0.0, 6.0) | {"speaker": "host1"}},
        "S04": {"treatment": "closeup-guest1", "panels": [panel("full", 0, [1200.0, 1300.0], 14.0, 20.0)],
                "quote": panel("bottom", 960, [1500.0, 1600.0], 14.0, 20.0) | {"speaker": "guest1"}},
    }
    quotes = [{"id": "B1", "start": 4.0, "end": 16.0, "rect": [0, 960 - 960, 1080, 960], "shots": [
        {"t0": 4.0, "t1": 10.0, "dst": [40, 40, 1000, 455], "zoom": [1.0, 1.02]},
        {"t0": 10.0, "t1": 16.0, "dst": [40, 40, 1000, 880], "zoom": [1.0, 1.02]}]}]
    capplace.write_framing(tmp_path, clip, 1920, segments, quotes)


def test_mouth_zones_follow_what_is_on_screen(tmp_path: Path) -> None:
    clip = short_clip()
    write_framing(tmp_path, clip)
    zones = capplace.load_zones(tmp_path, clip, 1920)
    solo = [(z.who, z.t0, z.t1) for z in zones if z.who.endswith("-full")]
    quote = [(z.who, z.t0, z.t1) for z in zones if z.who.endswith("-quote")]
    assert solo == [("S01-full", 0.0, 4.0), ("S04-full", 16.0, 20.0)], "no hidden closeup mouth inside the overlay window"
    assert quote == [("S01-quote", 4.0, 6.0), ("S04-quote", 14.0, 16.0)], "the bottom-panel mouth only while the overlay is up"
    assert all(z.top == 1500.0 for z in zones if z.who.endswith("-quote"))


def test_screenshot_keepouts_cover_each_shot_with_its_push_in(tmp_path: Path) -> None:
    clip = short_clip()
    write_framing(tmp_path, clip)
    keep = capplace.load_keepouts(tmp_path, clip, 1920)
    assert [(k.t0, k.t1) for k in keep] == [(4.0, 10.0), (10.0, 16.0)]
    assert keep[1].bottom >= 40 + 880 and keep[1].bottom <= 960, "the tall screenshot reaches the seam; the push-in is included"
    assert keep[0].bottom < 600


def test_stale_framing_for_another_overlay_window_is_refused(tmp_path: Path) -> None:
    write_framing(tmp_path, short_clip())
    with pytest.raises(ValueError, match="different timeline"):
        capplace.load_zones(tmp_path, short_clip([overlay(start=5.0)]), 1920)


# --- captions -------------------------------------------------------------------------------------------------------


def place(keepouts: list[capplace.Zone], mouths: list[capplace.Zone], lines: int = 2) -> capplace.Placement:
    return capplace.choose_position(4.0, 6.0, lines, 56.0, 1080, 1920, mouths, 320.0, 1.0, 200.0, 1600.0,
                                    keepouts=keepouts, top_first=True)


def test_quote_captions_sit_under_the_seam_clear_of_the_screenshot() -> None:
    shot_zone = capplace.Zone(4.0, 6.0, 40.0, 520.0, "B1 screenshot")
    p = place([shot_zone], [])
    assert p.name == "panel-top" and p.top >= 960 and p.top > shot_zone.bottom + capplace.MOUTH_MARGIN_PX


def test_a_tall_screenshot_pushes_the_caption_off_the_seam() -> None:
    tall = capplace.Zone(4.0, 6.0, 40.0, 940.0, "B1 screenshot")
    p = place([tall], [])
    assert not capplace.hits(p.top, p.bottom, 4.0, 6.0, [tall]) and p.top >= 940


def test_a_caption_never_covers_the_bottom_panel_mouth() -> None:
    mouth = capplace.Zone(4.0, 6.0, 1000.0, 1120.0, "S01-quote")
    p = place([capplace.Zone(4.0, 6.0, 40.0, 520.0, "B1 screenshot")], [mouth])
    assert capplace.exposure(p.top, p.bottom, 4.0, 6.0, [mouth])[0] == 0.0


def test_no_position_clear_of_screenshot_and_mouth_raises() -> None:
    zones = [capplace.Zone(4.0, 6.0, 40.0, 1500.0, "B1 screenshot")]
    with pytest.raises(ValueError, match="screenshot"):
        place(zones, [])


def test_validator_flags_a_caption_over_the_screenshot() -> None:
    keep = [capplace.Zone(4.0, 6.0, 40.0, 940.0, "B1 screenshot")]
    run = {"layout": "quote", "t0": 4.0, "t1": 6.0, "placement": "seam", "top": 880.0, "bottom": 1040.0}
    findings = validate_subtitles.quote_clearance("event 1", run, keep)
    assert [f.check for f in findings] == ["quote_clearance"]
    ok = run | {"placement": "panel-top", "top": 972.0, "bottom": 1132.0}
    assert validate_subtitles.quote_clearance("event 1", ok, keep) == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
