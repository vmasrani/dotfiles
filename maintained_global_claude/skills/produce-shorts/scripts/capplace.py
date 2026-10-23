"""Where captions may sit so they never cover a mouth — shared by extract_segments, align_subtitles and validate_subtitles.

Not executable (pure stdlib + pslib). `extract_segments.py` measures, per cut, the vertical band between each
speaker's nose and chin in output-frame pixels and writes it to `assets/aroll/layout.json`
(`write_layout`). Captions are placed per treatment:

* solo (closeup, b-roll): the style's bottom-centre;
* split screen: the caption must leave BOTH faces' mouths clear, so it goes on the panel seam
  (centred on the 960px boundary) or, if a mouth reaches the seam, at the top of the bottom panel.
  `choose_position` picks the first that clears every mouth zone measured while the caption is on screen
  (TOLERATE_FRACTION of the stretch, at most TOLERATE_MAX_S, of contact is allowed) and raises when none does.

Position follows the layout frame by frame: a card that spans a layout change is NOT split (that would break
its reading-speed budget); it gets one position per `layout_runs` stretch, written to the `.placements.json`
sidecar of the .ass, and the renderer switches position on exactly the frame the layout switches.

The layout carries `key` = a fingerprint of the clip's A-roll timeline; `load_zones` refuses a layout measured for a
different timeline ("run extract_segments.py first") instead of placing captions from stale faces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pslib import Clip

LAYOUT_PATH = Path("assets") / "aroll" / "layout.json"
MOUTH_MARGIN_PX = 16.0      # air kept between a caption band and a mouth zone
PANEL_TOP_PAD_PX = 12.0     # gap between the seam and a caption set at the top of the bottom panel
TOLERATE_FRACTION = 0.25    # a card straddling a cut may brush a mouth for this share of its life ...
TOLERATE_MAX_S = 0.6        # ... and never longer than this
LINE_HEIGHT_EM = 1.2        # matches remotion/gen-props.mjs lineHeightEm and validate_subtitles.LINE_HEIGHT_FACTOR


@dataclass(frozen=True)
class Zone:
    """The nose-to-chin band [top, bottom] (output px) of one speaker while clip time is in [t0, t1)."""

    t0: float
    t1: float
    top: float
    bottom: float
    who: str


@dataclass(frozen=True)
class Placement:
    name: str                 # "bottom" | "seam" | "panel-top" | "gap"
    ass_tags: str             # override block for the event text
    top: float                # resulting band, output px
    bottom: float


def layout_key(clip: Clip) -> str:
    rows = [(s.id, s.visual.treatment, s.visual.speakers, s.visual.crop, round(s.source_in, 4), round(s.source_out, 4),
             round(s.output_in, 4), round(s.output_out, 4)) for s in clip.timeline if s.visual.kind == "aroll"]
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()[:16]


def write_layout(clip_dir: Path, clip: Clip, frame_h: int, files: dict[str, dict]) -> Path:
    path = clip_dir / LAYOUT_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": layout_key(clip), "frame_h": frame_h, "files": files}, indent=1))
    return path


def load_zones(clip_dir: Path, clip: Clip, frame_h: int) -> list[Zone]:
    path = clip_dir / LAYOUT_PATH
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing — run scripts/extract_segments.py before aligning captions "
                                f"(it measures where each speaker's mouth is)")
    blob = json.loads(path.read_text())
    if blob["key"] != layout_key(clip):
        raise ValueError(f"{path} was measured for a different timeline than clip.yaml now has — re-run scripts/extract_segments.py")
    if blob["frame_h"] != frame_h:
        raise ValueError(f"{path} was measured on a {blob['frame_h']}px-tall frame, captions are placed on {frame_h}px — re-run scripts/extract_segments.py")
    return [Zone(shot["t0"], shot["t1"], shot["mouth"][0], shot["mouth"][1], f"{name}")
            for name, entry in blob["files"].items() for shot in entry["shots"] if shot["mouth"] is not None]


def has_split(clip: Clip) -> bool:
    return any(s.visual.kind == "aroll" and s.visual.treatment == "splitscreen" for s in clip.timeline)


def block_height(lines: int, font_px: float) -> float:
    return lines * font_px * LINE_HEIGHT_EM


def hits(top: float, bottom: float, start: float, end: float, zones: list[Zone]) -> list[Zone]:
    """Zones visible while [start, end) is on screen whose mouth band meets [top, bottom] (plus the margin)."""
    return [z for z in zones if z.t0 < end and z.t1 > start
            and top < z.bottom + MOUTH_MARGIN_PX and bottom > z.top - MOUTH_MARGIN_PX]


def exposure(top: float, bottom: float, start: float, end: float, zones: list[Zone]) -> tuple[float, list[Zone]]:
    """Seconds of [start, end) during which the band [top, bottom] covers some mouth, and the zones responsible."""
    covered = hits(top, bottom, start, end, zones)
    spans = sorted((max(start, z.t0), min(end, z.t1)) for z in covered)
    total, edge = 0.0, start
    for a, b in spans:
        a = max(a, edge)
        if b > a:
            total += b - a
            edge = b
    return total, covered


def tolerated_s(start: float, end: float) -> float:
    return min(TOLERATE_MAX_S, TOLERATE_FRACTION * (end - start))


def layout_of(segment) -> str:
    return "split" if segment.visual.kind == "aroll" and segment.visual.treatment == "splitscreen" else "solo"


@dataclass(frozen=True)
class LayoutRun:
    """The stretch [t0, t1) of a caption's life during which the screen layout does not change.

    t0 is the caption's start or the output time of the cut that changes the layout, so the renderer's
    round(t0 * fps) is exactly the frame the layout switches on."""

    t0: float
    t1: float
    layout: str               # "solo" | "split"


def layout_runs(clip: Clip, start: float, end: float, fps: float) -> list[LayoutRun]:
    """[start, end) cut at every layout change, in the frames the renderer draws (round(t * fps)).

    Raises when the timeline leaves any drawn frame of the caption uncovered."""
    first, last = round(start * fps), round(end * fps)
    pieces = [(max(start, s.output_in), min(end, s.output_out), layout_of(s)) for s in clip.timeline
              if max(first, round(s.output_in * fps)) < min(last, round(s.output_out * fps))]
    runs: list[LayoutRun] = []
    for t0, t1, layout in sorted(pieces):
        if runs and runs[-1].layout == layout:
            runs[-1] = LayoutRun(runs[-1].t0, t1, layout)
        else:
            runs.append(LayoutRun(t0, t1, layout))
    frames = [(round(r.t0 * fps), round(r.t1 * fps)) for r in runs]
    if not frames or frames[0][0] != first or frames[-1][1] != last or any(a[1] != b[0] for a, b in zip(frames, frames[1:])):
        raise ValueError(f"caption {start:.2f}-{end:.2f}s: the timeline does not cover frames {first}-{last} contiguously "
                         f"(layout runs {frames}) — fix the timeline's output_in/output_out")
    return runs


def placements_path(ass_path: Path) -> Path:
    """Sidecar of an aligned .ass: each card's position per layout run (align_subtitles writes it,
    validate_subtitles and remotion/gen-props.mjs refuse an .ass without it)."""
    return ass_path.with_suffix(".placements.json")


def choose_position(start: float, end: float, lines: int, font_px: float, play_w: int, play_h: int, zones: list[Zone],
                    default_margin_v: float, split_share: float, safe_top: float, safe_bottom: float) -> Placement:
    """The first position whose mouth exposure is within tolerated_s(); raises if none.

    A caption that is mostly on a split screen tries the seam, then the top of the bottom panel, then the style's
    bottom-centre; one that is mostly on a solo tries bottom-centre first. A card that straddles a cut therefore sits
    where it is clear for most of its life and may brush a mouth for a short stretch around the cut. When a card
    straddles a cut so evenly that none of those works, it goes in a gap between the mouths (just under the one above,
    inside the safe zone), nearest the seam, with zero exposure.
    """
    seam = play_h / 2
    block = block_height(lines, font_px)
    bottom = Placement("bottom", "", play_h - default_margin_v - block, play_h - default_margin_v)
    seam_p = Placement("seam", "{\\an5}", seam - block / 2, seam + block / 2)
    top_p = Placement("panel-top", f"{{\\an8\\pos({play_w / 2:g},{seam + PANEL_TOP_PAD_PX:g})}}",
                      seam + PANEL_TOP_PAD_PX, seam + PANEL_TOP_PAD_PX + block)
    order = [seam_p, top_p, bottom] if split_share >= 0.5 else [bottom, seam_p, top_p]
    blocked = []
    for c in order:
        seconds, covered = exposure(c.top, c.bottom, start, end, zones)
        if seconds <= tolerated_s(start, end):
            return c
        blocked.append(f"{c.name} {c.top:.0f}-{c.bottom:.0f}px covers {seconds:.2f}s of " + ", ".join(
            f"{z.who} mouth {z.top:.0f}-{z.bottom:.0f}px" for z in covered))
    visible = [z for z in zones if z.t0 < end and z.t1 > start]
    tops = [z.bottom + MOUTH_MARGIN_PX + 1 for z in visible] + [z.top - MOUTH_MARGIN_PX - 1 - block for z in visible]
    for top in sorted(tops, key=lambda t: abs(t + block / 2 - seam)):
        if top >= safe_top and top + block <= safe_bottom and not hits(top, top + block, start, end, zones):
            return Placement("gap", f"{{\\an8\\pos({play_w / 2:g},{top:.0f})}}", top, top + block)
    raise ValueError(f"caption {start:.2f}-{end:.2f}s ({lines} line(s) @ {font_px:g}px) has no position that keeps every mouth "
                     f"uncovered (tolerance {tolerated_s(start, end):.2f}s): " + "; ".join(blocked))
