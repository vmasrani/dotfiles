"""The quote layout of a short: a picture overlay (a blog-post screenshot) over the top half, the current speaker below.

Not executable (pure stdlib + pslib + facelib). While a fullscreen picture overlay is on in a short, the 1080x1920 frame
is two 1080x960 panels:

* TOP — the screenshot, fitted inside the panel with a margin on a blurred, darkened copy of itself (drawn by
  remotion/src/Short.tsx; the fit rectangles are decided HERE and written to `assets/framing.json`, never in TypeScript);
* BOTTOM — the speaker of the timeline segment on screen (`segment.speaker`, not the cutaway treatment), framed exactly
  like a split-screen panel: `facelib.plan_shots(..., "panel", ...)`, so the crop stays inside that speaker's tile.

The overlay is the existing clip.yaml `overlays:` entry (schemas.md § Overlays), timed in OUTPUT seconds. Everything a
short cannot draw yet — pip, text modes, video, grids, crops, labels — is refused with "not implemented for shorts".
"""

from __future__ import annotations

from pslib import Clip, Overlay, TimelineSegment
from psmedia import even

QUOTE_MARGIN_PX = 40       # air between the screenshot and the edge of its panel
QUOTE_PANEL_KIND = "panel"
STILL_EXTS = (".png", ".jpg", ".jpeg", ".webp")


def unsupported(ov: Overlay) -> list[str]:
    """Why `ov` cannot be drawn in a short (empty = it can)."""
    if ov.mode != "fullscreen":
        return [f"mode {ov.mode!r} (only fullscreen picture overlays)"]
    out: list[str] = []
    if ov.lines or ov.box is not None or ov.from_box is not None:
        out.append("text lines / box / from_box")
    if ov.label is not None:
        out.append("label")
    if not ov.shots:
        out.append("no shots")
    for k, shot in enumerate(ov.shots, start=1):
        where = f"shot {k}"
        if shot.grid is not None:
            out.append(f"{where}: a grid")
        elif shot.asset is None or not shot.asset.lower().endswith(STILL_EXTS):
            out.append(f"{where}: {shot.asset!r} is not a still image (png/jpg/webp)")
        if shot.crop is not None:
            out.append(f"{where}: crop")
        if shot.src_in is not None or shot.src_out is not None or shot.speed != 1.0 or shot.hold_last:
            out.append(f"{where}: video range")
    return out


def quote_overlays(clip: Clip) -> list[Overlay]:
    """The overlays of a short, refusing anything the quote layout cannot draw."""
    for ov in clip.overlays:
        reasons = unsupported(ov)
        if reasons:
            raise NotImplementedError(f"overlay {ov.id}: not implemented for shorts — " + "; ".join(reasons))
    return list(clip.overlays)


def fit_rect(img_w: int, img_h: int, panel_w: int, panel_h: int, margin: int = QUOTE_MARGIN_PX) -> tuple[int, int, int, int]:
    """Where the screenshot is drawn (x, y, w, h) inside a panel: the largest copy that fits inside the margin, centred."""
    scale = min((panel_w - 2 * margin) / img_w, (panel_h - 2 * margin) / img_h)
    w, h = even(round(img_w * scale)), even(round(img_h * scale))
    return (panel_w - w) // 2, (panel_h - h) // 2, w, h


def zoomed_rect(rect: tuple[float, float, float, float], zoom: float) -> tuple[float, float, float, float]:
    """`rect` scaled by `zoom` about its centre (the push-in)."""
    x, y, w, h = rect
    return x + w / 2 - w * zoom / 2, y + h / 2 - h * zoom / 2, w * zoom, h * zoom


def quote_slices(clip: Clip, ov: Overlay) -> list[tuple[TimelineSegment, float, float]]:
    """(segment, t0, t1): every A-roll segment the overlay covers, with the part of it inside the window.

    The bottom panel shows `segment.speaker`; a split screen's speaker must be one of its two."""
    out: list[tuple[TimelineSegment, float, float]] = []
    for seg in clip.timeline:
        t0, t1 = max(ov.start, seg.output_in), min(ov.end, seg.output_out)
        if seg.visual.kind != "aroll" or t1 - t0 <= 1e-6:
            continue
        if seg.visual.treatment == "splitscreen" and seg.speaker not in (seg.visual.speakers or []):
            raise ValueError(f"{seg.id}: speaker {seg.speaker!r} is not on the split screen {seg.visual.speakers} — "
                             f"the quote layout shows the speaker below the screenshot")
        out.append((seg, t0, t1))
    if not out or abs(out[0][1] - ov.start) > 1e-3 or abs(out[-1][2] - ov.end) > 1e-3 or any(
            abs(a[2] - b[1]) > 1e-3 for a, b in zip(out, out[1:])):
        raise ValueError(f"overlay {ov.id} {ov.start:.2f}-{ov.end:.2f}s is not covered contiguously by A-roll segments")
    return out


def shot_slots(ov: Overlay) -> list[tuple[float, float, object]]:
    """(t0, t1, shot) in OUTPUT seconds: a shot lasts until the next one starts (the last one until the window ends)."""
    return [(ov.start + shot.at, ov.start + (ov.shots[k + 1].at if k + 1 < len(ov.shots) else ov.duration), shot)
            for k, shot in enumerate(ov.shots)]


def quote_record(ov: Overlay, dims: dict[str, tuple[int, int]], out_w: int, panel_h: int, blur_px: float, brightness: float) -> dict:
    """One overlay as it goes into framing.json: the top panel, its backdrop and every screenshot's fit rectangle."""
    return {
        "id": ov.id, "start": ov.start, "end": ov.end,
        "fade_in_frames": ov.fade_in_frames, "fade_out_frames": ov.fade_out_frames,
        "rect": [0, 0, out_w, panel_h],
        "backdrop": {"blur_px": blur_px, "brightness": brightness},
        "shots": [{
            "t0": round(t0, 4), "t1": round(t1, 4), "asset": shot.asset, "src_dims": list(dims[shot.asset]),
            "dst": list(fit_rect(*dims[shot.asset], out_w, panel_h)), "zoom": list(shot.zoom or [1.0, 1.0]),
            "dissolve_frames": shot.dissolve_frames,
        } for t0, t1, shot in shot_slots(ov)],
    }


def speaker_panel_shots(track, dims: tuple[int, int], out_w: int, panel_h: int, max_upscale: float, where: str):
    """Crop shots for the bottom panel: a split-screen panel crop, bounded by the speaker's tile."""
    import facelib

    shots = facelib.plan_shots(track, dims, out_w, panel_h, QUOTE_PANEL_KIND, max_upscale, where)
    check_inside_tile(shots, where)
    return shots


def check_inside_tile(shots, where: str) -> None:
    """The tile invariant, asserted again on the quote panel: no crop key may leave its shot's tile."""
    for shot in shots:
        if shot.tile is None:
            continue
        l, t, r, b = shot.tile
        for _, x, y in shot.keys:
            if x < l - 0.51 or y < t - 0.51 or x + shot.w > r + 0.51 or y + shot.h > b + 0.51:
                raise ValueError(f"{where}: crop {shot.w}x{shot.h}@({x},{y}) leaves the speaker's tile {tuple(shot.tile)} — "
                                 f"it would show a neighbouring speaker")
