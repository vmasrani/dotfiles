#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""Stage 8 step 4 — cut every A-roll timeline segment into `assets/aroll/`.

Source selection per segment:

* `closeup-<speaker>` / `reaction-<speaker>` — if that speaker has a `camera_file`,
  the isolated camera is used and the source range is shifted by the sync offset
  (`camera_t = episode_t - offset_s`). An unverified, missing or gap-crossing sync
  entry is a hard refusal: unverified sync means unusable footage, never a silent
  fall back to the published frame.
* everything else — the segment's own `source_file`.

Framing: the speaker's `preferred_crop` when set, otherwise a treatment-appropriate
centre crop. Output geometry follows the Remotion composition's contract
(remotion/gen-props.mjs):

* `closeup-<speaker>` / `reaction-<speaker>` → `<segment-id>.mp4` at the profile's
  exact resolution (1080x1920).
* `splitscreen` → `<segment-id>-top.mp4` + `<segment-id>-bottom.mp4`, one per-speaker
  panel each, at target width × half target height (1080x960); the composition stacks
  them. Top is the left half of the source frame, bottom the right half.
* `source-frame` → `<segment-id>.mp4`, the full frame at the profile width with its
  own aspect kept; the composition letterboxes it.

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

from pslib import (
    EPSILON,
    Clip,
    Episode,
    Speaker,
    SyncEntry,
    TimelineSegment,
    ffprobe_media,
    fmt_range,
    load_clip,
    load_episode,
)
from psmedia import (
    center_crop,
    episode_root_for,
    even,
    ff_time,
    fmt_crop,
    load_config,
    media_path,
    parse_crop,
    probe_dims,
    probed_duration,
    profile_dims,
    resolve_profile,
    run_ffmpeg,
    validate_crop_within,
)

console = Console()
app = typer.Typer(add_completion=False)

SPEAKER_TREATMENTS = ("closeup-", "reaction-")


@dataclass
class Job:
    """One output file: a source range, a crop, and a target geometry."""

    segment: TimelineSegment
    name: str                       # output basename without extension
    source_rel: str                 # path relative to the episode root
    source_path: Path
    source_in: float
    source_out: float
    crop: tuple[int, int, int, int]  # w, h, x, y
    fit: str                        # "profile" (exact WxH) | "width" (profile width, free height)
    origin: str                     # human-readable note for the report

    @property
    def duration(self) -> float:
        return self.source_out - self.source_in


# ---------------------------------------------------------------------------
# Source selection
# ---------------------------------------------------------------------------


def treatment_speaker(seg: TimelineSegment) -> str | None:
    for prefix in SPEAKER_TREATMENTS:
        if seg.visual.treatment.startswith(prefix):
            return seg.visual.treatment[len(prefix):]
    return None


def speaker_by_id(episode: Episode, sid: str, where: str) -> Speaker:
    match = [s for s in episode.speakers if s.id == sid]
    if not match:
        raise ValueError(f"{where}: speaker {sid!r} is not in episode.yaml speakers ({sorted(episode.speaker_ids())})")
    return match[0]


def sync_for(episode: Episode, camera_file: str) -> SyncEntry | None:
    match = [s for s in episode.sync if s.file == camera_file]
    if len(match) > 1:
        raise ValueError(f"episode.yaml has {len(match)} sync entries for {camera_file}")
    return match[0] if match else None


def camera_range(sync: SyncEntry, seg: TimelineSegment) -> tuple[float, float]:
    """Episode-time range → camera-time range. Camera t0 occurs `offset_s` after episode t0."""
    return seg.source_in - sync.offset_s, seg.source_out - sync.offset_s


def resolve_source(seg: TimelineSegment, episode: Episode) -> tuple[str, float, float, str, list[str]]:
    """(source_rel, source_in, source_out, origin, refusals) for one A-roll segment."""
    sid = treatment_speaker(seg)
    if sid is None:
        return seg.source_file, seg.source_in, seg.source_out, "segment source_file", []

    speaker = speaker_by_id(episode, sid, seg.id)
    if speaker.camera_file is None:
        return seg.source_file, seg.source_in, seg.source_out, f"segment source_file (no camera for {sid})", []

    sync = sync_for(episode, speaker.camera_file)
    if sync is None:
        return "", 0.0, 0.0, "", [
            f"{seg.id}: speaker {sid} has camera_file {speaker.camera_file} but episode.yaml has no sync "
            f"entry for it — run scripts/sync_cameras.py and verify it before rendering"
        ]
    if not sync.verified:
        return "", 0.0, 0.0, "", [
            f"{seg.id}: sync for {sync.file} is not verified (confidence {sync.confidence:.2f}, "
            f"method {sync.method}) — verify it (`sync_cameras.py verify`, then set verified: true) "
            f"or change {seg.id}'s treatment away from {seg.visual.treatment}"
        ]

    cam_in, cam_out = camera_range(sync, seg)
    refusals = []
    if cam_in < -EPSILON:
        refusals.append(
            f"{seg.id}: source range {fmt_range(seg.source_in, seg.source_out)} maps to camera time "
            f"{cam_in:.3f}s in {sync.file} at offset {sync.offset_s:+.3f}s — before the camera started rolling"
        )
    cam_duration = probed_duration(episode, sync.file)
    if cam_out > cam_duration + EPSILON:
        refusals.append(
            f"{seg.id}: maps to camera time {cam_out:.3f}s in {sync.file}, past its probed "
            f"duration {cam_duration:.3f}s"
        )
    for gap in sync.gaps:
        if cam_in < gap.camera_s + gap.duration_s and cam_out > gap.camera_s:
            refusals.append(
                f"{seg.id}: camera range {cam_in:.3f}-{cam_out:.3f}s crosses a recorded discontinuity in "
                f"{sync.file} at {gap.camera_s:.3f}s (+{gap.duration_s:.3f}s) — the sync offset is not valid there"
            )
    origin = f"{sync.file} @ offset {sync.offset_s:+.3f}s"
    return sync.file, cam_in, cam_out, origin, refusals


# ---------------------------------------------------------------------------
# Framing
# ---------------------------------------------------------------------------


def panel_crops(
    src_w: int, src_h: int, panel_w: int, panel_h: int, speakers: list[Speaker], where: str
) -> list[tuple[str, tuple[int, int, int, int], str]]:
    """The two split-screen panels: (suffix, crop, note), top = left half, bottom = right half.

    Each panel is one speaker's framing at the panel aspect. A speaker's
    `preferred_crop` wins for the half it lies inside (that is what the director set
    it for); otherwise the half is centre-cropped to the panel aspect. Two preferred
    crops inside the same half is a manifest ambiguity, not something to pick between.
    """
    half = even(src_w // 2)
    panels = []
    for suffix, origin in (("top", 0), ("bottom", src_w - half)):
        inside = [
            s for s in speakers
            if s.preferred_crop
            and (lambda c: origin <= c[2] and c[2] + c[0] <= origin + half)(parse_crop(s.preferred_crop))
        ]
        if len(inside) > 1:
            raise ValueError(
                f"{where}: speakers {[s.id for s in inside]} both have a preferred_crop inside the "
                f"{suffix} half of the frame — one panel cannot show two speakers; fix the crops in episode.yaml"
            )
        if inside:
            panels.append((suffix, parse_crop(inside[0].preferred_crop), f"preferred_crop({inside[0].id})"))
            continue
        w, h, x, y = center_crop(half, even(src_h), panel_w, panel_h)
        panels.append((suffix, (w, h, origin + x, y), f"centre {panel_w}:{panel_h} of the {suffix} half"))
    return panels


def build_jobs(
    clip: Clip, episode: Episode, episode_root: Path, out_w: int, out_h: int, aspect_w: int, aspect_h: int,
    blur_fill_aspect: tuple[int, int] = (4, 5),
) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    refusals: list[str] = []
    for seg in clip.timeline:
        if seg.visual.kind != "aroll":
            continue
        source_rel, src_in, src_out, origin, seg_refusals = resolve_source(seg, episode)
        refusals += seg_refusals
        if seg_refusals:
            continue
        source_path = media_path(episode_root, source_rel)
        src_w, src_h = probe_dims(episode, source_rel)
        treatment = seg.visual.treatment
        sid = treatment_speaker(seg)

        if treatment == "splitscreen":
            panel_w, panel_h = out_w, even(out_h // 2)
            for suffix, crop, note in panel_crops(src_w, src_h, panel_w, panel_h, episode.speakers, seg.id):
                validate_crop_within(crop, src_w, src_h, f"{seg.id} ({suffix})")
                jobs.append(Job(seg, f"{seg.id}-{suffix}", source_rel, source_path, src_in, src_out,
                                crop, "half", f"{origin} — {note}"))
            continue

        if treatment == "source-frame":
            crop = (even(src_w), even(src_h), 0, 0)
            fit = "width"
            note = "full frame"
        elif treatment.startswith("blur-fill-"):
            # Blur-fill keeps the SOURCE'S FULL HEIGHT — so a head is never cropped — but
            # narrows the width to an intermediate aspect before the composition blurs the
            # remainder in behind it. The aspect is the whole design decision:
            #
            #   16:9 (the raw frame) -> a 1080x608 band, face ~25% of frame height. That is
            #     the letterbox failure with a prettier backdrop; measured on this episode.
            #   9:16 (a full crop)   -> face ~69-72%, and the head clips when the speaker
            #     leans forward. This is what blur-fill exists to avoid.
            #   4:5  (the default)   -> a 1080x1350 band filling ~70% of frame height, face
            #     ~45-50%, full source height retained. Head complete AND large enough to read.
            #
            # Per-segment `visual.crop` still wins where a speaker has moved.
            bf_w, bf_h = blur_fill_aspect
            if seg.visual.crop:
                crop = parse_crop(seg.visual.crop)
                note = f"segment crop (blur-fill {bf_w}:{bf_h})"
            else:
                crop = center_crop(src_w, src_h, bf_w, bf_h)
                note = f"blur-fill {bf_w}:{bf_h}"
            fit = "width"
        elif sid is not None:
            speaker = speaker_by_id(episode, sid, seg.id)
            if seg.visual.crop:
                crop = parse_crop(seg.visual.crop)
                note = f"segment crop({sid})"
            elif speaker.preferred_crop:
                crop = parse_crop(speaker.preferred_crop)
                note = f"preferred_crop({sid})"
            else:
                crop = center_crop(src_w, src_h, aspect_w, aspect_h)
                note = f"centre {aspect_w}:{aspect_h}"
            fit = "profile"
        else:
            refusals.append(
                f"{seg.id}: unsupported aroll treatment {treatment!r} — expected "
                f"closeup-<speaker>|reaction-<speaker>|splitscreen|source-frame"
            )
            continue

        validate_crop_within(crop, src_w, src_h, seg.id)
        jobs.append(Job(seg, seg.id, source_rel, source_path, src_in, src_out, crop, fit,
                        f"{origin} — {note}"))
    return jobs, refusals


def expected_dims(job: Job, out_w: int, out_h: int) -> tuple[int, int]:
    """The exact output geometry — computed here, never left to ffmpeg's `-2` rounding.

    `profile` fills the whole target frame, `half` one split-screen panel (the
    Remotion composition stacks two of them), `width` keeps the source aspect at the
    target width and lets the composition letterbox it.
    """
    if job.fit == "profile":
        return out_w, out_h
    if job.fit == "half":
        return out_w, even(out_h // 2)
    w, h, _, _ = job.crop
    return out_w, max(2, even(int(round(out_w * h / w))))


def filter_chain(job: Job, out_w: int, out_h: int, fps: float) -> str:
    w, h, x, y = job.crop
    want_w, want_h = expected_dims(job, out_w, out_h)
    chain = [f"crop={w}:{h}:{x}:{y}"]
    if job.fit == "width":
        chain.append(f"scale={want_w}:{want_h}")
    else:
        chain += [
            f"scale={want_w}:{want_h}:force_original_aspect_ratio=decrease",
            f"pad={want_w}:{want_h}:(ow-iw)/2:(oh-ih)/2",
        ]
    chain += ["setsar=1", f"fps={fps:g}"]
    return ",".join(chain)


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
            "-vf", filter_chain(job, out_w, out_h, fps),
            "-c:v", "libx264", "-crf", str(crf), "-preset", "medium",
            "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-movflags", "+faststart",
            str(out_path),
        ],
        what=f"cutting {job.name} from {job.source_rel}",
    )


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    profile_name: str = typer.Option("youtube-shorts", "--profile", help="Platform profile name from episode.yaml"),
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
    load_config(config_path)  # fails loudly if the pipeline config is missing/malformed

    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")
    profile = resolve_profile(episode, profile_name)
    out_w, out_h = profile_dims(profile)
    aspect_w, aspect_h = (int(v) for v in profile.aspect.split(":"))

    jobs, refusals = build_jobs(clip, episode, root, out_w, out_h, aspect_w, aspect_h)
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
            fmt_range(job.source_in, job.source_out), fmt_crop(job.crop),
            f"{probe.width}x{probe.height}@{probe.fps:g}", f"{probe.duration_s:.3f}s",
        )
    console.print(table)

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
