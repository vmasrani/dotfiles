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
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Tile invariant of the shorts framing — run: `uv run --script scripts/test_framing.py -q`.

A speaker's crop NEVER crosses their own tile. The source is a 1920x1080 Zoom-style gallery of three 640x1080
tiles; a 1080x960 split-screen panel inside one tile is at most 640x569 source px. The regression these tests pin:
the seam detector demanded a colour step on 90% of the face band, missed the seam between tiles whose backgrounds
match for a stretch, silently fell back to the whole frame as the tile, and cropped 1120px-wide panels that showed
the neighbouring speakers at both edges.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pytest

import facelib
import framer
from facelib import Face, FaceError, Sample, SpeakerTrack

W, H = 1920, 1080
TILES = {"left": (0, 0, 640, 1080), "middle": (640, 0, 1280, 1080), "right": (1280, 0, 1920, 1080)}
OUT_W, PANEL_H, MAX_UPSCALE = 1080, 960, 2.0


def gallery_frame(blend_rows: tuple[int, int] = (240, 330)) -> np.ndarray:
    """Three flat tiles. Inside `blend_rows` the middle tile matches its neighbours, so no seam shows there: the
    colour step spans ~85% of the middle speaker's face band, as in the real episode (0.59-0.95)."""
    gray = np.empty((H, W), np.float32)
    gray[:, :640], gray[:, 640:1280], gray[:, 1280:] = 90.0, 160.0, 90.0
    gray[blend_rows[0]:blend_rows[1], 640:1280] = 90.0
    return gray


def face(cx: float, y: float = 240.0, w: float = 400.0, h: float = 500.0, t: float = 0.0, bounds=None) -> Face:
    x = cx - w / 2
    eye = y + 0.4 * h
    lm = (x + 0.3 * w, eye, x + 0.7 * w, eye, x + 0.5 * w, y + 0.6 * h, x + 0.35 * w, y + 0.8 * h, x + 0.65 * w, y + 0.8 * h)
    return Face(t, x, y, w, h, 0.99, lm, (), bounds)


def inside(crop: tuple[int, int, int, int], tile: tuple[int, int, int, int]) -> bool:
    x, y, w, h = crop
    return tile[0] <= x and tile[1] <= y and x + w <= tile[2] and y + h <= tile[3]


def track_in(tile_name: str, gray: np.ndarray, **face_kwargs) -> SpeakerTrack:
    """Two seconds of one speaker, tile bounds measured from the frame with the pipeline's own seam detector."""
    l, _, r, _ = TILES[tile_name]
    cx = (l + r) / 2 + 20
    samples = []
    for k in range(13):
        f = face(cx, t=k / 6, **face_kwargs)
        samples.append(Sample(f.t, Face(f.t, f.x, f.y, f.w, f.h, f.score, f.lm, f.row, facelib._seam_bounds(gray, f))))
    return SpeakerTrack(0.0, 2.0, 6.0, samples)


def crops(shots) -> list[tuple[int, int, int, int]]:
    return [(x, y, s.w, s.h) for s in shots for _, x, y in s.keys]


def test_seam_found_despite_matching_stretch() -> None:
    left, _, right, _ = facelib._seam_bounds(gray=gallery_frame(), f=face(660 + 20 + 320))
    assert 638 <= left <= 642 and 1278 <= right <= 1282, f"middle tile measured ({left}, {right}), real tile is (640, 1280)"


@pytest.mark.parametrize("tile_name", ["left", "middle", "right"])
def test_panel_crop_is_clamped_inside_the_speakers_tile(tile_name: str) -> None:
    track = track_in(tile_name, gallery_frame())
    # a 400px face wants a 2.8 x 400 = 1120px-wide panel crop: wider than the 640px tile it lives in
    shots = facelib.plan_shots(track, (W, H), OUT_W, PANEL_H, "panel", MAX_UPSCALE, "test")
    tile = TILES[tile_name]
    for crop in crops(shots):
        assert inside(crop, tile), f"{tile_name}: crop {crop} leaves tile {tile}"
        assert crop[2] <= tile[2] - tile[0]
    for shot in shots:
        assert shot.tile is not None and inside((shot.tile[0], shot.tile[1], shot.tile[2] - shot.tile[0], shot.tile[3] - shot.tile[1]), tile)
        assert shot.scale <= MAX_UPSCALE + 1e-6


def test_panel_that_would_exceed_max_upscale_is_blur_filled_inside_the_tile() -> None:
    gray = np.full((H, W), 90.0, np.float32)
    gray[:, :400] = 160.0          # a 400px-wide tile: a full-width 1080px panel would be magnified 2.7x
    samples = []
    for k in range(13):
        f = face(200.0, t=k / 6, w=48.0, h=60.0, y=300.0)
        samples.append(Sample(f.t, Face(f.t, f.x, f.y, f.w, f.h, f.score, f.lm, f.row, facelib._seam_bounds(gray, f))))
    shots = facelib.plan_shots(SpeakerTrack(0.0, 2.0, 6.0, samples), (W, H), OUT_W, PANEL_H, "panel", MAX_UPSCALE, "test")
    for shot in shots:
        assert shot.blur_fill and shot.scale <= MAX_UPSCALE + 1e-6
        assert all(inside(c, (0, 0, 400, 1080)) for c in crops([shot]))
        dx, dy, ow, oh = shot.dst
        assert 0 <= dx and dx + ow <= OUT_W and 0 <= dy and dy + oh <= PANEL_H


def middle_track(**face_kwargs) -> SpeakerTrack:
    """The middle speaker over two seconds, tile (640,0)-(1280,1080) as the seam detector measures it on the real episode."""
    samples = [Sample(k / 6, face(980.0, t=k / 6, bounds=(641.0, 0.0, 1278.0, 1080.0), **face_kwargs)) for k in range(13)]
    return SpeakerTrack(0.0, 2.0, 6.0, samples)


def test_panel_zooms_out_to_head_and_shoulders_when_the_tile_is_tall_enough() -> None:
    # a 220x300 face in a 640x1080 tile: the 30% rule wants a 1000px-tall crop, which is tile-wide (640) rather than 1125 wide
    shot = facelib.plan_shots(middle_track(w=220.0, h=300.0, y=300.0), (W, H), OUT_W, PANEL_H, "panel", MAX_UPSCALE, "test")[0]
    assert 0.27 <= shot.face_frac <= 0.33, f"face is {shot.face_frac:.0%} of the panel, the rule is 30%"
    assert shot.h >= 950 and shot.w <= 640 and shot.blur_fill, "tile-wide, tall crop with blurred side gaps"
    assert shot.dst[1] == 0 and shot.dst[3] == PANEL_H, "fit to the panel by height"
    assert inside((shot.keys[0][1], shot.keys[0][2], shot.w, shot.h), TILES["middle"])


def test_panel_with_a_tile_filling_face_shows_the_whole_tile_height_with_head_room() -> None:
    shot = facelib.plan_shots(middle_track(), (W, H), OUT_W, PANEL_H, "panel", MAX_UPSCALE, "test")[0]
    old_face_frac = 500 * (OUT_W / 560 / 1.125) / PANEL_H     # the previous 2.8-face-widths crop magnified a 500px face ~1.7x
    assert shot.h == 1080 and shot.blur_fill
    assert shot.face_frac < 0.5 < old_face_frac, f"face {shot.face_frac:.0%} of the panel (was ~{old_face_frac:.0%})"
    assert shot.keys[0][2] + 0.2 * 500 <= 240, "the crop starts well above the face box (head room)"


def test_closeup_crop_stays_inside_the_tile() -> None:
    track = track_in("middle", gallery_frame())
    shots = facelib.plan_shots(track, (W, H), OUT_W, 1920, "closeup", MAX_UPSCALE, "test")
    for shot in shots:
        assert shot.blur_fill, "a 9:16 window is wider than a 640px tile at this face size, so the shot must be blur-filled"
        assert all(inside(c, TILES["middle"]) for c in crops([shot]))


def test_seam_less_tile_holding_a_neighbour_is_refused() -> None:
    flat = np.full((H, W), 128.0, np.float32)      # no seam anywhere: the "tile" would be the whole frame
    speaker, neighbour = face(300.0), face(980.0)
    with pytest.raises(FaceError, match="no tile seam was found"):
        facelib.tile_bounds(flat, speaker, [speaker, neighbour], "test")


def test_single_person_frame_without_seams_is_the_whole_frame() -> None:
    flat = np.full((H, W), 128.0, np.float32)
    speaker = face(960.0)
    assert facelib.tile_bounds(flat, speaker, [speaker], "test") == (0.0, 0.0, float(W), float(H))


def test_face_box_overhanging_the_seam_still_finds_its_tile() -> None:
    # the detector's box of a speaker leaning toward the left tile starts 8px before the seam at x=640
    left, _, right, _ = facelib._seam_bounds(gallery_frame(), Face(0.0, 632.0, 240.0, 400.0, 480.0, 0.9, face(840.0).lm, (), None))
    assert 638 <= left <= 642 and 1278 <= right <= 1282


def test_small_stray_detection_in_the_tile_is_not_a_neighbour() -> None:
    gray = gallery_frame()
    speaker = face(960.0)
    hand = face(800.0, y=600.0, w=198.0, h=164.0)       # a low-confidence box on a hand: under half the speaker's face height
    assert facelib.tile_bounds(gray, speaker, [speaker, hand], "test")[0] > 600


def test_second_box_on_the_speakers_own_face_is_not_a_neighbour() -> None:
    gray = gallery_frame()
    speaker = face(1000.0)                                   # x 800-1200, y 240-740
    on_beard = face(1000.0, y=524.0, w=252.0, h=252.0)       # half the face height, centred inside the speaker's box
    assert facelib.tile_bounds(gray, speaker, [speaker, on_beard], "test")[0] > 600


def test_crop_leaving_the_tile_is_refused_by_the_shot_check() -> None:
    f = face(960.0, bounds=(640.0, 0.0, 1280.0, 1080.0))
    shot = facelib.Shot(0.0, 1.0, 1000, 889, [(0.0, 460, 100)], scale=1.08)
    with pytest.raises(FaceError, match="leaves the speaker's tile"):
        facelib._finish(shot, [f], 1920, (640, 0, 1280, 1080), "test")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))


@pytest.mark.parametrize("face_cx", [860.0, 960.0, 1060.0])
def test_closeup_sharp_rect_is_horizontally_centred_over_the_backdrop(face_cx: float) -> None:
    # a face near either edge of its tile pushes the 9:16 window past the tile, so the sharp crop is clipped on one side;
    # the clipped crop must still sit in the middle of the frame (equal blurred margins left and right)
    samples = [Sample(k / 6, face(face_cx, t=k / 6, bounds=(641.0, 0.0, 1278.0, 1080.0))) for k in range(13)]
    shots = facelib.plan_shots(SpeakerTrack(0.0, 2.0, 6.0, samples), (W, H), OUT_W, 1920, "closeup", MAX_UPSCALE, "test")
    for shot in shots:
        dx, _, ow, _ = shot.dst
        assert ow < OUT_W, "the sharp crop is narrower than the frame, so margins exist"
        assert dx == (OUT_W - ow) // 2, f"left margin {dx}, right margin {OUT_W - ow - dx}"


@pytest.mark.parametrize("face_cx", [860.0, 960.0, 1060.0])
def test_panel_sharp_rect_is_horizontally_centred_over_the_backdrop(face_cx: float) -> None:
    samples = [Sample(k / 6, face(face_cx, t=k / 6, w=220.0, h=300.0, y=300.0, bounds=(641.0, 0.0, 1278.0, 1080.0))) for k in range(13)]
    shot = facelib.plan_shots(SpeakerTrack(0.0, 2.0, 6.0, samples), (W, H), OUT_W, PANEL_H, "panel", MAX_UPSCALE, "test")[0]
    dx, _, ow, _ = shot.dst
    assert dx == (OUT_W - ow) // 2, f"left margin {dx}, right margin {OUT_W - ow - dx}"


def test_wordless_segment_keeps_its_existing_treatment() -> None:
    """A segment with no transcript words (muted / as-recorded) must pass through rebuild_timeline untouched."""
    from types import SimpleNamespace

    import plan_framing
    from cliplib import OutWord

    def seg(sid, a, b, dialogue, visual):
        return {"id": sid, "source_in": a, "source_out": b, "output_in": a, "output_out": b, "dialogue": dialogue, "speaker": "A", "visual": visual}

    wordless = seg("S01", 0.0, 2.0, "", {"kind": "aroll", "treatment": "as-recorded", "locked": False})
    spoken = seg("S02", 2.0, 4.0, "hello there", {"kind": "aroll", "treatment": "x", "locked": False})
    words = [OutWord(0, 1, "hello", "A", 2.0, 2.5, 2.0, 2.5), OutWord(1, 1, "there", "A", 2.5, 3.0, 2.5, 3.0)]
    lab = plan_framing.Label("closeup-A")
    plan = plan_framing.Plan(ctx=SimpleNamespace(clip={"timeline": [wordless, spoken]}), cfg=None, words=words, spk=["A", "A"], locked=[False, False],
                             label=[lab, lab], reason=["r", "r"], duration=4.0, fps=30.0, transcript=[])
    out = plan_framing.rebuild_timeline(plan)
    assert out[0] == wordless
    assert out[1]["visual"]["treatment"] == "closeup-A"
