#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "static-ffmpeg>=2.7",
#   "platformdirs>=4",
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Stage 8 step 4 — decide the framing of every A-roll timeline segment (`assets/framing.json`).

This script cuts NO video. It decides, per segment and per speaker panel, which part of which source video
is shown and where it is drawn; `remotion/gen-props.mjs` copies that geometry into props.json and the Remotion
composition (`remotion/src/Short.tsx`) draws it from the single source video with a CSS transform.

Source selection per speaker panel:

* the speaker has a `camera_file` — that isolated camera is used and the source range is shifted
  by the sync offset (`camera_t = episode_t - offset_s`). An unverified, missing or gap-crossing
  sync entry is a hard refusal: unverified sync means unusable footage, never a silent fall back
  to the published frame.
* otherwise — the segment's own `source_file` (a shared, multi-person frame).

Framing is COMPUTED PER SEGMENT from where the speaker's face is (scripts/facelib.py): YuNet
face detection on frames sampled across the segment's source range, the speaker's face picked
by transcript-derived identity on a shared frame (or the largest face on an isolated camera),
and a crop centred on their median face position at the panel aspect, with head room. No stored
crop is read: `episode.yaml speakers[].preferred_crop` is not used. A speaker whose face cannot be
found in a segment is a hard refusal — there is no centre-crop fallback. `visual.crop` (a per-segment
override set by hand) still wins for a closeup. Detections are cached under `clips/<slug>/assets/faces/`.

TILE INVARIANT: on a gallery frame (Zoom-style tiles) a speaker's crop NEVER crosses their own tile. The tile is
measured from the colour seams around the speaker's face on every sampled frame (facelib.tile_bounds) and refused
when it still holds another person's face. A closeup frames head and shoulders (face box ~30% of the frame
height, eye line ~0.30-0.36); a split-screen panel (and the quote layout's speaker panel) likewise frames head and shoulders — face box ~30% of the panel height, eye line ~0.36 — as a tile-wide, tall crop fit to the panel's height with blurred side gaps when a crop of the panel's aspect would be wider than the tile. Neither is magnified past
`framing.max_upscale` (config, default 2.0): when the tile cannot supply that, the shot is BLUR-FILLED — the sharp
tile-bounded crop at its true scale over a blurred, darkened copy of itself (a CSS backdrop in the composition).

`assets/framing.json` holds, per segment, the panels (`full` for a closeup, `top` + `bottom` for a split screen)
and per panel the source file, the source start time and the shots: crop window keys in source pixels, the draw
rectangle inside the panel, the blur-fill backdrop, the tile and the nose-to-chin mouth band in output pixels.
`capplace.load_zones` reads the mouth bands (align_subtitles.py / validate_subtitles.py keep captions off every
mouth), so captions are placed against exactly the geometry Remotion draws.

QUOTE LAYOUT: a short's `overlays:` (fullscreen stills, schemas.md § Overlays) turn the frame into a split while they are
up — the screenshot on the top panel, the segment's speaker on the bottom panel (framed like a split-screen panel, so the
crop stays inside that speaker's tile; scripts/quotelayout.py). Each A-roll segment under an overlay gets a `quote` panel
beside its normal panels, and `quotes` holds the screenshot fit rectangles. Anything else a horizontal overlay can do
(pip, text modes, video, grids, crops, labels) is refused: "not implemented for shorts".

Horizontal clips (`format: clip`) are not handled here; see render_horizontal.py.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

import capplace
import facelib
import quotelayout
from broll import still_dims
from framer import Framer, resolve_source
from pslib import Clip, Episode, TimelineSegment, fmt_range, load_clip, load_episode
from psmedia import (
    episode_root_for,
    even,
    load_config,
    media_path,
    parse_crop,
    probe_dims,
    profile_dims,
    resolve_profile,
    validate_crop_within,
)

console = Console()
app = typer.Typer(add_completion=False)

SPEAKER_TREATMENTS = ("closeup-",)


@dataclass
class Panel:
    """One drawn video rectangle: a source range, a crop schedule, and where in the output frame it sits."""

    segment: TimelineSegment
    slot: str                       # "full" | "top" | "bottom"
    speaker: str
    rect: tuple[int, int, int, int]  # x, y, w, h in output px
    source_rel: str                 # path relative to the episode root
    source_dims: tuple[int, int]
    source_in: float
    source_out: float
    shots: list[facelib.Shot]       # crop windows over source time (one per layout; a moving window pans)
    origin: str                     # human-readable note for the report

    @property
    def name(self) -> str:
        return self.segment.id if self.slot == "full" else f"{self.segment.id}-{self.slot}"


def treatment_speaker(seg: TimelineSegment) -> str | None:
    for prefix in SPEAKER_TREATMENTS:
        if seg.visual.treatment.startswith(prefix):
            return seg.visual.treatment[len(prefix):]
    return None


def override_shot(seg_in: float, seg_out: float, crop: tuple[int, int, int, int], rect_w: int, rect_h: int) -> facelib.Shot:
    """A hand-set `visual.crop`: the crop letterboxed (never stretched) into the panel, no backdrop, no tile."""
    w, h, x, y = crop
    scale = min(rect_w / w, rect_h / h)
    ow, oh = even(round(w * scale)), even(round(h * scale))
    return facelib.Shot(seg_in, seg_out, w, h, [(seg_in, x, y)], dst=((rect_w - ow) // 2, (rect_h - oh) // 2, ow, oh), scale=ow / w)


def build_panels(
    clip: Clip, episode: Episode, episode_root: Path, clip_dir: Path, out_w: int, out_h: int, max_upscale: float,
) -> tuple[list[Panel], list[str]]:
    panels: list[Panel] = []
    refusals: list[str] = []
    framer = Framer(clip_dir, episode_root, episode)
    panel_h = even(out_h // 2)

    def framed(seg: TimelineSegment, sid: str, source: tuple, kind: str, h: int) -> list[facelib.Shot] | None:
        """Face-detected shots, or None after recording why not (the case boundary: one bad segment must not hide the rest)."""
        try:
            return framer.shots(seg, sid, source, kind, out_w, h, max_upscale)
        except facelib.FaceError as err:
            refusals.append(str(err))
            return None

    for seg in clip.timeline:
        if seg.visual.kind != "aroll":
            continue
        treatment = seg.visual.treatment
        sid = treatment_speaker(seg)

        if treatment == "splitscreen":
            names = seg.visual.speakers
            if not names or len(names) != 2 or len(set(names)) != 2:
                raise ValueError(f"{seg.id}: splitscreen needs visual.speakers = [top, bottom] (two distinct ids), got {names}")
            for slot, panel_sid, y in zip(("top", "bottom"), names, (0, out_h - panel_h)):
                source = resolve_source(seg, episode, panel_sid)
                refusals += source[4]
                if source[4]:
                    continue
                source_rel, src_in, src_out, origin, _, isolated = source
                shots = framed(seg, panel_sid, source, "panel", panel_h)
                if shots is None:
                    continue
                panels.append(Panel(seg, slot, panel_sid, (0, y, out_w, panel_h), source_rel, probe_dims(episode, source_rel),
                                    src_in, src_out, shots, f"{origin} — {slot} = {panel_sid} ({'own camera' if isolated else 'shared frame'})"))
            continue

        if sid is None:
            refusals.append(
                f"{seg.id}: unsupported treatment {treatment!r} for a short — expected "
                f"closeup-<speaker>|splitscreen (horizontal clips use render_horizontal.py)"
            )
            continue
        source = resolve_source(seg, episode, sid)
        refusals += source[4]
        if source[4]:
            continue
        source_rel, src_in, src_out, origin, _, isolated = source
        if seg.visual.crop:
            shots = [override_shot(src_in, src_out, parse_crop(seg.visual.crop), out_w, out_h)]
            note = f"{sid} (visual.crop override)"
        else:
            shots = framed(seg, sid, source, "closeup", out_h)
            note = f"{sid} ({'own camera' if isolated else 'shared frame'})"
        if shots is None:
            continue
        panels.append(Panel(seg, "full", sid, (0, 0, out_w, out_h), source_rel, probe_dims(episode, source_rel),
                            src_in, src_out, shots, f"{origin} — {note}"))

    for panel in panels:
        media_path(episode_root, panel.source_rel)  # the file Remotion will open must exist
        src_w, src_h = panel.source_dims
        for shot in panel.shots:
            for _, x, y in shot.keys:
                validate_crop_within((shot.w, shot.h, x, y), src_w, src_h, panel.name)
    return panels, refusals


def build_quote_panels(
    clip: Clip, episode: Episode, episode_root: Path, clip_dir: Path, out_w: int, out_h: int, max_upscale: float,
) -> tuple[list[Panel], list[dict], list[str]]:
    """(bottom panels of the quote layout, one framing record per overlay, refusals). Raises for an overlay a short cannot draw."""
    overlays = quotelayout.quote_overlays(clip)
    if not overlays:
        return [], [], []
    panel_h = even(out_h // 2)
    framer = Framer(clip_dir, episode_root, episode)
    panels: list[Panel] = []
    refusals: list[str] = []
    quotes: list[dict] = []
    done: set[str] = set()
    for ov in overlays:
        dims = {}
        for shot in ov.shots:
            path = clip_dir / "broll" / shot.asset
            if not path.is_file():
                raise FileNotFoundError(f"overlay {ov.id}: {path} is missing — copy the screenshot into the clip's broll/")
            dims[shot.asset] = still_dims(path)
        quotes.append(quotelayout.quote_record(ov, dims, out_w, panel_h, facelib.BLUR_PX, facelib.BLUR_BRIGHTNESS))
        for seg, _, _ in quotelayout.quote_slices(clip, ov):
            if seg.id in done:
                continue
            done.add(seg.id)
            source = resolve_source(seg, episode, seg.speaker)
            refusals += source[4]
            if source[4]:
                continue
            source_rel, src_in, src_out, origin, _, isolated = source
            where = f"{seg.id} quote ({seg.speaker})"
            try:
                shots = quotelayout.speaker_panel_shots(framer.track(seg, seg.speaker, source), probe_dims(episode, source_rel),
                                                        out_w, panel_h, max_upscale, where)
            except facelib.FaceError as err:
                refusals.append(str(err))
                continue
            panels.append(Panel(seg, "bottom", seg.speaker, (0, out_h - panel_h, out_w, panel_h), source_rel, probe_dims(episode, source_rel),
                                src_in, src_out, shots, f"{origin} — quote {ov.id}: {seg.speaker} below the screenshot "
                                f"({'own camera' if isolated else 'shared frame'})"))
    for panel in panels:
        media_path(episode_root, panel.source_rel)
        for shot in panel.shots:
            for _, x, y in shot.keys:
                validate_crop_within((shot.w, shot.h, x, y), *panel.source_dims, f"{panel.segment.id}-quote")
    return panels, quotes, refusals


def describe_shots(panel: Panel) -> str:
    def one(s: facelib.Shot) -> str:
        x, y = s.keys[0][1], s.keys[0][2]
        text = f"{s.w}x{s.h}@({x},{y})" + ("" if s.static else f" pan x{len(s.keys)}")
        if s.face_frac:
            text += f" {s.scale:.2f}x face {s.face_frac:.0%} eyes {s.eye_frac:.2f}"
        return text + (" BLUR-FILL" if s.blur_fill else "")
    return one(panel.shots[0]) if len(panel.shots) == 1 else f"{len(panel.shots)} shots: " + " | ".join(
        f"{s.t0 - panel.source_in:.1f}s {one(s)}" for s in panel.shots)


def shot_entry(panel: Panel, shot: facelib.Shot, rect_w: int, rect_h: int) -> dict:
    """One shot in CLIP time: crop keys in source px, the draw rectangle in panel px, the mouth band in full-frame px."""
    to_clip = panel.segment.output_in - panel.source_in
    mouth = None if shot.mouth == (0.0, 0.0) else [round(shot.mouth[0] + panel.rect[1], 1), round(shot.mouth[1] + panel.rect[1], 1)]
    return {
        "t0": round(shot.t0 + to_clip, 4), "t1": round(shot.t1 + to_clip, 4),
        "crop": {"w": shot.w, "h": shot.h, "keys": [[round(t + to_clip, 4), x, y] for t, x, y in shot.keys]},
        "dst": list(shot.dst) if shot.dst is not None else [0, 0, rect_w, rect_h],
        "backdrop": {"blur_px": facelib.BLUR_PX, "brightness": facelib.BLUR_BRIGHTNESS} if shot.blur_fill else None,
        "tile": None if shot.tile is None else list(shot.tile),
        "scale": round(shot.scale, 3), "face_frac": round(shot.face_frac, 3), "eye_frac": round(shot.eye_frac, 3),
        "mouth": mouth,
    }


def framing_entry(panel: Panel) -> dict:
    _, _, w, h = panel.rect
    return {
        "slot": panel.slot, "speaker": panel.speaker, "rect": list(panel.rect),
        "source": panel.source_rel, "source_dims": list(panel.source_dims),
        "source_start_s": round(panel.source_in, 4),
        "shots": [shot_entry(panel, shot, w, h) for shot in panel.shots],
    }


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    profile_name: str = typer.Option("youtube-shorts", "--profile", help="Platform profile name from episode.yaml (format: short)"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"),
    config_path: Path = typer.Option(None, "--config", help="Pipeline config (default: config/defaults.yaml)"),
) -> None:
    """Decide the framing of every A-roll segment of CLIP_DIR and write assets/framing.json."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    root = episode_root_for(clip_dir, episode_root)
    config = load_config(config_path, root)  # fails loudly if the pipeline config is missing/malformed

    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")
    profile = resolve_profile(episode, profile_name)
    if profile.format != "short" or clip.clip.format != "short":
        raise typer.BadParameter(
            f"frame_segments.py is for shorts: profile {profile.name!r} is {profile.format!r}, clip "
            f"{clip.clip.id} is {clip.clip.format!r}. Horizontal clips render via render_horizontal.py."
        )
    out_w, out_h = profile_dims(profile)

    panels, refusals = build_panels(clip, episode, root, clip_dir, out_w, out_h, config.framing.max_upscale)
    quote_panels, quotes, quote_refusals = build_quote_panels(clip, episode, root, clip_dir, out_w, out_h, config.framing.max_upscale)
    refusals += quote_refusals
    if refusals:
        console.print("[bold red]REFUSED[/] — A-roll sources are not usable as the manifest asks:")
        for r in refusals:
            console.print(f"  [red]•[/] {r}")
        raise typer.Exit(1)
    if not panels:
        raise typer.BadParameter(f"{clip.clip.id}: timeline has no aroll segments — nothing to frame")

    logger.info(f"clip={clip.clip.id} profile={profile.name} {out_w}x{out_h}@{profile.fps:g} panels={len(panels)}")

    table = RichTable(title=f"A-roll framing — {clip.clip.id} @ {profile.name}", header_style="bold cyan")
    for column, kwargs in (
        ("Panel", {"no_wrap": True}), ("Treatment", {}), ("Source used", {}), ("Range", {"no_wrap": True}),
        ("Crop", {}), ("Tile", {"no_wrap": True}),
    ):
        table.add_column(column, **kwargs)
    for panel in [*panels, *quote_panels]:
        tile = panel.shots[0].tile
        table.add_row(panel.name, panel.segment.visual.treatment, panel.origin, fmt_range(panel.source_in, panel.source_out),
                      describe_shots(panel), "-" if tile is None else f"{tile[0]}-{tile[2]}")
    console.print(table)

    by_segment: dict[str, dict] = {}
    for panel in panels:
        entry = by_segment.setdefault(panel.segment.id, {"treatment": panel.segment.visual.treatment, "panels": []})
        entry["panels"].append(framing_entry(panel))
    for panel in quote_panels:
        by_segment[panel.segment.id]["quote"] = framing_entry(panel)
    path = capplace.write_framing(clip_dir, clip, out_h, by_segment, quotes)
    logger.info(f"wrote {path}")
    console.print(f"[bold green]OK[/] {clip.clip.id}: {len(panels)} panel(s) over {len(by_segment)} A-roll segment(s) → {path} ({len(quote_panels)} quote panel(s) over {len(quotes)} overlay(s); no video written)")


if __name__ == "__main__":
    app()
