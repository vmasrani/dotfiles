"""Picture overlays (fullscreen / pip) for horizontal clips → one transparent full-frame layer each.

Not executable — render_horizontal.py calls `build_picture_layer()` once per picture overlay, then
composites every layer over the cut in one pass (`composite_filters()`). Spec: schemas.md § Overlays.

A layer is the overlay's whole window as a full-frame (W x H) BGRA FFV1 file: everything outside
the box is transparent, so the final pass is a plain `overlay` at the window's start. Inside the
window:

* each **shot** fills the box (cover-fit after its optional crop): a video range (with `speed`, and
  `hold_last` to freeze the final frame), a still, or a **grid** of stills that pop in on cue;
* `zoom: [a, b]` is a push-in across the shot (zoompan on a 2x upscale, so it does not judder);
* consecutive shots cut or cross-dissolve (`dissolve_frames`);
* a pip gets a border (config broll.pip); `from_box` + `move_frames` animate the box's size and
  position (eased) from where the previous picture was — a fullscreen still shrinking into a pip,
  or a pip growing to fullscreen;
* `fade_in_frames` / `fade_out_frames` fade the layer's alpha.
"""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from broll import STILL_EXTS
from pslib import Box, Overlay, Shot
from psmedia import BrollConfig, parse_crop, run_ffmpeg

ASPECT_TOLERANCE = 0.01
MOVE_MARGIN_PX = 16


def frames(seconds: float, fps: float) -> int:
    return round(seconds * fps)


def window_frames(ov: Overlay, fps: float) -> int:
    """Frames the overlay owns on the output frame grid (same rounding as the timeline cut)."""
    return frames(ov.end, fps) - frames(ov.start, fps)


def full_box(w: int, h: int) -> Box:
    return Box(x=0, y=0, w=w, h=h)


def target_box(ov: Overlay, w: int, h: int) -> Box:
    return ov.box if ov.mode == "pip" else full_box(w, h)


def content_size(ov: Overlay, w: int, h: int) -> tuple[int, int]:
    """Render the pictures at the larger of the two boxes, so a move only ever scales DOWN."""
    tb = target_box(ov, w, h)
    if ov.from_box is None:
        return tb.w, tb.h
    fb = ov.from_box
    if abs(fb.w / fb.h - tb.w / tb.h) > ASPECT_TOLERANCE * (tb.w / tb.h):
        raise ValueError(f"{ov.id}: from_box {fb.w}x{fb.h} and box {tb.w}x{tb.h} differ in aspect — a move cannot distort the picture")
    big = fb if fb.w * fb.h > tb.w * tb.h else tb
    return big.w - big.w % 2, big.h - big.h % 2


def grid_cells(cw: int, ch: int, cols: int, rows: int, gap: int) -> list[tuple[int, int, int, int]]:
    """(x, y, w, h) per cell, row-major, inside a cw x ch picture with `gap` px gutters."""
    cell_w = (cw - (cols + 1) * gap) // cols
    cell_h = (ch - (rows + 1) * gap) // rows
    return [
        (gap + c * (cell_w + gap), gap + r * (cell_h + gap), cell_w - cell_w % 2, cell_h - cell_h % 2)
        for r in range(rows) for c in range(cols)
    ]


def _crop(spec: str | None) -> str:
    if spec is None:
        return ""
    w, h, x, y = parse_crop(spec)
    return f"crop={w}:{h}:{x}:{y},"


def _cover(cw: int, ch: int) -> str:
    return f"scale={cw}:{ch}:force_original_aspect_ratio=increase:flags=lanczos,crop={cw}:{ch},"


def _zoom(shot: Shot, cw: int, ch: int, n: int, fps: float) -> str:
    if shot.zoom is None:
        return ""
    z0, z1 = shot.zoom
    return (
        f"scale={cw * 2}:{ch * 2}:flags=lanczos,"
        f"zoompan=z='{z0}+({z1}-{z0})*on/{max(n - 1, 1)}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        f":d=1:s={cw}x{ch}:fps={fps:g},"
    )


def _tb(fps: float) -> str:
    f = Fraction(fps).limit_denominator(1001)
    return f"settb={f.denominator}/{f.numerator}"


class Graph:
    """Collects ffmpeg inputs and filter chains for one layer."""

    def __init__(self) -> None:
        self.inputs: list[str] = []
        self.chains: list[str] = []
        self._n = 0
        self._n_labels = 0

    def add_input(self, args: list[str]) -> int:
        self.inputs += args
        self._n += 1
        return self._n - 1

    def label(self, stem: str) -> str:
        self._n_labels += 1
        return f"{stem}{self._n_labels}"


def _still_input(g: Graph, path: Path, seconds: float, fps: float) -> int:
    return g.add_input(["-loop", "1", "-framerate", f"{fps:g}", "-t", f"{seconds + 1.0:.6f}", "-i", str(path)])


def shot_chain(g: Graph, shot: Shot, broll: Path, cw: int, ch: int, n: int, fps: float, cfg: BrollConfig) -> str:
    """Add the filters for one shot (cw x ch, exactly n frames, yuv420p) and return its label."""
    out = g.label("shot")
    tail = f"trim=end_frame={n},setpts=PTS-STARTPTS,format=yuv420p,setsar=1,{_tb(fps)}[{out}]"
    if shot.grid is not None:
        gd = shot.grid
        base = g.label("grid")
        g.chains.append(f"color=c={cfg.grid.background}:s={cw}x{ch}:r={fps:g}:d={n / fps + 1.0:.6f},format=yuva420p[{base}]")
        cells = grid_cells(cw, ch, gd.cols, gd.rows, cfg.grid.gap_px)
        cur = base
        for tile, (x, y, w, h) in zip(gd.tiles, cells):
            idx = _still_input(g, broll / tile.asset, n / fps, fps)
            t = g.label("tile")
            pop = cfg.grid.tile_pop_frames / fps
            g.chains.append(
                f"[{idx}:v]fps={fps:g},{_crop(tile.crop)}{_cover(w, h)}format=yuva420p,"
                f"fade=t=in:st={tile.at:.6f}:d={pop:.6f}:alpha=1,setpts=PTS-STARTPTS[{t}]"
            )
            nxt = g.label("grid")
            g.chains.append(f"[{cur}][{t}]overlay=x={x}:y={y}:format=auto:shortest=1[{nxt}]")
            cur = nxt
        g.chains.append(f"[{cur}]{tail}")
        return out
    path = broll / shot.asset
    if path.suffix.lower() in STILL_EXTS:
        idx = _still_input(g, path, n / fps, fps)
        g.chains.append(f"[{idx}:v]fps={fps:g},{_crop(shot.crop)}{_cover(cw, ch)}{_zoom(shot, cw, ch, n, fps)}{tail}")
        return out
    idx = g.add_input(["-ss", f"{shot.src_in:.6f}", "-t", f"{shot.src_out - shot.src_in:.6f}", "-i", str(path)])
    g.chains.append(
        f"[{idx}:v]setpts=(PTS-STARTPTS)/{shot.speed:g},fps={fps:g},{_crop(shot.crop)}{_cover(cw, ch)}"
        f"{_zoom(shot, cw, ch, n, fps)}tpad=stop_mode=clone:stop=-1,{tail}"
    )
    return out


def _ease(t_expr: str, seconds: float) -> str:
    """Smoothstep 0→1 over `seconds`, as an ffmpeg expression in `t_expr`."""
    p = f"clip({t_expr}/{seconds:.6f},0,1)"
    return f"({p}*{p}*(3-2*{p}))"


def build_picture_layer(ov: Overlay, clip_dir: Path, w: int, h: int, fps: float, cfg: BrollConfig, out: Path) -> None:
    """Render one fullscreen/pip overlay to a transparent W x H FFV1 layer of its window length."""
    if ov.layer != "picture":
        raise ValueError(f"{ov.id}: build_picture_layer renders fullscreen/pip only, got {ov.mode}")
    if out.exists():
        raise FileExistsError(f"{out} exists — layers are rebuilt per render version, never overwritten")
    broll = clip_dir / "broll"
    n_win = window_frames(ov, fps)
    cw, ch = content_size(ov, w, h)
    g = Graph()

    labels: list[str] = []
    starts = [frames(s.at, fps) for s in ov.shots]
    for k, shot in enumerate(ov.shots):
        end = starts[k + 1] if k + 1 < len(ov.shots) else n_win
        ext = max(ov.shots[k + 1].dissolve_frames, 1) if k + 1 < len(ov.shots) else 0
        labels.append(shot_chain(g, shot, broll, cw, ch, end - starts[k] + ext, fps, cfg))
    cur = labels[0]
    for k in range(1, len(labels)):
        d = max(ov.shots[k].dissolve_frames, 1) / fps
        nxt = g.label("mix")
        g.chains.append(f"[{cur}][{labels[k]}]xfade=transition=fade:duration={d:.6f}:offset={starts[k] / fps:.6f}[{nxt}]")
        cur = nxt

    border = cfg.pip.border_px if ov.mode == "pip" else 0
    pic = g.label("pic")
    g.chains.append(
        f"[{cur}]trim=end_frame={n_win},setpts=PTS-STARTPTS,format=rgba"
        + (f",pad=iw+{2 * border}:ih+{2 * border}:{border}:{border}:color={cfg.pip.border_color}" if border else "")
        + f"[{pic}]"
    )
    tb = target_box(ov, w, h)
    placed = g.label("placed")
    if ov.from_box is None:
        canvas = g.label("canvas")
        g.chains.append(f"color=c=black@0.0:s={w}x{h}:r={fps:g}:d={n_win / fps:.6f},format=rgba[{canvas}]")
        g.chains.append(f"[{canvas}][{pic}]overlay=x={tb.x - border}:y={tb.y - border}:format=auto:shortest=1[{placed}]")
    else:
        # A box that changes size every frame cannot go through scale+overlay (overlay drops frames
        # whose size changes — measured: the first 0.3 s of a fullscreen→pip move rendered empty).
        # Instead the bordered picture is stretched to the full frame and `perspective` maps its
        # corners onto the eased box each frame; everything outside the box has alpha 0.
        fb, n_move = ov.from_box, ov.move_frames
        # `perspective` replicates the input's edge pixels outside the mapped quad, so the picture
        # is first framed by a transparent margin; the margin's corners are what get mapped.
        m = MOVE_MARGIN_PX
        inner_w, inner_h = w - 2 * m, h - 2 * m

        def corners(b: Box) -> tuple[float, float, float, float]:
            bx, by, bw, bh = b.x - border, b.y - border, b.w + 2 * border, b.h + 2 * border
            sx, sy = bw / inner_w, bh / inner_h
            return bx - m * sx, by - m * sy, bx + bw + m * sx, by + bh + m * sy

        p = f"clip(in/{n_move},0,1)"
        e = f"({p}*{p}*(3-2*{p}))"
        lerp = lambda a, b: f"({a:.3f}+({b - a:.3f})*{e})"  # noqa: E731
        (fx0, fy0, fx1, fy1), (tx0, ty0, tx1, ty1) = corners(fb), corners(tb)
        x0, y0, x1, y1 = lerp(fx0, tx0), lerp(fy0, ty0), lerp(fx1, tx1), lerp(fy1, ty1)
        g.chains.append(
            f"[{pic}]scale={inner_w}:{inner_h}:flags=bicubic,format=yuva444p,"
            f"pad={w}:{h}:{m}:{m}:color=black@0.0,"
            f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':x2='{x0}':y2='{y1}':x3='{x1}':y3='{y1}'"
            f":sense=destination:eval=frame:interpolation=cubic,format=rgba[{placed}]"
        )
    fades = []
    if ov.fade_in_frames:
        fades.append(f"fade=t=in:st=0:d={ov.fade_in_frames / fps:.6f}:alpha=1")
    if ov.fade_out_frames:
        fades.append(f"fade=t=out:st={(n_win - ov.fade_out_frames) / fps:.6f}:d={ov.fade_out_frames / fps:.6f}:alpha=1")
    g.chains.append(f"[{placed}]format=rgba,{','.join(fades) + ',' if fades else ''}trim=end_frame={n_win},setpts=PTS-STARTPTS[layer]")

    out.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [*g.inputs, "-filter_complex", ";".join(g.chains), "-map", "[layer]",
         "-c:v", "ffv1", "-pix_fmt", "bgra", "-r", f"{fps:g}", "-frames:v", str(n_win), str(out)],
        what=f"building picture overlay {ov.id} ({ov.mode}, {ov.duration:.2f}s)",
    )


def composite_filters(base: str, layers: list[tuple[int, Overlay]], fps: float) -> tuple[list[str], str]:
    """Chains that overlay each (input index, overlay) layer at its window. Returns (chains, out label)."""
    chains: list[str] = []
    cur = base
    for n, (idx, ov) in enumerate(layers):
        start = frames(ov.start, fps) / fps
        end = frames(ov.end, fps) / fps
        shifted, nxt = f"ol{n}", f"comp{n}"
        chains.append(f"[{idx}:v]setpts=PTS-STARTPTS+{start:.6f}/TB[{shifted}]")
        chains.append(
            f"[{cur}][{shifted}]overlay=x=0:y=0:eof_action=pass:format=auto"
            f":enable='between(t,{start - 0.5 / fps:.6f},{end - 0.5 / fps:.6f})'[{nxt}]"
        )
        cur = nxt
    return chains, cur
