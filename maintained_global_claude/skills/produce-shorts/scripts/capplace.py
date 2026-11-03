"""Where captions may sit so they never cover a mouth — shared by frame_segments, align_subtitles and validate_subtitles.

Not executable (pure stdlib + pslib). `frame_segments.py` measures, per shot, the vertical band between each
speaker's nose and chin in output-frame pixels and writes it, with the framing geometry Remotion draws, to
`assets/framing.json` (`write_framing`). Captions are placed per treatment:

* solo (closeup, b-roll): the style's bottom-centre;
* quote layout (a picture overlay in a short: screenshot on the top panel, the speaker on the bottom panel): the
  caption goes at the top of the bottom panel, or on the seam, and must clear the speaker's mouth AND the screenshot
  as drawn (`load_keepouts`, zero tolerance — it never covers the screenshot's text);
* split screen: the caption must leave BOTH faces' mouths clear, so it goes on the panel seam
  (centred on the 960px boundary) or, if a mouth reaches the seam, at the top of the bottom panel.
  `choose_position` picks the first that clears every mouth zone measured while the caption is on screen
  (TOLERATE_FRACTION of the stretch, at most TOLERATE_MAX_S, of contact is allowed) and raises when none does.

Position follows the layout frame by frame: a card that spans a layout change is NOT split (that would break
its reading-speed budget); it gets one position per `layout_runs` stretch, written to the `.placements.json`
sidecar of the .ass, and the renderer switches position on exactly the frame the layout switches.

The framing carries `key` = a fingerprint of the clip's A-roll timeline; `load_zones` refuses a framing measured for a
different timeline ("run frame_segments.py first") instead of placing captions from stale faces.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from pslib import Clip

FRAMING_PATH = Path("assets") / "framing.json"
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


def quote_windows(clip: Clip) -> list[tuple[float, float]]:
    """OUTPUT-time windows [start, end) of a short's picture overlays, during which the quote layout is on screen."""
    return [(ov.start, ov.end) for ov in clip.overlays] if clip.clip.format == "short" else []


def has_quote(clip: Clip) -> bool:
    return bool(quote_windows(clip))


def needs_zones(clip: Clip) -> bool:
    """True when captions must be placed against measured geometry (a split screen or a quote layout)."""
    return has_split(clip) or has_quote(clip)


def layout_key(clip: Clip) -> str:
    rows = [(s.id, s.visual.treatment, s.visual.speakers, s.visual.crop, round(s.source_in, 4), round(s.source_out, 4),
             round(s.output_in, 4), round(s.output_out, 4)) for s in clip.timeline if s.visual.kind == "aroll"]
    if has_quote(clip):   # the speaker below a screenshot is chosen per segment, so the windows and speakers are part of the key
        rows = [rows, [(o.id, o.mode, round(o.start, 4), round(o.end, 4)) for o in clip.overlays],
                [(s.id, s.speaker) for s in clip.timeline if s.visual.kind == "aroll"]]
    return hashlib.sha256(json.dumps(rows, default=str).encode()).hexdigest()[:16]


def write_framing(clip_dir: Path, clip: Clip, frame_h: int, segments: dict[str, dict], quotes: list[dict] | None = None) -> Path:
    """`segments[id] = {"treatment", "panels": [{"slot", "shots": [{"t0", "t1", "mouth", ...}], ...}], "quote"?: {...panel...}}`
    (frame_segments.py); `quotes` = one record per picture overlay (quotelayout.quote_record)."""
    path = clip_dir / FRAMING_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"key": layout_key(clip), "frame_h": frame_h, "segments": segments, "quotes": quotes or []}, indent=1))
    return path


def _framing(clip_dir: Path, clip: Clip, frame_h: int, hint: str) -> dict:
    path = clip_dir / FRAMING_PATH
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing — run scripts/frame_segments.py before {hint} "
                                f"(it measures where each speaker's mouth is)")
    blob = json.loads(path.read_text())
    if blob["key"] != layout_key(clip):
        raise ValueError(f"{path} was measured for a different timeline than clip.yaml now has — re-run scripts/frame_segments.py")
    if blob["frame_h"] != frame_h:
        raise ValueError(f"{path} was measured on a {blob['frame_h']}px-tall frame, captions are placed on {frame_h}px — re-run scripts/frame_segments.py")
    return blob


def _outside(t0: float, t1: float, windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """[t0, t1) minus the windows."""
    pieces = [(t0, t1)]
    for w0, w1 in windows:
        pieces = [p for a, b in pieces for p in ((a, min(b, w0)), (max(a, w1), b)) if p[1] - p[0] > 1e-6]
    return pieces


def _inside(t0: float, t1: float, windows: list[tuple[float, float]]) -> list[tuple[float, float]]:
    return [(max(t0, w0), min(t1, w1)) for w0, w1 in windows if min(t1, w1) - max(t0, w0) > 1e-6]


def load_zones(clip_dir: Path, clip: Clip, frame_h: int) -> list[Zone]:
    """Mouth bands of whatever is on screen: the regular panels outside the quote windows, the bottom-panel speaker inside."""
    blob = _framing(clip_dir, clip, frame_h, "aligning captions")
    windows = quote_windows(clip)
    zones = [Zone(a, b, shot["mouth"][0], shot["mouth"][1], f"{seg_id}-{panel['slot']}")
             for seg_id, entry in blob["segments"].items() for panel in entry["panels"]
             for shot in panel["shots"] if shot["mouth"] is not None
             for a, b in _outside(shot["t0"], shot["t1"], windows)]
    zones += [Zone(a, b, shot["mouth"][0], shot["mouth"][1], f"{seg_id}-quote")
              for seg_id, entry in blob["segments"].items() if entry.get("quote")
              for shot in entry["quote"]["shots"] if shot["mouth"] is not None
              for a, b in _inside(shot["t0"], shot["t1"], windows)]
    return zones


def load_keepouts(clip_dir: Path, clip: Clip, frame_h: int) -> list[Zone]:
    """The screenshot as drawn (fit rectangle at its full push-in), per shot, in output px: captions may never touch it."""
    blob = _framing(clip_dir, clip, frame_h, "aligning captions")
    out: list[Zone] = []
    for quote in blob["quotes"]:
        _, top, _, height = quote["rect"]
        for shot in quote["shots"]:
            x, y, w, h = shot["dst"]
            zoom = max(shot["zoom"])
            out.append(Zone(shot["t0"], shot["t1"], top + y + h / 2 - h * zoom / 2, top + y + h / 2 + h * zoom / 2,
                            f"{quote['id']} screenshot"))
    return out


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

    t0 is the caption's start or the output time of the cut (or overlay edge) that changes the layout, so the
    renderer's round(t0 * fps) is exactly the frame the layout switches on."""

    t0: float
    t1: float
    layout: str               # "solo" | "split" | "quote"


def layout_runs(clip: Clip, start: float, end: float, fps: float) -> list[LayoutRun]:
    """[start, end) cut at every layout change, in the frames the renderer draws (round(t * fps)).

    A picture overlay in a short is a "quote" run whatever the timeline shows underneath.
    Raises when the timeline leaves any drawn frame of the caption uncovered."""
    first, last = round(start * fps), round(end * fps)
    windows = [(round(a * fps), round(b * fps)) for a, b in quote_windows(clip)]
    spans = [(round(s.output_in * fps), round(s.output_out * fps), layout_of(s)) for s in clip.timeline]
    cuts = sorted({first, last} | {c for a, b, _ in spans for c in (a, b)} | {c for w in windows for c in w})
    cuts = [c for c in cuts if first <= c <= last]
    runs: list[LayoutRun] = []
    frames: list[tuple[int, int]] = []
    for a, b in zip(cuts, cuts[1:]):
        layout = "quote" if any(w0 <= a < w1 for w0, w1 in windows) else next((lay for s0, s1, lay in spans if s0 <= a < s1), None)
        if layout is None:
            raise ValueError(f"caption {start:.2f}-{end:.2f}s: the timeline does not cover frame {a} — fix the timeline's output_in/output_out")
        t0, t1 = (start if a == first else a / fps), (end if b == last else b / fps)
        if runs and runs[-1].layout == layout:
            runs[-1] = LayoutRun(runs[-1].t0, t1, layout)
            frames[-1] = (frames[-1][0], b)
        else:
            runs.append(LayoutRun(t0, t1, layout))
            frames.append((a, b))
    if not frames or frames[0][0] != first or frames[-1][1] != last or any(x[1] != y[0] for x, y in zip(frames, frames[1:])):
        raise ValueError(f"caption {start:.2f}-{end:.2f}s: the timeline does not cover frames {first}-{last} contiguously "
                         f"(layout runs {frames}) — fix the timeline's output_in/output_out")
    return runs


def placements_path(ass_path: Path) -> Path:
    """Sidecar of an aligned .ass: each card's position per layout run (align_subtitles writes it,
    validate_subtitles and remotion/gen-props.mjs refuse an .ass without it)."""
    return ass_path.with_suffix(".placements.json")


def choose_position(start: float, end: float, lines: int, font_px: float, play_w: int, play_h: int, zones: list[Zone],
                    default_margin_v: float, split_share: float, safe_top: float, safe_bottom: float,
                    keepouts: list[Zone] = (), top_first: bool = False) -> Placement:
    """The first position whose mouth exposure is within tolerated_s(); raises if none.

    A caption that is mostly on a split screen tries the seam, then the top of the bottom panel, then the style's
    bottom-centre; one that is mostly on a solo tries bottom-centre first. A card that straddles a cut therefore sits
    where it is clear for most of its life and may brush a mouth for a short stretch around the cut. When a card
    straddles a cut so evenly that none of those works, it goes in a gap between the mouths (just under the one above,
    inside the safe zone), nearest the seam, with zero exposure.

    `keepouts` (the screenshot of a quote layout) tolerate NO contact: a position that touches one is never chosen.
    `top_first` (quote layout) tries the top of the bottom panel first, then the seam, then the bottom.
    """
    seam = play_h / 2
    block = block_height(lines, font_px)
    bottom = Placement("bottom", "", play_h - default_margin_v - block, play_h - default_margin_v)
    seam_p = Placement("seam", "{\\an5}", seam - block / 2, seam + block / 2)
    top_p = Placement("panel-top", f"{{\\an8\\pos({play_w / 2:g},{seam + PANEL_TOP_PAD_PX:g})}}",
                      seam + PANEL_TOP_PAD_PX, seam + PANEL_TOP_PAD_PX + block)
    order = [top_p, seam_p, bottom] if top_first else [seam_p, top_p, bottom] if split_share >= 0.5 else [bottom, seam_p, top_p]
    blocked = []
    for c in order:
        pictured = hits(c.top, c.bottom, start, end, keepouts)
        if pictured:
            blocked.append(f"{c.name} {c.top:.0f}-{c.bottom:.0f}px covers the " + ", ".join(
                f"{z.who} {z.top:.0f}-{z.bottom:.0f}px" for z in pictured))
            continue
        seconds, covered = exposure(c.top, c.bottom, start, end, zones)
        if seconds <= tolerated_s(start, end):
            return c
        blocked.append(f"{c.name} {c.top:.0f}-{c.bottom:.0f}px covers {seconds:.2f}s of " + ", ".join(
            f"{z.who} mouth {z.top:.0f}-{z.bottom:.0f}px" for z in covered))
    visible = [z for z in [*zones, *keepouts] if z.t0 < end and z.t1 > start]
    tops = [z.bottom + MOUTH_MARGIN_PX + 1 for z in visible] + [z.top - MOUTH_MARGIN_PX - 1 - block for z in visible]
    for top in sorted(tops, key=lambda t: abs(t + block / 2 - seam)):
        if top >= safe_top and top + block <= safe_bottom and not hits(top, top + block, start, end, [*zones, *keepouts]):
            return Placement("gap", f"{{\\an8\\pos({play_w / 2:g},{top:.0f})}}", top, top + block)
    raise ValueError(f"caption {start:.2f}-{end:.2f}s ({lines} line(s) @ {font_px:g}px) has no position that keeps every mouth "
                     f"uncovered (tolerance {tolerated_s(start, end):.2f}s): " + "; ".join(blocked))
