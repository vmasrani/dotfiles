#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Stage 8 step 4 — cut every A-roll timeline segment into `assets/aroll/`.

Source selection per speaker panel:

* the speaker has a `camera_file` — that isolated camera is used and the source range is shifted
  by the sync offset (`camera_t = episode_t - offset_s`). An unverified, missing or gap-crossing
  sync entry is a hard refusal: unverified sync means unusable footage, never a silent fall back
  to the published frame.
* otherwise — the segment's own `source_file` (a shared, multi-person frame).

Framing is COMPUTED PER SEGMENT from where the speaker's face is (scripts/facelib.py): YuNet
face detection on frames sampled across the segment's source range, the speaker's face picked
by transcript-derived identity on a shared frame (or the largest face on an isolated camera),
and a crop centred on their median face position at the output aspect, with head room, kept
inside their own tile. No stored crop is read: `episode.yaml speakers[].preferred_crop` is not
used. A speaker whose face cannot be found in a segment is a hard refusal — there is no centre-
crop fallback. `visual.crop` (a per-segment override set by hand) still wins for a closeup.
Detections are cached under `clips/<slug>/assets/faces/`.

A closeup frames head and shoulders: the face box is ~30% of the frame height, the eye line sits at
~0.30-0.36, and the source crop is never magnified beyond `framing.max_upscale` (config, default 2.0).
When the speaker's tile cannot supply a full 9:16 window at that scale, the output is BLUR-FILLED —
the sharp crop at its true scale over a blurred, darkened copy of itself — baked into the segment's mp4
(same file name and treatment, so the manifest and the Remotion props are unchanged). A face that
cannot be found is still a hard refusal.

Alongside the cuts it writes `assets/aroll/layout.json`: per file and shot, the nose-to-chin band in
output pixels, which `align_subtitles.py` / `validate_subtitles.py` use to keep split-screen captions
off every mouth (scripts/capplace.py).

Output geometry follows the Remotion composition's contract (remotion/gen-props.mjs):

* `closeup-<speaker>` → `<segment-id>.mp4` at the profile's exact resolution (1080x1920).
* `splitscreen` → `<segment-id>-top.mp4` + `<segment-id>-bottom.mp4`, one per-speaker
  panel each, at target width × half target height (1080x960); the composition stacks
  them. `visual.speakers` = [top, bottom] picks WHICH speaker's face goes in each panel.

Horizontal clips (`format: clip`) are not handled here; see render_horizontal.py.

Video only (`-an`): the audio track of the finished clip comes from
assemble_audio.py, never from these staged cuts.
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
from framer import Framer, resolve_source
from pslib import EPSILON, Clip, Episode, TimelineSegment, ffprobe_media, fmt_range, load_clip, load_episode
from psmedia import (
    episode_root_for,
    even,
    ff_time,
    load_config,
    media_path,
    parse_crop,
    probe_dims,
    profile_dims,
    resolve_profile,
    run_ffmpeg,
    validate_crop_within,
)

console = Console()
app = typer.Typer(add_completion=False)

SPEAKER_TREATMENTS = ("closeup-",)


@dataclass
class Job:
    """One output file: a source range, a crop schedule, and a target geometry."""

    segment: TimelineSegment
    name: str                       # output basename without extension
    source_rel: str                 # path relative to the episode root
    source_path: Path
    source_in: float
    source_out: float
    shots: list[facelib.Shot]       # crop windows over source time (one per layout; a moving window pans)
    fit: str                        # "profile" (exact WxH) | "half" (one split-screen panel)
    origin: str                     # human-readable note for the report

    @property
    def duration(self) -> float:
        return self.source_out - self.source_in


# ---------------------------------------------------------------------------
# Treatment -> jobs
# ---------------------------------------------------------------------------


def treatment_speaker(seg: TimelineSegment) -> str | None:
    for prefix in SPEAKER_TREATMENTS:
        if seg.visual.treatment.startswith(prefix):
            return seg.visual.treatment[len(prefix):]
    return None


def static_shot(seg_in: float, seg_out: float, crop: tuple[int, int, int, int]) -> facelib.Shot:
    w, h, x, y = crop
    return facelib.Shot(seg_in, seg_out, w, h, [(seg_in, x, y)])


def build_jobs(
    clip: Clip, episode: Episode, episode_root: Path, clip_dir: Path, out_w: int, out_h: int, max_upscale: float,
) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
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
            for suffix, panel_sid in zip(("top", "bottom"), names):
                source = resolve_source(seg, episode, panel_sid)
                refusals += source[4]
                if source[4]:
                    continue
                source_rel, src_in, src_out, origin, _, isolated = source
                shots = framed(seg, panel_sid, source, "panel", panel_h)
                if shots is None:
                    continue
                jobs.append(Job(seg, f"{seg.id}-{suffix}", source_rel, media_path(episode_root, source_rel), src_in, src_out,
                                shots, "half", f"{origin} — {suffix} = {panel_sid} ({'own camera' if isolated else 'shared frame'})"))
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
            shots = [static_shot(src_in, src_out, parse_crop(seg.visual.crop))]
            note = f"{sid} (visual.crop override)"
        else:
            shots = framed(seg, sid, source, "closeup", out_h)
            note = f"{sid} ({'own camera' if isolated else 'shared frame'})"
        if shots is None:
            continue
        jobs.append(Job(seg, seg.id, source_rel, media_path(episode_root, source_rel), src_in, src_out, shots, "profile",
                        f"{origin} — {note}"))

    for job in jobs:
        src_w, src_h = probe_dims(episode, job.source_rel)
        for shot in job.shots:
            for _, x, y in shot.keys:
                validate_crop_within((shot.w, shot.h, x, y), src_w, src_h, job.name)
    return jobs, refusals


def expected_dims(job: Job, out_w: int, out_h: int) -> tuple[int, int]:
    """The exact output geometry — computed here, never left to ffmpeg's `-2` rounding.

    `profile` fills the whole target frame, `half` one split-screen panel (the
    Remotion composition stacks two of them).
    """
    return (out_w, out_h) if job.fit == "profile" else (out_w, even(out_h // 2))


def pan_expr(shot: facelib.Shot, axis: int) -> str:
    """ffmpeg expression for the crop window's x (axis 1) or y (axis 2) at shot-relative time `t`."""
    keys = [(round(k[0] - shot.t0, 3), k[axis]) for k in shot.keys]
    expr = str(keys[-1][1])
    for (ta, va), (tb, vb) in reversed(list(zip(keys, keys[1:]))):
        expr = f"if(lt(t,{tb}),{va}+({vb}-{va})*(t-{ta})/{tb - ta:.3f},{expr})"
    return expr if len(keys) == 1 else f"'{expr}'"


def shot_graph(shot: facelib.Shot, src: str, dst: str, want_w: int, want_h: int) -> str:
    """Filter-graph fragment `[src]` -> `[dst]` that frames one shot at want_w x want_h.

    A blur-fill shot (`shot.dst`) draws the sharp crop at its true scale over a copy of itself that is scaled to
    cover the frame at 1/BLUR_SCALE size, blurred, darkened and scaled back up (cheap: the blur runs on a thumbnail).
    """
    crop = f"crop={shot.w}:{shot.h}:{pan_expr(shot, 1)}:{pan_expr(shot, 2)}"
    if shot.dst is None:
        return (f"[{src}]{crop},scale={want_w}:{want_h}:force_original_aspect_ratio=decrease,"
                f"pad={want_w}:{want_h}:(ow-iw)/2:(oh-ih)/2,setsar=1[{dst}]")
    dx, dy, ow, oh = shot.dst
    bw, bh = want_w // facelib.BLUR_SCALE // 2 * 2, want_h // facelib.BLUR_SCALE // 2 * 2
    return (f"[{src}]{crop},split[{dst}a][{dst}b];"
            f"[{dst}a]scale={bw}:{bh}:force_original_aspect_ratio=increase,crop={bw}:{bh},gblur=sigma={facelib.BLUR_SIGMA:g},"
            f"lutyuv=y=val*{facelib.BLUR_BRIGHTNESS:g},scale={want_w}:{want_h}:flags=bilinear[{dst}bg];"
            f"[{dst}b]scale={ow}:{oh}:flags=lanczos[{dst}fg];"
            f"[{dst}bg][{dst}fg]overlay={dx}:{dy},setsar=1[{dst}]")


def filter_args(job: Job, out_w: int, out_h: int, fps: float) -> list[str]:
    """`-filter_complex` + `-map` for the job: one framed shot, or trim/frame/concat when the layout changes inside the segment."""
    want_w, want_h = expected_dims(job, out_w, out_h)
    if len(job.shots) == 1:
        graph = shot_graph(job.shots[0], "0:v", "s0", want_w, want_h) + f";[s0]fps={fps:g}[out]"
        return ["-filter_complex", graph, "-map", "[out]"]
    legs = [
        f"[0:v]trim=start={shot.t0 - job.source_in:.4f}:end={shot.t1 - job.source_in:.4f},setpts=PTS-STARTPTS[t{k}];"
        + shot_graph(shot, f"t{k}", f"v{k}", want_w, want_h)
        for k, shot in enumerate(job.shots)
    ]
    concat = "".join(f"[v{k}]" for k in range(len(job.shots))) + f"concat=n={len(job.shots)}:v=1:a=0,fps={fps:g}[out]"
    return ["-filter_complex", ";".join([*legs, concat]), "-map", "[out]"]


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract(job: Job, out_path: Path, out_w: int, out_h: int, fps: float, crf: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg(
        [
            # -ss BEFORE -i is input seeking: ffmpeg jumps to the prior keyframe and decodes
            # forward from there. With -ss after -i it decodes the file from frame 0 and
            # discards everything before source_in — on a 99-minute episode that cost ~107s
            # to cut a 3s segment. Input seeking has been frame-accurate since ffmpeg 2.1.
            # -t (duration) rather than -to, because -to after an input -ss is relative to
            # the post-seek timeline and silently produces the wrong length.
            "-ss", ff_time(job.source_in),
            "-i", str(job.source_path),
            "-t", ff_time(job.source_out - job.source_in),
            "-an", "-sn", "-dn",
            *filter_args(job, out_w, out_h, fps),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
            "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-movflags", "+faststart",
            str(out_path),
        ],
        what=f"cutting {job.name} from {job.source_rel}",
    )


def describe_shots(job: Job) -> str:
    def one(s: facelib.Shot) -> str:
        x, y = s.keys[0][1], s.keys[0][2]
        text = f"{s.w}x{s.h}@({x},{y})" + ("" if s.static else f" pan x{len(s.keys)}")
        if s.face_frac:
            text += f" {s.scale:.2f}x face {s.face_frac:.0%} eyes {s.eye_frac:.2f}"
        return text + (" BLUR-FILL" if s.blur_fill else "")
    return one(job.shots[0]) if len(job.shots) == 1 else f"{len(job.shots)} shots: " + " | ".join(
        f"{s.t0 - job.source_in:.1f}s {one(s)}" for s in job.shots)


def layout_entry(job: Job, panel_offset: int) -> dict:
    """The shots of one output file in CLIP time, with mouth bands in full-frame pixels (panel_offset = the panel's top)."""
    seg = job.segment
    return {
        "segment": seg.id, "treatment": seg.visual.treatment,
        "shots": [{
            "t0": round(seg.output_in + shot.t0 - job.source_in, 4), "t1": round(seg.output_in + shot.t1 - job.source_in, 4),
            "blur_fill": shot.blur_fill, "scale": round(shot.scale, 3), "face_frac": round(shot.face_frac, 3),
            "eye_frac": round(shot.eye_frac, 3),
            "mouth": None if shot.mouth == (0.0, 0.0) else [round(shot.mouth[0] + panel_offset, 1), round(shot.mouth[1] + panel_offset, 1)],
        } for shot in job.shots],
    }


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    profile_name: str = typer.Option("youtube-shorts", "--profile", help="Platform profile name from episode.yaml (format: short)"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"),
    config_path: Path = typer.Option(None, "--config", help="Pipeline config (default: config/defaults.yaml)"),
    crf: int = typer.Option(16, "--crf", help="x264 quality for the staged cuts (lower is better)"),
    out_dir: Path = typer.Option(Path("assets/aroll"), "--out-dir", help="Output directory, relative to CLIP_DIR"),
) -> None:
    """Cut, crop and normalise every A-roll segment of CLIP_DIR into assets/aroll/."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    root = episode_root_for(clip_dir, episode_root)
    config = load_config(config_path)  # fails loudly if the pipeline config is missing/malformed

    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")
    profile = resolve_profile(episode, profile_name)
    if profile.format != "short" or clip.clip.format != "short":
        raise typer.BadParameter(
            f"extract_segments.py is for shorts: profile {profile.name!r} is {profile.format!r}, clip "
            f"{clip.clip.id} is {clip.clip.format!r}. Horizontal clips render via render_horizontal.py."
        )
    out_w, out_h = profile_dims(profile)

    jobs, refusals = build_jobs(clip, episode, root, clip_dir, out_w, out_h, config.framing.max_upscale)
    if refusals:
        console.print("[bold red]REFUSED[/] — A-roll sources are not usable as the manifest asks:")
        for r in refusals:
            console.print(f"  [red]•[/] {r}")
        raise typer.Exit(1)
    if not jobs:
        raise typer.BadParameter(f"{clip.clip.id}: timeline has no aroll segments — nothing to extract")

    logger.info(
        f"clip={clip.clip.id} profile={profile.name} {out_w}x{out_h}@{profile.fps:g} "
        f"aroll_files={len(jobs)}"
    )

    table = RichTable(title=f"A-roll cuts — {clip.clip.id} @ {profile.name}", header_style="bold cyan")
    for column, kwargs in (
        ("Seg", {"no_wrap": True}), ("Treatment", {}), ("Source used", {}), ("Range", {"no_wrap": True}),
        ("Crop", {}), ("Output", {"no_wrap": True}), ("Duration", {"justify": "right"}),
    ):
        table.add_column(column, **kwargs)

    wanted = {f"{job.name}.mp4" for job in jobs}
    for stale in sorted(p for p in (clip_dir / out_dir).glob("*.mp4") if p.name not in wanted):
        logger.info(f"removing {stale.name} — no longer used by the timeline's current framing")
        stale.unlink()

    failures: list[str] = []
    for job in jobs:
        out_path = clip_dir / out_dir / f"{job.name}.mp4"
        extract(job, out_path, out_w, out_h, profile.fps, crf)
        probe = ffprobe_media(out_path)
        want_w, want_h = expected_dims(job, out_w, out_h)
        tolerance = EPSILON + 1.0 / profile.fps
        if (probe.width, probe.height) != (want_w, want_h):
            failures.append(f"{job.name}: {probe.width}x{probe.height}, expected {want_w}x{want_h}")
        if probe.fps is None or abs(probe.fps - profile.fps) > 0.01:
            failures.append(f"{job.name}: {probe.fps} fps, expected {profile.fps:g}")
        if abs(probe.duration_s - job.duration) > tolerance:
            failures.append(
                f"{job.name}: {probe.duration_s:.3f}s, expected {job.duration:.3f}s (±{tolerance:.3f}s)"
            )
        table.add_row(
            job.name, job.segment.visual.treatment, job.origin,
            fmt_range(job.source_in, job.source_out), describe_shots(job),
            f"{probe.width}x{probe.height}@{probe.fps:g}", f"{probe.duration_s:.3f}s",
        )
    console.print(table)

    panel_h = even(out_h // 2)
    layout = capplace.write_layout(clip_dir, clip, out_h, {
        job.name: layout_entry(job, panel_h if job.name.endswith("-bottom") else 0) for job in jobs})
    logger.info(f"wrote {layout}")

    if failures:
        console.print("[bold red]FAIL[/] staged cuts do not match the profile/timeline:")
        for f in failures:
            console.print(f"  [red]•[/] {f}")
        raise typer.Exit(1)
    console.print(
        f"[bold green]OK[/] {clip.clip.id}: {len(jobs)} A-roll file(s) → {clip_dir / out_dir} "
        f"(h264 crf {crf}, {profile.fps:g} fps, no audio)"
    )


if __name__ == "__main__":
    app()
