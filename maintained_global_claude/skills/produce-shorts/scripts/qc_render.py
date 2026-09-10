#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "pysubs2>=1.7",
# ]
# ///
"""Stage 9 — automated QC of a rendered clip.

Writes `qc-v<N>.json` (schema in `references/schemas.md`) next to `clip.yaml` and exits
nonzero when any check fails. Every check below appears in the `checks` array on every
run, passed or not: a check that produced no finding is visible evidence that it ran,
never an absence. A check that *cannot* run (missing tool, unparseable filter output)
raises — it is never silently downgraded to a pass.

**The subject is the per-profile encode** (stage 8 step 6), i.e.
`render.versions[N].finals[<profile>]` — never the raw Remotion master in
`versions[N].preview`. The master is an intermediate: it can carry a full-range pix_fmt
tag (`yuvj420p`) and other properties the profile does not specify, so judging it against
a platform profile would produce fabricated failures. Nothing here asserts pix_fmt or
colour range for that reason; `--render` exists to QC a profile encode *before* the
manifest records it, not to point QC at a master.

Checks (`references/render-qc.md` § Stage 9):

    container_matches_profile  streams present; codec/resolution/fps/aspect/container
    duration_matches_manifest  container vs clip.output.duration_s, audio vs video stream
    black_frames               blackdetect; intervals fail unless the storyboard plans them
    frozen_frames              freezedetect (-60dB, >= 1.5s); same storyboard exemption
    loudness                   ebur128 integrated LUFS +/- tolerance, true peak under ceiling
    clipping                   astats clipped-sample count == 0
    silence                    silencedetect >= 0.8s anywhere, plus a probe of every internal cut
    cut_points                 scene detection vs the timeline's hard cuts (crossfades exempt)
    subtitles_present          the aligned .ass exists and re-passes validate_subtitles
    assets_tracked             every assets[] file exists with a matching sha256
    manifest_agreement         rendered duration/fps/resolution vs clip.yaml output block

Plus a contact sheet (`renders/v<N>-contact-sheet.png`): one labelled frame at every
timeline boundary and every segment midpoint, tiled for human review.
"""

from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    EPSILON,
    TIMELINE_HEADERS,
    Clip,
    PlatformProfile,
    find_table,
    fmt_mmss,
    load_clip,
    load_episode,
    parse_md_tables,
    sha256_file,
)
from psmedia import PipelineConfig, episode_root_for, load_config, profile_dims, resolve_profile
from validate_subtitles import validate as validate_subtitle_script

console = Console()
app = typer.Typer(add_completion=False)

# --------------------------------------------------------------------------------------
# Thresholds — every magic number in one place, each with the rule it encodes
# --------------------------------------------------------------------------------------

#: Duration agreement window (container vs manifest, audio vs video). Tighter than a
#: frame at 30fps would be dishonest: a 30fps mp4 can only land on 33ms boundaries.
DURATION_TOLERANCE_S = 0.10

#: blackdetect: an all-black run at least this long is reported.
BLACK_MIN_DURATION_S = 0.10
BLACK_PIXEL_THRESHOLD = 0.10

#: freezedetect: identical frames within this noise floor for at least this long.
FREEZE_NOISE_DB = "-60dB"
FREEZE_MIN_DURATION_S = 1.5

#: silencedetect: a dropout anywhere in the clip.
SILENCE_NOISE_DB = "-50dB"
SILENCE_MIN_DURATION_S = 0.8

#: Internal cuts get a dedicated, stricter probe: a jump-cut click or a missing frame of
#: audio is far shorter than a whole-clip dropout, so the window threshold is lower.
CUT_WINDOW_S = 1.0
CUT_WINDOW_SILENCE_MIN_S = 0.25
#: How much longer than its source original a pause may measure before it counts as an
#: edit artifact. silencedetect places boundaries a few tens of ms apart on the render
#: (loudnorm + AAC) versus the raw source, so an exact comparison would fail on
#: measurement noise. A real splice inserts a discrete gap far larger than this.
NATURAL_PAUSE_TOLERANCE_S = 0.10
#: Noise floor used when re-probing the SOURCE to ask "was this quiet here anyway?".
#: Deliberately more permissive than SILENCE_NOISE_DB: the question is whether the speaker
#: had paused, not whether the source was digitally silent. Measured case — a pause reading
#: -54 dB mean in the source and -57 dB in the render sits either side of a -50 dB line and
#: would otherwise be reported as an edit artifact when nothing was edited. Speech sits far
#: above this, so a genuine hole (speech in the source, silence in the render) still fails.
SOURCE_SILENCE_NOISE_DB = "-45dB"

#: Scene-change detection for cut verification.
SCENE_THRESHOLD = 0.30
# A cut between two shots of the SAME locked-off camera cannot produce a 0.30 delta — the
# frames either side differ only by however much the speaker moved in the elided moment,
# so SCENE_THRESHOLD governs only what counts as an UNEXPECTED visual change. CONFIRMING
# an expected cut needs a much gentler test.
#
# That test cannot be a constant. How large a same-camera jump cut registers depends on the
# shot: how tight the crop is, how much the speaker moves, how noisy the sensor is. A fixed
# 0.08 was calibrated on one clip and then missed a real cut at 0.0789 on the next — while
# that same cut was the clear local maximum, 3.5x the clip's own noise. Calibrate against
# the clip instead: take every frame at least NOISE_EXCLUSION_S from ANY declared boundary
# (so neither the cut itself nor an adjacent one contaminates the sample) and use the 95th
# percentile of those as this render's noise floor.
#
# Measured over 15 declared hard cuts across two clips, every real cut landed at 3.5-68.6x
# p95 while a cut that failed to render would sit near 1.0x. 2.5x splits that gap with
# margin on both sides: the weakest real cut clears it by 38%, and the loudest noise
# percentile (p99, 1.7x) stays below it.
CONFIRM_NOISE_MULTIPLE = 2.5
#: Absolute safety net for a near-static render whose p95 noise is ~0, where a pure ratio
#: would confirm a cut from nothing. Below every real cut measured (min 0.0789).
SCENE_CONFIRM_FLOOR = 0.05
#: Frames this close to a declared boundary are excluded from the noise sample.
NOISE_EXCLUSION_S = 0.5
#: An expected cut must register a scene change within this distance of its output time.
CUT_MATCH_TOLERANCE_S = 0.25
#: A detected scene change further than this from ANY timeline boundary is unexpected.
#: At a `crossfade-<N>f` boundary the ramp length is ADDED to this window: the outgoing
#: segment holds N extra frames while the incoming one ramps opacity over it, so the
#: frame-to-frame delta peaks somewhere inside the ramp rather than on the boundary.
CUT_UNEXPECTED_TOLERANCE_S = 0.50

#: Frame-rate agreement (r_frame_rate is a rational; 29.97 vs 30 must still fail).
FPS_TOLERANCE = 0.05

#: Contact sheet geometry.
CONTACT_TILE_WIDTH = 320
CONTACT_TILE_PADDING = 6

#: drawtext needs a real font file; fontconfig is not guaranteed on a build machine.
FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]

#: A black or frozen interval is only acceptable when the plan asked for it
#: (`references/render-qc.md` § Stage 9). "The plan" means a segment's `visual.motion`,
#: `visual.treatment`, or the storyboard Timeline row's Visual cell, and it must say so
#: with one of these words — an overlapping interval passes only on an explicit match.
#: The vocabulary is deliberately narrow: a vague Visual cell must not excuse a defect.
BLACK_INTENT_WORDS = ("black",)
FREEZE_INTENT_WORDS = ("freeze", "frozen", "still", "black")


# --------------------------------------------------------------------------------------
# Result model
# --------------------------------------------------------------------------------------


@dataclass
class Check:
    name: str
    passed: bool
    detail: str

    def as_json(self) -> dict[str, object]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


@dataclass
class Interval:
    start: float
    end: float

    def overlaps(self, start: float, end: float) -> bool:
        return self.start < end - EPSILON and self.end > start + EPSILON

    def __str__(self) -> str:
        return f"{self.start:.2f}-{self.end:.2f}s"


# --------------------------------------------------------------------------------------
# Subprocess helpers
# --------------------------------------------------------------------------------------


@dataclass
class Run:
    stdout: str
    stderr: str

    @property
    def merged(self) -> str:
        return self.stdout + "\n" + self.stderr


def _run(cmd: list[str]) -> Run:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"command failed (exit {proc.returncode}): {' '.join(cmd)}\n{proc.stderr[-3000:]}"
        )
    return Run(stdout=proc.stdout, stderr=proc.stderr)


def ffmpeg_analyse(render: Path, args: list[str]) -> Run:
    """Run an analysis-only ffmpeg pass (null muxer) and hand back its full output."""
    return _run(["ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(render), *args, "-f", "null", "-"])


def ffprobe_json(path: Path) -> dict:
    run = _run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    )
    return json.loads(run.stdout)


def _dims(resolution: str, where: str) -> tuple[int, int]:
    """`"1080x1920"` -> (1080, 1920). psmedia.profile_dims does this for profiles; this is
    the same rule for the manifest's own `output.resolution` string."""
    w, _, h = resolution.lower().partition("x")
    if not w.strip().isdigit() or not h.strip().isdigit():
        raise ValueError(f"{where}: unparseable resolution {resolution!r} — expected WxH")
    return int(w), int(h)


def _fraction(value: str) -> float:
    num, _, den = value.partition("/")
    denom = float(den) if den else 1.0
    if denom == 0.0:
        raise ValueError(f"ffprobe returned a zero-denominator frame rate: {value!r}")
    return float(num) / denom


def _stream(probe: dict, kind: str) -> dict | None:
    return next((s for s in probe.get("streams", []) if s.get("codec_type") == kind), None)


def _stream_duration(stream: dict, label: str) -> float:
    raw = stream.get("duration") or stream.get("tags", {}).get("DURATION")
    if raw is None:
        raise RuntimeError(
            f"the {label} stream carries no duration — cannot verify stream agreement. "
            f"Re-mux the render with a container that records per-stream durations (mp4/mov)."
        )
    if ":" in str(raw):
        h, m, s = str(raw).split(":")
        return int(h) * 3600 + int(m) * 60 + float(s)
    return float(raw)


def find_font() -> str:
    for candidate in FONT_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise RuntimeError(
        "no usable TrueType font found for the contact sheet labels; looked for "
        f"{FONT_CANDIDATES}. Install one (e.g. `brew install --cask font-dejavu`) or add "
        "its path to FONT_CANDIDATES in qc_render.py."
    )


# --------------------------------------------------------------------------------------
# Filter output parsers — formats verified against ffmpeg 8.x
# --------------------------------------------------------------------------------------

_BLACK_RE = re.compile(r"black_start:\s*([\d.]+)\s+black_end:\s*([\d.]+)")
_FREEZE_START_RE = re.compile(r"freeze_start:\s*([\d.]+)")
_FREEZE_END_RE = re.compile(r"freeze_end:\s*([\d.]+)")
_SILENCE_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SILENCE_END_RE = re.compile(r"silence_end:\s*([\d.]+)")
_SCENE_TIME_RE = re.compile(r"pts_time:([\d.]+)")
#: metadata=print emits the timestamp and the score on separate lines; one alternation over
#: both keeps them in emission order so each score can be paired with the time above it.
_SCENE_FRAME_RE = re.compile(r"pts_time:([\d.]+)|scene_score=([\d.]+)")
_EBUR_I_RE = re.compile(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS")
_EBUR_PEAK_RE = re.compile(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+)\s*dBFS")
_ASTATS_RE = {
    "min": re.compile(r"Min level:\s*(-?[\d.]+)"),
    "max": re.compile(r"Max level:\s*(-?[\d.]+)"),
    "peak_db": re.compile(r"Peak level dB:\s*(-?[\d.]+|-?inf)"),
    "abs_peak_count": re.compile(r"Abs Peak count:\s*([\d.]+)"),
}


def _paired_intervals(starts: list[float], ends: list[float], eof: float) -> list[Interval]:
    """Zip detector start/end markers; an unterminated run ends at EOF, never silently dropped."""
    out: list[Interval] = []
    for n, start in enumerate(starts):
        end = ends[n] if n < len(ends) else eof
        out.append(Interval(start=start, end=end))
    return out


def detect_black(render: Path) -> list[Interval]:
    run = ffmpeg_analyse(
        render, ["-vf", f"blackdetect=d={BLACK_MIN_DURATION_S}:pix_th={BLACK_PIXEL_THRESHOLD}", "-an"]
    )
    return [Interval(float(a), float(b)) for a, b in _BLACK_RE.findall(run.merged)]


def detect_freeze(render: Path, eof: float) -> list[Interval]:
    run = ffmpeg_analyse(
        render, ["-vf", f"freezedetect=n={FREEZE_NOISE_DB}:d={FREEZE_MIN_DURATION_S}", "-an"]
    )
    starts = [float(v) for v in _FREEZE_START_RE.findall(run.merged)]
    ends = [float(v) for v in _FREEZE_END_RE.findall(run.merged)]
    return _paired_intervals(starts, ends, eof)


def detect_silence(
    render: Path, eof: float, min_duration: float, window: tuple[float, float] | None = None,
    noise_db: str = SILENCE_NOISE_DB,
) -> list[Interval]:
    pre = ["-ss", f"{window[0]:.3f}", "-t", f"{window[1] - window[0]:.3f}"] if window else []
    cmd = [
        "ffmpeg", "-nostdin", "-hide_banner", "-v", "info", *pre, "-i", str(render),
        "-af", f"silencedetect=n={noise_db}:d={min_duration}", "-vn", "-f", "null", "-",
    ]
    run = _run(cmd)
    offset = window[0] if window else 0.0
    starts = [float(v) + offset for v in _SILENCE_START_RE.findall(run.merged)]
    ends = [float(v) + offset for v in _SILENCE_END_RE.findall(run.merged)]
    limit = window[1] if window else eof
    return _paired_intervals(starts, ends, limit)


def scene_scores(render: Path) -> list[tuple[float, float]]:
    """Every frame's (time, scene score), for calibrating a confirm threshold per render.

    `select='gte(scene,0)'` passes every frame, so this is one decode of the whole file
    rather than one per threshold.
    """
    run = _run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-v", "info", "-i", str(render),
            "-vf", "select='gte(scene,0)',metadata=print", "-an", "-f", "null", "-",
        ]
    )
    out: list[tuple[float, float]] = []
    at: float | None = None
    for time_s, score in _SCENE_FRAME_RE.findall(run.merged):
        if time_s:
            at = float(time_s)
        elif at is not None:
            out.append((at, float(score)))
    if not out:
        raise RuntimeError(
            "no scene scores parsed — cut verification is unmeasured, which is not a pass. "
            f"ffmpeg output tail:\n{run.merged[-1500:]}"
        )
    return out


def confirm_threshold(scores: list[tuple[float, float]], boundaries: list[float]) -> float:
    """Scene-score floor above which a frame counts as confirming a declared cut.

    Derived from this render's own noise rather than assumed: how large a same-camera jump
    cut registers depends entirely on the shot. Frames near ANY boundary are excluded so
    that neither the cut under test nor an adjacent one inflates the floor it is judged by.
    """
    noise = sorted(
        v for t, v in scores if all(abs(t - b) > NOISE_EXCLUSION_S for b in boundaries)
    )
    if not noise:
        return SCENE_CONFIRM_FLOOR
    p95 = noise[min(len(noise) - 1, int(0.95 * len(noise)))]
    return max(SCENE_CONFIRM_FLOOR, CONFIRM_NOISE_MULTIPLE * p95)


def detect_scene_changes(render: Path, threshold: float = SCENE_THRESHOLD) -> list[float]:
    run = _run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-i", str(render),
            "-vf", f"select='gt(scene,{threshold})',metadata=print:file=-",
            "-an", "-f", "null", "-",
        ]
    )
    return sorted(float(v) for v in _SCENE_TIME_RE.findall(run.stdout))


def measure_loudness(render: Path) -> tuple[float, float]:
    """(integrated LUFS, true peak dBTP) from a single ebur128 pass."""
    run = ffmpeg_analyse(render, ["-af", "ebur128=peak=true", "-vn"])
    integrated = _EBUR_I_RE.search(run.merged)
    peak = _EBUR_PEAK_RE.search(run.merged)
    if integrated is None or peak is None:
        raise RuntimeError(
            "could not parse the ebur128 summary — loudness is unmeasured, which is not a pass. "
            f"ffmpeg output tail:\n{run.merged[-1500:]}"
        )
    return float(integrated.group(1)), float(peak.group(1))


def measure_clipping(render: Path) -> tuple[int, float]:
    """(clipped sample count, peak level dBFS).

    astats reports levels in the sample format it is handed, so the audio is forced to
    s16 first: every sample at or past full scale is clamped to exactly +/-32767/32768,
    which makes `Abs Peak count` the count of clipped samples whenever the peak sits on
    the rail. When both rails are hit the count is a lower bound — still nonzero, still
    a failure, which is all this check asserts.
    """
    run = ffmpeg_analyse(
        render, ["-af", "aformat=sample_fmts=s16,astats=measure_perchannel=none", "-vn"]
    )
    values = {}
    for key, pattern in _ASTATS_RE.items():
        match = pattern.search(run.merged)
        if match is None:
            raise RuntimeError(
                f"astats did not report `{key}` — clipping is unmeasured, which is not a pass. "
                f"ffmpeg output tail:\n{run.merged[-1500:]}"
            )
        values[key] = match.group(1)
    peak_db = -math.inf if values["peak_db"].endswith("inf") else float(values["peak_db"])
    on_rail = float(values["max"]) >= 32767.0 or float(values["min"]) <= -32768.0
    return (int(float(values["abs_peak_count"])) if on_rail else 0), peak_db


# --------------------------------------------------------------------------------------
# Timeline facts
# --------------------------------------------------------------------------------------


_CROSSFADE_RE = re.compile(r"^crossfade-(\d+)f$")


def transition_ramp_seconds(transition: str, fps: float, where: str) -> float:
    """Output seconds over which a transition's visual change is smeared.

    `cut` is 0 — an instantaneous, must-detect change. `crossfade-<N>f` is N/fps: the
    outgoing segment holds N extra frames while the incoming one ramps opacity on top,
    so the scene-detection spike (if any) lands inside the ramp, not on the boundary.
    The manifest cut point itself does not move and audio stays aligned.

    Any other value raises. An unrecognised transition must never quietly fall through
    to "treat as a crossfade" — that would silently exempt a real cut from detection.
    """
    value = transition.strip().lower()
    if value == "cut":
        return 0.0
    match = _CROSSFADE_RE.match(value)
    if match is None:
        raise ValueError(
            f"{where}: unknown transition {transition!r} — clip.yaml allows `cut` or "
            f"`crossfade-<N>f` (schemas.md). Fix the manifest; QC will not guess."
        )
    if fps <= 0:
        raise ValueError(f"{where}: clip.output.fps is {fps}, cannot convert a frame count to seconds")
    return int(match.group(1)) / fps


@dataclass
class Timeline:
    clip: Clip
    storyboard_visual: dict[str, str] = field(default_factory=dict)

    @property
    def boundaries(self) -> list[float]:
        """Every output time where one segment gives way to the next, plus 0 and the end."""
        return [0.0, *[seg.output_out for seg in self.clip.timeline]]

    @property
    def boundary_slack(self) -> list[tuple[float, float]]:
        """(boundary time, extra seconds a legitimate visual change may drift past it).

        Zero for a hard cut; the crossfade ramp length at a `crossfade-<N>f` boundary.
        Validates every transition string on the way through.
        """
        segments = self.clip.timeline
        out: list[tuple[float, float]] = [(0.0, 0.0)]
        for n, seg in enumerate(segments):
            ramp = (
                transition_ramp_seconds(seg.transition, self.clip.output.fps, seg.id)
                if n < len(segments) - 1
                else 0.0
            )
            out.append((seg.output_out, ramp))
        return out

    @property
    def internal_boundaries(self) -> list[tuple[float, str]]:
        """Boundaries between segments whose source ranges are not contiguous (jump cuts)."""
        out: list[tuple[float, str]] = []
        for a, b in zip(self.clip.timeline, self.clip.timeline[1:]):
            same_file = a.source_file == b.source_file
            contiguous = same_file and abs(b.source_in - a.source_out) <= EPSILON
            if not contiguous:
                reason = "different source file" if not same_file else f"source jump {a.source_out:.2f}->{b.source_in:.2f}"
                out.append((a.output_out, f"{a.id}|{b.id} ({reason})"))
        return out

    def _hard_cut_pairs(self):
        return [
            (a, b)
            for a, b in zip(self.clip.timeline, self.clip.timeline[1:])
            if a.transition.strip().lower() == "cut"
        ]

    @staticmethod
    def _is_unverifiable(a, b) -> bool:
        """True when a hard cut here is not guaranteed to produce a visual discontinuity.

        Scene detection can only confirm a cut that CHANGES THE PICTURE. That is guaranteed
        when the camera changes (different source file) or the framing changes (different
        treatment). It is NOT guaranteed within one static talking-head shot:

        - gap 0 — a motion-only split; by construction nothing changes (S15->S16).
        - a small gap — 0.5s removed from a speaker who barely moved scores 0.0271, well
          under any honest floor, while real camera changes measured >=0.0789 (S11->S12).

        Whether such a cut registers depends on how much the subject happened to move, which
        the pipeline neither controls nor promises. Demanding a spike there fails correct
        renders. These boundaries are reported as SKIPPED with their measured peak so the
        gap in coverage is visible and auditable — never counted as passed.
        """
        return a.source_file == b.source_file and a.visual.treatment == b.visual.treatment

    @property
    def hard_cuts(self) -> list[tuple[float, str, str]]:
        """Every hard cut as (output time, label, why-unverifiable — empty when it must register)."""
        out: list[tuple[float, str, str]] = []
        for a, b in self._hard_cut_pairs():
            gap = b.source_in - a.source_out
            why = "motion-only split" if abs(gap) <= EPSILON else f"{gap:.2f}s jump within one shot"
            out.append((a.output_out, f"{a.id}->{b.id}", why if self._is_unverifiable(a, b) else ""))
        return out

    def visual_text(self, segment_id: str) -> str:
        seg = next(s for s in self.clip.timeline if s.id == segment_id)
        parts = [seg.visual.treatment, seg.visual.motion or "", self.storyboard_visual.get(segment_id, "")]
        return " ".join(parts).lower()

    def planned_by(self, interval: Interval, words: tuple[str, ...]) -> str | None:
        """The segment id whose plan uses one of `words` over this interval, if any."""
        for seg in self.clip.timeline:
            if not interval.overlaps(seg.output_in, seg.output_out):
                continue
            text = self.visual_text(seg.id)
            if any(word in text for word in words):
                return seg.id
        return None


def read_storyboard_visuals(storyboard: Path) -> dict[str, str]:
    """Segment id -> the storyboard Timeline row's Visual cell. Absent storyboard = {}."""
    if not storyboard.is_file():
        return {}
    tables = parse_md_tables(storyboard.read_text())
    rows = find_table(tables, TIMELINE_HEADERS).row_dicts()
    return {row["Segment"].strip(): row["Visual"] for row in rows}


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def check_container(probe: dict, profile: PlatformProfile) -> Check:
    video, audio = _stream(probe, "video"), _stream(probe, "audio")
    problems: list[str] = []
    if video is None:
        problems.append("no video stream")
    if audio is None:
        problems.append("no audio stream")
    if problems:
        return Check("container_matches_profile", False, "; ".join(problems))

    width, height = int(video["width"]), int(video["height"])
    fps = _fraction(video["r_frame_rate"])
    want_w, want_h = profile_dims(profile)
    divisor = math.gcd(width, height)
    aspect = f"{width // divisor}:{height // divisor}"
    format_names = probe.get("format", {}).get("format_name", "").split(",")

    if video["codec_name"] != profile.video_codec:
        problems.append(f"video codec {video['codec_name']} != {profile.video_codec}")
    if audio["codec_name"] != profile.audio_codec:
        problems.append(f"audio codec {audio['codec_name']} != {profile.audio_codec}")
    if (width, height) != (want_w, want_h):
        problems.append(f"resolution {width}x{height} != {profile.resolution}")
    if abs(fps - profile.fps) > FPS_TOLERANCE:
        problems.append(f"fps {fps:.3f} != {profile.fps:g}")
    if aspect != profile.aspect:
        problems.append(f"aspect {aspect} != {profile.aspect}")
    if profile.container not in format_names:
        problems.append(f"container {format_names} does not include {profile.container}")

    summary = f"{video['codec_name']}/{audio['codec_name']} {width}x{height}@{fps:g} {aspect} in {format_names[0]}"
    return Check(
        "container_matches_profile",
        not problems,
        summary if not problems else f"{summary} — {'; '.join(problems)}",
    )


def check_duration(probe: dict, clip: Clip) -> Check:
    container = float(probe["format"]["duration"])
    video, audio = _stream(probe, "video"), _stream(probe, "audio")
    if video is None or audio is None:
        return Check("duration_matches_manifest", False, "missing a video or audio stream to compare")
    v_dur = _stream_duration(video, "video")
    a_dur = _stream_duration(audio, "audio")
    want = clip.output.duration_s

    problems = []
    if abs(container - want) > DURATION_TOLERANCE_S:
        problems.append(f"container {container:.3f}s vs manifest {want:.3f}s (delta {container - want:+.3f}s)")
    if abs(v_dur - a_dur) > DURATION_TOLERANCE_S:
        problems.append(f"video {v_dur:.3f}s vs audio {a_dur:.3f}s (delta {v_dur - a_dur:+.3f}s)")
    detail = f"container {container:.3f}s / video {v_dur:.3f}s / audio {a_dur:.3f}s vs manifest {want:.3f}s (±{DURATION_TOLERANCE_S}s)"
    return Check("duration_matches_manifest", not problems, detail if not problems else f"{detail} — {'; '.join(problems)}")


def _planned_split(
    name: str, intervals: list[Interval], timeline: Timeline, words: tuple[str, ...], probe_detail: str
) -> Check:
    """Shared verdict for the two detectors whose intervals the storyboard may authorise."""
    if not intervals:
        return Check(name, True, f"none ({probe_detail})")
    tagged = [(iv, timeline.planned_by(iv, words)) for iv in intervals]
    bad = [iv for iv, seg in tagged if seg is None]
    planned = [f"{iv} (planned by {seg})" for iv, seg in tagged if seg is not None]
    if bad:
        return Check(
            name,
            False,
            f"{len(bad)} unplanned interval(s): {', '.join(str(iv) for iv in bad)}"
            + (f"; planned: {', '.join(planned)}" if planned else "")
            + f" ({probe_detail}). An interval passes only when the overlapping segment's "
            f"visual/motion or the storyboard Visual cell says one of {list(words)}.",
        )
    return Check(name, True, f"{len(planned)} interval(s), all planned: {', '.join(planned)} ({probe_detail})")


def check_black(render: Path, timeline: Timeline) -> Check:
    return _planned_split(
        "black_frames",
        detect_black(render),
        timeline,
        BLACK_INTENT_WORDS,
        f"blackdetect d={BLACK_MIN_DURATION_S}s pix_th={BLACK_PIXEL_THRESHOLD}",
    )


def check_freeze(render: Path, eof: float, timeline: Timeline) -> Check:
    return _planned_split(
        "frozen_frames",
        detect_freeze(render, eof),
        timeline,
        FREEZE_INTENT_WORDS,
        f"freezedetect n={FREEZE_NOISE_DB} d={FREEZE_MIN_DURATION_S}s",
    )


def check_loudness(render: Path, profile: PlatformProfile, tolerance: float) -> Check:
    integrated, true_peak = measure_loudness(render)
    problems = []
    if abs(integrated - profile.loudness_lufs) > tolerance:
        problems.append(f"integrated {integrated:.1f} LUFS outside {profile.loudness_lufs:g} ±{tolerance:g} LU")
    if true_peak > profile.true_peak_dbtp:
        problems.append(f"true peak {true_peak:.1f} dBTP over the {profile.true_peak_dbtp:g} dBTP ceiling")
    detail = (
        f"{integrated:.1f} LUFS (target {profile.loudness_lufs:g} ±{tolerance:g}), "
        f"true peak {true_peak:.1f} dBTP (ceiling {profile.true_peak_dbtp:g})"
    )
    return Check("loudness", not problems, detail if not problems else f"{detail} — {'; '.join(problems)}")


def check_clipping(render: Path) -> Check:
    clipped, peak_db = measure_clipping(render)
    detail = f"{clipped} clipped sample(s), peak {peak_db:.2f} dBFS"
    return Check("clipping", clipped == 0, detail)


def natural_pause_at(root: Path, timeline: Timeline, out_start: float, out_end: float) -> float:
    """Longest silence the SOURCE already had under this rendered interval, in seconds.

    A pause the speaker actually took is not a splice artifact. Mapping the rendered
    interval back through the segment that produced it and re-probing the untouched source
    distinguishes "the edit tore a hole here" from "he paused here, and the edit made it
    shorter". Returns 0.0 when nothing maps (no segment, or the file is unavailable) so an
    unverifiable interval stays reported rather than silently excused.
    """
    total = 0.0
    for seg in timeline.clip.timeline:
        lo, hi = max(out_start, seg.output_in), min(out_end, seg.output_out)
        if hi <= lo:
            continue
        source = root / seg.source_file
        if not source.is_file():
            continue
        shift = seg.source_in - seg.output_in
        win_lo, win_hi = lo + shift, hi + shift
        # A pause that straddles a cut is the silent TAIL of one segment followed by the
        # silent HEAD of the next. Each piece is natural; only their sum is comparable to
        # what the render shows, so accumulate rather than taking the longest single piece.
        # Probe with no minimum duration — a 0.16s fragment is still real silence, and the
        # CUT_WINDOW_SILENCE_MIN_S floor would discard it and understate the total.
        for iv in detect_silence(source, seg.source_out, 0.0, window=(win_lo, win_hi),
                                 noise_db=SOURCE_SILENCE_NOISE_DB):
            total += max(0.0, min(iv.end, win_hi) - max(iv.start, win_lo))
    return total


def check_silence(render: Path, eof: float, timeline: Timeline, root: Path) -> Check:
    everywhere = detect_silence(render, eof, SILENCE_MIN_DURATION_S)
    cuts = timeline.internal_boundaries
    dropouts: list[str] = []
    excused = 0
    for at, label in cuts:
        window = (max(0.0, at - CUT_WINDOW_S), min(eof, at + CUT_WINDOW_S))
        found = detect_silence(render, eof, CUT_WINDOW_SILENCE_MIN_S, window=window)
        for iv in found:
            # Only a pause the edit CREATED or LENGTHENED is a defect. Trimming a 0.85s
            # natural pause down to 0.47s is good editing, and the old check failed it.
            natural = natural_pause_at(root, timeline, iv.start, iv.end)
            if natural + NATURAL_PAUSE_TOLERANCE_S >= (iv.end - iv.start):
                excused += 1
                continue
            dropouts.append(
                f"{iv} at cut {label} (source had only {natural:.2f}s here)"
            )

    # The whole-clip sweep needs the same source comparison as the cut probe: a speaker who
    # pauses for a second has not created a dropout, and a storyboard may keep that beat
    # deliberately. Without this, every clip carrying a natural pause reports a false red.
    created = []
    for iv in everywhere:
        natural = natural_pause_at(root, timeline, iv.start, iv.end)
        if natural + NATURAL_PAUSE_TOLERANCE_S >= (iv.end - iv.start):
            excused += 1
            continue
        created.append(f"{iv} (source had only {natural:.2f}s here)")

    problems = []
    if created:
        problems.append(
            f"{len(created)} silence >= {SILENCE_MIN_DURATION_S}s not present in the source: "
            f"{', '.join(created)}"
        )
    if dropouts:
        problems.append(f"{len(dropouts)} dropout(s) at internal cuts: {', '.join(dropouts)}")
    detail = (
        f"whole clip clear at n={SILENCE_NOISE_DB} d={SILENCE_MIN_DURATION_S}s; "
        f"{len(cuts)} internal cut(s) probed ±{CUT_WINDOW_S:g}s at d={CUT_WINDOW_SILENCE_MIN_S:g}s"
        + (f"; {excused} pause(s) present in the source, not edit artifacts" if excused else "")
    )
    return Check("silence", not problems, detail if not problems else "; ".join(problems))


def check_cut_points(render: Path, timeline: Timeline) -> Check:
    # Built first so an unknown transition string fails loudly before any measurement.
    windows = timeline.boundary_slack
    # Two sensitivities: a floor calibrated on this render's own noise to CONFIRM the cuts
    # we know about (same-camera jump cuts land well under SCENE_THRESHOLD, by an amount
    # that varies per shot), and the strict fixed threshold to decide what counts as an
    # unannounced visual change.
    scores = scene_scores(render)
    floor = confirm_threshold(scores, [at for at, _ in windows])
    confirmed = [t for t, v in scores if v > floor]
    detected = [t for t, v in scores if v > SCENE_THRESHOLD]
    crossfades = sum(1 for _, ramp in windows if ramp > 0)

    def peak_at(at: float) -> float:
        return max((v for t, v in scores if abs(t - at) <= CUT_MATCH_TOLERANCE_S), default=0.0)

    # Confirm first, categorise second. A boundary that DID register is verified no matter
    # what category it falls in — only an unregistered one needs the distinction between
    # "should have shown up, didn't" (a defect) and "was never guaranteed to" (a coverage gap).
    registered = [
        (at, label, why)
        for at, label, why in timeline.hard_cuts
        if any(abs(d - at) <= CUT_MATCH_TOLERANCE_S for d in confirmed)
    ]
    unregistered = [
        (at, label, why)
        for at, label, why in timeline.hard_cuts
        if not any(abs(d - at) <= CUT_MATCH_TOLERANCE_S for d in confirmed)
    ]
    missing = [
        f"{label} @{at:.2f}s (peak {peak_at(at):.4f})" for at, label, why in unregistered if not why
    ]
    skipped = [(at, f"{label} @{at:.2f}s ({why})") for at, label, why in unregistered if why]
    unexpected = [
        f"{d:.2f}s"
        for d in detected
        if min((abs(d - at) - ramp for at, ramp in windows), default=math.inf) > CUT_UNEXPECTED_TOLERANCE_S
    ]

    problems = []
    if missing:
        problems.append(
            f"{len(missing)} expected hard cut(s) with no scene change within "
            f"±{CUT_MATCH_TOLERANCE_S}s: {', '.join(missing)}"
        )
    if unexpected:
        problems.append(
            f"{len(unexpected)} scene change(s) >{CUT_UNEXPECTED_TOLERANCE_S}s from any boundary "
            f"(plus its crossfade ramp): {', '.join(unexpected)}"
        )
    detail = (
        f"{len(confirmed)} scene change(s) at scene>{floor:.4f} (noise-calibrated) "
        f"({len(detected)} above {SCENE_THRESHOLD}); "
        f"{len(registered)} of {len(timeline.hard_cuts)} hard cut(s) confirmed within "
        f"±{CUT_MATCH_TOLERANCE_S}s; "
        f"{crossfades} crossfade boundary/ies exempt from must-detect"
    )
    # A skip is never folded into the pass count — "verified" and "not verifiable" must
    # read differently, on a green check as much as on a red one.
    if skipped:
        listed = ", ".join(f"{label} peak {peak_at(at):.4f}" for at, label in skipped)
        detail += f"; {len(skipped)} SKIPPED (unverifiable): {listed}"
    return Check("cut_points", not problems, detail if not problems else "; ".join(problems))


def check_subtitles(
    probe: dict, ass: Path | None, clip: Clip, config: PipelineConfig, profile: PlatformProfile
) -> Check:
    lines = clip.subtitles.lines
    muxed = [s for s in probe.get("streams", []) if s.get("codec_type") == "subtitle"]
    delivery = f"{len(muxed)} muxed subtitle stream(s)" if muxed else "burned-in (no subtitle stream)"
    if not lines:
        return Check("subtitles_present", True, f"manifest declares no subtitle lines; render is {delivery}")
    if ass is None or not ass.is_file():
        return Check(
            "subtitles_present",
            False,
            f"manifest declares {len(lines)} subtitle line(s) but no aligned .ass was found"
            + (f" at {ass}" if ass is not None else " (pass --ass PATH)"),
        )
    findings = validate_subtitle_script(ass, clip, config, profile)
    if findings:
        return Check(
            "subtitles_present",
            False,
            f"{ass.name}: {len(findings)} validate_subtitles finding(s) against final timing — "
            + "; ".join(f"[{f.check}] {f.where}: {f.actual}" for f in findings[:6])
            + (f" (+{len(findings) - 6} more)" if len(findings) > 6 else ""),
        )
    return Check(
        "subtitles_present",
        True,
        f"{ass.name} present, {len(lines)} manifest line(s) matched, validate_subtitles green; {delivery}",
    )


def check_assets(clip: Clip, clip_dir: Path) -> Check:
    problems: list[str] = []
    by_id = {a.id: a for a in clip.assets}
    for asset in clip.assets:
        path = clip_dir / asset.file
        if not path.is_file():
            problems.append(f"{asset.id}: file missing at {asset.file}")
            continue
        if asset.sha256 is None:
            problems.append(f"{asset.id}: no sha256 recorded (actual {sha256_file(path)})")
            continue
        actual = sha256_file(path)
        if actual != asset.sha256:
            problems.append(f"{asset.id}: sha256 {actual[:12]}… != manifest {asset.sha256[:12]}…")
    for seg in clip.timeline:
        if seg.visual.kind != "broll":
            continue
        if seg.visual.asset_id is None:
            problems.append(f"{seg.id}: broll segment names no asset_id")
        elif seg.visual.asset_id not in by_id:
            problems.append(f"{seg.id}: asset {seg.visual.asset_id} absent from assets[]")
    broll = sum(1 for s in clip.timeline if s.visual.kind == "broll")
    detail = f"{len(clip.assets)} asset(s) present with matching sha256; {broll} broll segment(s) resolved"
    return Check("assets_tracked", not problems, detail if not problems else "; ".join(problems))


def check_manifest_agreement(probe: dict, clip: Clip) -> Check:
    video = _stream(probe, "video")
    if video is None:
        return Check("manifest_agreement", False, "no video stream to compare against clip.output")
    width, height = int(video["width"]), int(video["height"])
    fps = _fraction(video["r_frame_rate"])
    container = float(probe["format"]["duration"])
    want_w, want_h = _dims(clip.output.resolution, "clip.output.resolution")
    divisor = math.gcd(width, height)
    aspect = f"{width // divisor}:{height // divisor}"

    problems = []
    if (width, height) != (want_w, want_h):
        problems.append(f"resolution {width}x{height} != clip.output {clip.output.resolution}")
    if abs(fps - clip.output.fps) > FPS_TOLERANCE:
        problems.append(f"fps {fps:.3f} != clip.output {clip.output.fps:g}")
    if aspect != clip.output.aspect:
        problems.append(f"aspect {aspect} != clip.output {clip.output.aspect}")
    if abs(container - clip.output.duration_s) > DURATION_TOLERANCE_S:
        problems.append(f"duration {container:.3f}s != clip.output {clip.output.duration_s:.3f}s")
    last = clip.timeline[-1].output_out if clip.timeline else 0.0
    if abs(clip.output.duration_s - last) > EPSILON:
        problems.append(f"clip.output.duration_s {clip.output.duration_s:.3f}s != timeline end {last:.3f}s")
    detail = f"{width}x{height}@{fps:g} {aspect} {container:.3f}s vs clip.output {clip.output.resolution}@{clip.output.fps:g} {clip.output.aspect} {clip.output.duration_s:.3f}s"
    return Check("manifest_agreement", not problems, detail if not problems else f"{detail} — {'; '.join(problems)}")


# --------------------------------------------------------------------------------------
# Contact sheet
# --------------------------------------------------------------------------------------


def _escape_drawtext(text: str) -> str:
    return text.replace("\\", "\\\\").replace(":", "\\:").replace("'", "").replace("%", "\\%")


def contact_frames(timeline: Timeline, duration: float) -> list[tuple[float, str]]:
    """(sample time, label) for every timeline boundary and every segment midpoint."""
    segments = timeline.clip.timeline
    frames: list[tuple[float, str]] = []
    for seg in segments:
        frames.append((seg.output_in, f"{seg.id} in {fmt_mmss(seg.output_in)}"))
        mid = (seg.output_in + seg.output_out) / 2
        frames.append((mid, f"{seg.id} mid {fmt_mmss(mid)}"))
    if segments:
        end = segments[-1].output_out
        frames.append((end, f"END {fmt_mmss(end)}"))
    # Nudge samples off the exact boundary so each lands inside the segment it labels.
    nudged: list[tuple[float, str]] = []
    for at, label in frames:
        t = min(max(at + 0.04, 0.0), max(duration - 0.05, 0.0))
        nudged.append((t, label))
    return nudged


def build_contact_sheet(render: Path, out_path: Path, frames: list[tuple[float, str]], work: Path) -> None:
    if not frames:
        raise RuntimeError("no timeline segments — nothing to build a contact sheet from")
    font = find_font()
    work.mkdir(parents=True, exist_ok=True)
    for n, (at, label) in enumerate(frames, start=1):
        drawtext = (
            f"drawtext=fontfile={font}:text='{_escape_drawtext(label)}':x=8:y=8:fontsize=20:"
            f"fontcolor=white:box=1:boxcolor=black@0.65:boxborderw=6"
        )
        _run(
            [
                "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
                "-ss", f"{at:.3f}", "-i", str(render), "-frames:v", "1",
                "-vf", f"scale={CONTACT_TILE_WIDTH}:-2,{drawtext}",
                str(work / f"frame_{n:03d}.png"),
            ]
        )
    cols = math.ceil(math.sqrt(len(frames)))
    rows = math.ceil(len(frames) / cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg", "-nostdin", "-hide_banner", "-v", "error", "-y",
            "-framerate", "1", "-i", str(work / "frame_%03d.png"),
            "-vf", f"tile={cols}x{rows}:padding={CONTACT_TILE_PADDING}:margin={CONTACT_TILE_PADDING}:color=black",
            "-frames:v", "1", str(out_path),
        ]
    )
    if not out_path.is_file():
        raise RuntimeError(f"contact sheet was not written to {out_path}")
    # The per-frame stills exist only to feed `tile`; leaving them behind would litter
    # renders/ with files no manifest tracks.
    for stale in work.glob("frame_*.png"):
        stale.unlink()
    work.rmdir()


# --------------------------------------------------------------------------------------
# Render resolution
# --------------------------------------------------------------------------------------


def resolve_render(clip: Clip, clip_dir: Path, version: int, profile: str, override: Path | None) -> Path:
    """The profile encode for version N — `render.versions[N].finals[<profile>]`.

    Never `versions[N].preview`: that is the Remotion master, an intermediate that no
    platform profile describes. `--render` overrides the lookup so a freshly encoded
    profile file can be QC'd before the manifest records it.
    """
    if override is not None:
        path = override if override.is_absolute() else clip_dir / override
        if not path.is_file():
            raise typer.BadParameter(f"--render path does not exist: {path}")
        return path
    entry = next((v for v in clip.render.versions if v.version == version), None)
    if entry is None:
        known = sorted(v.version for v in clip.render.versions)
        raise typer.BadParameter(
            f"clip.yaml render.versions has no version {version} (known: {known or 'none'}). "
            f"Record the render first, or pass --render PATH to QC a file before the manifest update."
        )
    final = entry.finals.get(profile)
    if final is None:
        raise typer.BadParameter(
            f"render version {version} has no final for profile {profile!r} "
            f"(known: {sorted(entry.finals) or 'none'}). Pass --render PATH to override."
        )
    path = clip_dir / final
    if not path.is_file():
        raise typer.BadParameter(f"render recorded in clip.yaml does not exist on disk: {path}")
    return path


def default_ass(clip_dir: Path, version: int, override: Path | None) -> Path | None:
    if override is not None:
        return override if override.is_absolute() else clip_dir / override
    candidate = clip_dir / "subtitles" / f"v{version}.ass"
    return candidate


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------


def render_table(checks: list[Check]) -> None:
    table = RichTable(title="QC checks", header_style="bold")
    table.add_column("Check", no_wrap=True)
    table.add_column("Result", no_wrap=True)
    table.add_column("Detail")
    for c in checks:
        table.add_row(
            c.name,
            "[bold green]PASS[/]" if c.passed else "[bold red]FAIL[/]",
            c.detail,
            style=None if c.passed else "yellow",
        )
    console.print(table)


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    version: int = typer.Option(..., "--version", "-n", help="Render version N to QC"),
    profile: str = typer.Option("youtube-shorts", "--profile", help="Platform profile to QC against"),
    render: Path = typer.Option(
        None,
        "--render",
        help="Profile encode to QC, for use before the manifest records it "
        "(default: clip.yaml render.versions[N].finals[PROFILE]; never the Remotion master)",
    ),
    ass: Path = typer.Option(None, "--ass", help="Aligned .ass (default: CLIP_DIR/subtitles/v<N>.ass)"),
    episode_root: Path = typer.Option(
        None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"
    ),
    config: Path = typer.Option(None, "--config", help="Pipeline config (default: skill config/defaults.yaml)"),
) -> None:
    """QC render version N of CLIP_DIR, write qc-v<N>.json, exit nonzero on any failure."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    clip_path = clip_dir / "clip.yaml"
    if not clip_path.is_file():
        raise typer.BadParameter(f"missing required file: {clip_path}")

    root = episode_root_for(clip_dir, episode_root)
    settings = load_config(config)
    target = resolve_profile(load_episode(root / "episode.yaml"), profile)
    clip = load_clip(clip_path)
    render_path = resolve_render(clip, clip_dir, version, profile, render)
    ass_path = default_ass(clip_dir, version, ass)
    timeline = Timeline(clip=clip, storyboard_visual=read_storyboard_visuals(clip_dir / "storyboard.md"))

    logger.info(f"clip={clip_path} render={render_path} profile={target.name} version={version}")
    probe = ffprobe_json(render_path)
    eof = float(probe["format"]["duration"])

    checks = [
        check_container(probe, target),
        check_duration(probe, clip),
        check_black(render_path, timeline),
        check_freeze(render_path, eof, timeline),
        check_loudness(render_path, target, settings.render.qc_loudness_tolerance_lu),
        check_clipping(render_path),
        check_silence(render_path, eof, timeline, root),
        check_cut_points(render_path, timeline),
        check_subtitles(probe, ass_path, clip, settings, target),
        check_assets(clip, clip_dir),
        check_manifest_agreement(probe, clip),
    ]

    sheet_rel = Path("renders") / f"v{version}-contact-sheet.png"
    build_contact_sheet(
        render_path,
        clip_dir / sheet_rel,
        contact_frames(timeline, clip.output.duration_s),
        clip_dir / "renders" / f".contact-v{version}",
    )

    passed = all(c.passed for c in checks)
    report = {
        "clip_id": clip.clip.id,
        "render_version": version,
        "profile": target.name,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "passed": passed,
        "checks": [c.as_json() for c in checks],
        "contact_sheet": str(sheet_rel),
    }
    qc_path = clip_dir / f"qc-v{version}.json"
    qc_path.write_text(json.dumps(report, indent=2) + "\n")

    render_table(checks)
    console.print(f"contact sheet: [cyan]{clip_dir / sheet_rel}[/]")
    console.print(f"report: [cyan]{qc_path}[/]")
    if not passed:
        failed = [c.name for c in checks if not c.passed]
        console.print(f"[bold red]QC FAILED[/] {clip.clip.id} v{version} ({target.name}): {failed}")
        raise typer.Exit(1)
    console.print(
        f"[bold green]QC PASSED[/] {clip.clip.id} v{version} ({target.name}): "
        f"{len(checks)}/{len(checks)} checks green, {fmt_mmss(clip.output.duration_s)}"
    )


if __name__ == "__main__":
    app()
