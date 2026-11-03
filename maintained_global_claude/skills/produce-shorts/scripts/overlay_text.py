"""Text layers for horizontal-clip overlays: lower-thirds, cards, and picture labels → Remotion.

Not executable — render_horizontal.py calls `render_text_layers()`. The default ffmpeg build has
no `drawtext`, so every piece of on-screen type is drawn by the Remotion `Card` composition
(remotion/src/Card.tsx, the same bundled Inter family as the captions) and written as a
transparent ProRes 4444 layer the final ffmpeg pass overlays. The style is config/defaults.yaml
`broll.text` and nothing else — this module only translates it into Card props.

Layers produced (one file each, the overlay's window long):

* `<id>.mov` for every `lowerthird` / `card` overlay;
* `<id>-labels.mov` for a picture overlay with a `label` (under the pip) or grid-tile labels.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from overlay_picture import content_size, frames, grid_cells, target_box, window_frames
from pslib import Overlay, TextRun
from psmedia import SCRIPTS_DIR, BrollConfig, SubtitleConfig

TEMPLATE = SCRIPTS_DIR.parent / "remotion"
TEMPLATE_FILES = ("package.json", "package-lock.json", "remotion.config.ts", "tsconfig.json",
                  "render-cards.mjs", "src", "public/fonts", "lib", "gen-props.mjs")


@dataclass
class TextLayer:
    overlay: Overlay
    name: str          # file stem: <id> or <id>-labels
    props: dict


def _style(cfg: BrollConfig) -> dict:
    t = cfg.text
    return {
        "plateColor": t.plate_color, "plateOpacity": t.plate_opacity, "plateRadius": t.plate_radius,
        "platePadV": t.plate_pad_v, "platePadH": t.plate_pad_h, "accentColor": t.colors["accent"],
        "accentBarPx": t.accent_bar_px, "lineGap": t.line_gap, "ruleFrames": t.rule_frames,
        "popFrames": t.pop_frames, "ruleColor": t.rule_color, "textShadow": t.text_shadow,
    }


def _color(cfg: BrollConfig, key: str | None, where: str) -> str:
    name = key or "text"
    if name not in cfg.text.colors:
        raise ValueError(f"{where}: colour {name!r} is not in config broll.text.colors {sorted(cfg.text.colors)}")
    return cfg.text.colors[name]


def _run(cfg: BrollConfig, run: TextRun, fps: float, where: str, appear: int | None = None) -> dict:
    own = frames(run.at, fps) if run.at is not None else None
    return {
        "text": run.text,
        "color": _color(cfg, run.color, where),
        "weight": run.weight or cfg.text.weight,
        "appear": max(x for x in (own, appear) if x is not None) if (own is not None or appear is not None) else None,
        "underline": frames(run.underline_at, fps) if run.underline_at is not None else None,
        "strike": frames(run.strike_at, fps) if run.strike_at is not None else None,
    }


def _word_runs(cfg: BrollConfig, ov: Overlay, fps: float) -> list[list[dict]]:
    """Lines of runs, one Card run per WORD so a line wraps inside the plate's maxWidth (a Card run
    is an unbreakable inline-block — a long run used to overflow the plate). The space after a word
    is its own run (plain between two runs, so a rule never spills past the run it marks). `reveal: words`
    types the words on across reveal_s; otherwise each word keeps its run's `at`."""
    total = sum(len(r.text.split()) for line in ov.lines for r in line.runs)
    step = ov.reveal_s / max(total - 1, 1)
    k, out = 0, []
    for line in ov.lines:
        runs = []
        words = [(r, w) for r in line.runs for w in r.text.split()]
        for j, (r, word) in enumerate(words):
            appear = frames(k * step, fps) if ov.reveal == "words" else None
            runs.append(_run(cfg, r.model_copy(update={"text": word}), fps, ov.id, appear=appear))
            if j < len(words) - 1:
                inside = words[j + 1][0] is r   # a space inside one run keeps that run's rules
                plain = r.model_copy(update={"text": " "} if inside else {"text": " ", "underline_at": None, "strike_at": None})
                runs.append(_run(cfg, plain, fps, ov.id, appear=appear))
            k += 1
        out.append(runs)
    return out


def text_layer(ov: Overlay, cfg: BrollConfig, w: int, h: int, fps: float) -> TextLayer:
    t = cfg.text
    place_name = ov.placement or ("lowerthird" if ov.mode == "lowerthird" else "card")
    if place_name not in t.placements:
        raise ValueError(f"{ov.id}: placement {place_name!r} is not in config broll.text.placements {sorted(t.placements)}")
    place = t.placements[place_name]
    n = window_frames(ov, fps)
    sizes = [t.sizes["lowerthird"] if (ov.mode == "lowerthird" and i == 0) else
             t.sizes["lowerthird_sub"] if ov.mode == "lowerthird" else t.sizes["card"]
             for i in range(len(ov.lines))]
    element = {
        "x": place.x * w / 1920, "y": place.y * h / 1080, "anchor": place.anchor,
        "maxWidth": place.max_width * w / 1920,
        "align": "center" if place.anchor.endswith("center") and place.anchor != "center-left" else "left",
        "plate": True, "accentBar": ov.mode == "lowerthird",
        "from": 0, "to": n,
        "fadeIn": ov.fade_in_frames or t.fade_frames, "fadeOut": ov.fade_out_frames or t.fade_frames,
        "lines": [{"size": size, "runs": runs} for size, runs in zip(sizes, _word_runs(cfg, ov, fps))],
    }
    return TextLayer(ov, ov.id, _props(cfg, w, h, fps, n, [element]))


def label_layer(ov: Overlay, cfg: BrollConfig, w: int, h: int, fps: float) -> TextLayer | None:
    """Labels drawn over a picture overlay: the pip caption and/or grid-tile labels."""
    t = cfg.text
    n = window_frames(ov, fps)
    elements: list[dict] = []
    tb = target_box(ov, w, h)
    if ov.label:
        border = cfg.pip.border_px if ov.mode == "pip" else 0
        elements.append({
            "x": tb.x - border, "y": tb.y + tb.h + border + cfg.pip.label_gap_px, "anchor": "top-left",
            "maxWidth": tb.w + 2 * border, "align": "left", "plate": True, "accentBar": False,
            "from": ov.move_frames, "to": n, "fadeIn": t.fade_frames, "fadeOut": ov.fade_out_frames or t.fade_frames,
            "lines": [{"size": t.sizes["label"], "runs": [
                {"text": ov.label, "color": t.colors["text"], "weight": t.weight, "appear": None,
                 "underline": None, "strike": None}]}],
        })
    cw, ch = content_size(ov, w, h)
    if (cw, ch) != (tb.w, tb.h) and any(t2.label for s in ov.shots if s.grid for t2 in s.grid.tiles):
        raise ValueError(f"{ov.id}: grid-tile labels need a static box (no from_box move)")
    for k, shot in enumerate(ov.shots):
        if shot.grid is None:
            continue
        shot_end = frames(ov.shots[k + 1].at, fps) if k + 1 < len(ov.shots) else n
        cells = grid_cells(tb.w, tb.h, shot.grid.cols, shot.grid.rows, cfg.grid.gap_px)
        for tile, (x, y, cw_, ch_) in zip(shot.grid.tiles, cells):
            if not tile.label:
                continue
            start = frames(shot.at + tile.at, fps)
            elements.append({
                "x": tb.x + x + 10, "y": tb.y + y + ch_ - 10, "anchor": "bottom-left", "maxWidth": cw_ - 20,
                "align": "left", "plate": True, "accentBar": False, "from": start, "to": shot_end,
                "fadeIn": cfg.grid.tile_pop_frames, "fadeOut": 0 if shot_end < n else (ov.fade_out_frames or 0),
                "lines": [{"size": t.sizes["tile_label"], "runs": [
                    {"text": tile.label, "color": t.colors["text"], "weight": t.weight, "appear": None,
                     "underline": None, "strike": None}]}],
            })
    if not elements:
        return None
    return TextLayer(ov, f"{ov.id}-labels", _props(cfg, w, h, fps, n, elements))


def _props(cfg: BrollConfig, w: int, h: int, fps: float, n: int, elements: list[dict]) -> dict:
    return {"width": w, "height": h, "fps": fps, "durationInFrames": n, "style": _style(cfg), "elements": elements}


def plan_text_layers(overlays: list[Overlay], cfg: BrollConfig, subs: SubtitleConfig, w: int, h: int, fps: float) -> list[TextLayer]:
    if cfg.text.font != subs.font:
        raise ValueError(
            f"config broll.text.font {cfg.text.font!r} != subtitles.font {subs.font!r} — cards and captions "
            f"share one family (the Card composition loads only the bundled Inter)"
        )
    layers = [text_layer(ov, cfg, w, h, fps) for ov in overlays if ov.layer == "text"]
    layers += [lay for ov in overlays if ov.layer == "picture" if (lay := label_layer(ov, cfg, w, h, fps))]
    return layers


def ensure_workspace(clip_dir: Path) -> Path:
    """CLIP_DIR/remotion = the skill template's current sources (+ node_modules, installed once)."""
    ws = clip_dir / "remotion"
    ws.mkdir(exist_ok=True)
    for rel in TEMPLATE_FILES:
        src, dst = TEMPLATE / rel, ws / rel
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    if not (ws / "node_modules" / "@remotion" / "renderer").is_dir():
        proc = subprocess.run(["npm", "ci", "--no-audit", "--no-fund"], cwd=ws, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"npm ci in {ws} failed (exit {proc.returncode}): {proc.stderr[-3000:]}")
    return ws


def render_text_layers(layers: list[TextLayer], clip_dir: Path, out_dir: Path, concurrency: int) -> dict[str, Path]:
    """Render every layer with one bundle. Returns {layer name: .mov path}."""
    if not layers:
        return {}
    ws = ensure_workspace(clip_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {lay.name: out_dir / f"{lay.name}.mov" for lay in layers}
    jobs = out_dir / "cards.json"
    jobs.write_text(json.dumps({"concurrency": concurrency,
                                "jobs": [{"out": str(paths[lay.name]), "props": lay.props} for lay in layers]}, indent=1))
    proc = subprocess.run(["node", "render-cards.mjs", str(jobs)], cwd=ws, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"render-cards.mjs failed (exit {proc.returncode}):\n{proc.stdout[-2000:]}\n{proc.stderr[-4000:]}")
    missing = [str(p) for p in paths.values() if not p.is_file()]
    if missing:
        raise RuntimeError(f"render-cards.mjs exited 0 but did not write {missing}")
    return paths
