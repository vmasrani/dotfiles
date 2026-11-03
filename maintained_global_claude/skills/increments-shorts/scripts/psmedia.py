"""Shared render-stage helpers: pipeline config, platform profiles, ffmpeg driving.

Imported by the stage-8 entry scripts (`assemble_audio.py`, `frame_segments.py`,
`align_subtitles.py`) the same way they import `pslib` — the script directory is on
sys.path. This module is not itself executable.

Every helper here fails loudly: a missing file, a missing config block, a nonzero
ffmpeg exit or an unparseable crop is an exception with the offending value in the
message, never a default that lets a wrong render proceed.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Literal, get_args, get_origin

import yaml
from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from pslib import Episode, PlatformProfile

SCRIPTS_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = SCRIPTS_DIR.parent / "config" / "defaults.yaml"


# ---------------------------------------------------------------------------
# config/defaults.yaml
# ---------------------------------------------------------------------------


class Loose(BaseModel):
    """Blocks we do not consume (mining, providers, …) are ignored, not fatal."""

    model_config = ConfigDict(extra="ignore")


class SubtitleConfig(Loose):
    font: str
    font_fallbacks: list[str] = Field(default_factory=list)
    base_color: str
    #: Karaoke highlight: the word being spoken is drawn in this colour at this weight
    #: (read by align_subtitles.py for fit-to-width and by remotion/gen-props.mjs for drawing).
    active_color: str
    active_font_weight: int
    #: seeds clip.yaml subtitles.emphasis_palette (freeze_picks.py)
    emphasis_color: str
    #: caption type size as a fraction of frame height — the fit's target and cap (align_subtitles.py)
    font_height_fraction: float
    max_lines: int
    #: rows a card may take ONLY when no split into max_lines-row cards meets max_chars_per_second
    reading_speed_max_lines: int
    max_chars_per_line: int
    max_chars_per_second: float
    min_display_seconds: float
    emphasis_max_word_fraction: float
    #: Defaults match the previously hard-coded values so an older config still renders,
    #: but `config/defaults.yaml` now ships heavier ones — see finding 17b.
    outline_fraction: float = 0.05
    outline_color: str = "#101010"
    shadow_fraction: float = 0.03
    border_style: Literal["outline", "plate"] = "outline"
    plate_opacity: float = 0.55


class SafeZones(Loose):
    top: int
    bottom: int
    right: int
    left: int


class RenderConfig(Loose):
    internal_cut_crossfade_ms: float
    qc_loudness_tolerance_lu: float


class TranscriptionConfig(Loose):
    engine: str
    language: str


class FramingSettings(Loose):
    max_upscale: float = 2.0


class TextPlacement(Loose):
    x: int
    y: int
    anchor: str
    max_width: int


class BrollTextStyle(Loose):
    font: str
    colors: dict[str, str]
    weight: int
    bold_weight: int
    plate_color: str
    plate_opacity: float
    plate_radius: int
    plate_pad_v: int
    plate_pad_h: int
    accent_bar_px: int
    line_gap: float
    rule_color: str
    text_shadow: str
    sizes: dict[str, int]
    fade_frames: int
    pop_frames: int
    rule_frames: int
    placements: dict[str, TextPlacement]


class BrollPip(Loose):
    border_px: int
    border_color: str
    label_gap_px: int


class BrollGrid(Loose):
    gap_px: int
    background: str
    tile_pop_frames: int


class BrollRender(Loose):
    card_concurrency: int


class BrollConfig(Loose):
    text: BrollTextStyle
    pip: BrollPip
    grid: BrollGrid
    render: BrollRender


class PipelineConfig(Loose):
    transcription: TranscriptionConfig
    subtitles: SubtitleConfig
    safe_zones: SafeZones
    render: RenderConfig
    framing: FramingSettings = Field(default_factory=FramingSettings)
    #: horizontal-clip overlays; required only when a clip has `overlays:` (render_horizontal.py checks)
    broll: BrollConfig | None = None


def _deep_merge(base: dict, over: dict, prefix: str = "") -> tuple[dict, list[str]]:
    """Return (merged, dotted keys whose value came from `over`). Mappings merge per key; anything else is replaced."""
    merged, changed = dict(base), []
    for k, v in over.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            merged[k], sub = _deep_merge(base[k], v, f"{key}.")
            changed += sub
        else:
            merged[k] = v
            changed.append(key)
    return merged, changed


def _reject_unknown_keys(model: type[BaseModel], over: dict, prefix: str = "") -> None:
    """Models ignore extras, so a typo'd override would silently do nothing — reject keys no model field declares."""
    for k, v in over.items():
        field = model.model_fields.get(k)
        if field is None:
            raise ValueError(f"config_overrides.{prefix}{k}: unknown key (valid here: {sorted(model.model_fields)})")
        if not isinstance(v, dict):
            continue
        mapping = next((t for t in (field.annotation, *get_args(field.annotation)) if get_origin(t) is dict), None)
        if mapping is not None:
            # dict[str, Model]: the keys are free names (e.g. placements), each value is a Model
            value_model = _model_in(get_args(mapping)[1])
            for name, item in v.items():
                if value_model is not None and isinstance(item, dict):
                    _reject_unknown_keys(value_model, item, f"{prefix}{k}.{name}.")
            continue
        sub = _model_in(field.annotation)
        if sub is not None:
            _reject_unknown_keys(sub, v, f"{prefix}{k}.")


def _model_in(annotation: object) -> type[BaseModel] | None:
    """The BaseModel class an annotation names, directly or inside Optional/Union."""
    return next((t for t in (annotation, *get_args(annotation))
                 if isinstance(t, type) and issubclass(t, BaseModel)), None)


def load_config(path: str | Path | None = None, episode_root: str | Path | None = None) -> PipelineConfig:
    """Base config (defaults.yaml or `path`) with episode.yaml `config_overrides:` deep-merged over it, then validated."""
    p = Path(path) if path is not None else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError(f"missing pipeline config: {p} — pass --config or restore config/defaults.yaml")
    raw = yaml.safe_load(p.read_text())
    if episode_root is not None:
        ep_path = Path(episode_root) / "episode.yaml"
        overrides = (yaml.safe_load(ep_path.read_text()) or {}).get("config_overrides")
        if overrides is not None:
            if not isinstance(overrides, dict):
                raise ValueError(f"{ep_path}: config_overrides must be a mapping shaped like defaults.yaml")
            _reject_unknown_keys(PipelineConfig, overrides)
            raw, changed = _deep_merge(raw, overrides)
            for key in changed:
                logger.info(f"config override from {ep_path.name}: {key}")
    return PipelineConfig.model_validate(raw)


# ---------------------------------------------------------------------------
# Profiles and paths
# ---------------------------------------------------------------------------


def resolve_profile(episode: Episode, name: str) -> PlatformProfile:
    match = [p for p in episode.platform_profiles if p.name == name]
    if not match:
        known = [p.name for p in episode.platform_profiles]
        raise ValueError(f"platform profile {name!r} is not in episode.yaml platform_profiles (known: {known})")
    if len(match) > 1:
        raise ValueError(f"episode.yaml declares platform profile {name!r} {len(match)} times")
    return match[0]


def profile_dims(profile: PlatformProfile) -> tuple[int, int]:
    """`"1080x1920"` → (1080, 1920)."""
    w, _, h = profile.resolution.lower().partition("x")
    if not w.strip().isdigit() or not h.strip().isdigit():
        raise ValueError(f"profile {profile.name}: unparseable resolution {profile.resolution!r} — expected WxH")
    return int(w), int(h)


def episode_root_for(clip_dir: Path, override: Path | None) -> Path:
    root = (override or clip_dir.parent.parent).resolve()
    if not (root / "episode.yaml").is_file():
        raise FileNotFoundError(
            f"no episode.yaml under {root} — pass --episode-root explicitly "
            f"(default is CLIP_DIR/../.., i.e. {clip_dir.parent.parent})"
        )
    return root


def media_path(episode_root: Path, relative: str) -> Path:
    p = (episode_root / relative).resolve()
    if not p.is_file():
        raise FileNotFoundError(f"missing media file: {p} (referenced as {relative!r})")
    return p


def probed_duration(episode: Episode, relative: str) -> float:
    probe = episode.media.probes.get(relative)
    if probe is None:
        known = sorted(episode.media.probes)
        raise ValueError(f"episode.yaml media.probes has no entry for {relative!r} (known: {known})")
    return probe.duration_s


def probe_dims(episode: Episode, relative: str) -> tuple[int, int]:
    probe = episode.media.probes.get(relative)
    if probe is None:
        raise ValueError(f"episode.yaml media.probes has no entry for {relative!r}")
    if probe.width is None or probe.height is None:
        raise ValueError(f"episode.yaml media.probes[{relative!r}] has no width/height — re-run the ingest probe")
    return probe.width, probe.height


# ---------------------------------------------------------------------------
# Crops
# ---------------------------------------------------------------------------


def parse_crop(spec: str) -> tuple[int, int, int, int]:
    """`"x=120:y=0:w=960:h=1080"` → (w, h, x, y), the order ffmpeg's crop filter wants."""
    parts: dict[str, str] = {}
    for chunk in spec.split(":"):
        key, sep, value = chunk.strip().partition("=")
        if not sep:
            raise ValueError(f"unparseable crop {spec!r} — expected `x=..:y=..:w=..:h=..`, got chunk {chunk!r}")
        parts[key.strip().lower()] = value.strip()
    missing = [k for k in ("x", "y", "w", "h") if k not in parts]
    if missing:
        raise ValueError(f"crop {spec!r} is missing {missing} — expected `x=..:y=..:w=..:h=..`")
    extra = sorted(set(parts) - {"x", "y", "w", "h"})
    if extra:
        raise ValueError(f"crop {spec!r} has unknown keys {extra}")
    values = {}
    for key, raw in parts.items():
        if not raw.lstrip("-").isdigit():
            raise ValueError(f"crop {spec!r}: {key}={raw!r} is not an integer pixel value")
        values[key] = int(raw)
    if values["w"] <= 0 or values["h"] <= 0:
        raise ValueError(f"crop {spec!r} has non-positive width/height")
    return values["w"], values["h"], values["x"], values["y"]


def fmt_crop(crop: tuple[int, int, int, int]) -> str:
    w, h, x, y = crop
    return f"x={x}:y={y}:w={w}:h={h}"


def even(value: int) -> int:
    """Round down to an even number — h264 chroma subsampling needs even dimensions."""
    return value - (value % 2)


def center_crop(src_w: int, src_h: int, aspect_w: int, aspect_h: int) -> tuple[int, int, int, int]:
    """Largest centred `aspect_w:aspect_h` rectangle inside `src_w x src_h` → (w, h, x, y)."""
    if src_w <= 0 or src_h <= 0:
        raise ValueError(f"cannot centre-crop a {src_w}x{src_h} frame")
    by_height = even(int(round(src_h * aspect_w / aspect_h)))
    if by_height <= src_w:
        w, h = by_height, even(src_h)
    else:
        w, h = even(src_w), even(int(round(src_w * aspect_h / aspect_w)))
    return w, h, even((src_w - w) // 2), even((src_h - h) // 2)


def validate_crop_within(crop: tuple[int, int, int, int], src_w: int, src_h: int, where: str) -> None:
    w, h, x, y = crop
    if x < 0 or y < 0 or x + w > src_w or y + h > src_h:
        raise ValueError(
            f"{where}: crop {fmt_crop(crop)} falls outside the {src_w}x{src_h} source frame"
        )


# ---------------------------------------------------------------------------
# ffmpeg
# ---------------------------------------------------------------------------

from mediatools import ffmpeg_tool  # noqa: E402,F401  (the one cross-platform resolver)


def ffmpeg_base() -> list[str]:
    return [ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]


def run_ffmpeg(args: list[str], what: str) -> None:
    """Run ffmpeg with explicit args. Nonzero exit raises with the command and stderr."""
    cmd = [*ffmpeg_base(), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed while {what} (exit {proc.returncode})\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr: {proc.stderr.strip() or '<empty>'}"
        )


TRUE_PEAK_MARGIN_DB = 1.5   # the aac re-encode overshoots the wav's true peak by ~0.8 dB (measured)


def loudnorm_pass2_filter(measured: dict[str, str], lufs: float, tp: float) -> str:
    """Pass-2 linear loudnorm filter from pass 1's `print_format=json` measurements."""
    return (
        f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={measured['input_i']}:measured_TP={measured['input_tp']}"
        f":measured_LRA={measured['input_lra']}:measured_thresh={measured['input_thresh']}"
        f":offset={measured['target_offset']}:linear=true"
    )


def parse_loudnorm_json(stderr: str) -> dict[str, str]:
    """The JSON block loudnorm prints at the end of its measurement pass."""
    blob = stderr[stderr.rindex("{"):]
    return json.loads(blob[: blob.index("}") + 1])


def loudnorm_filter(wav: Path, lufs: float, tp: float) -> str:
    """Measure (pass 1) on the assembled wav and return the pass-2 linear loudnorm filter string."""
    out = subprocess.run(
        [ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-i", str(wav), "-af",
         f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True,
    )
    if out.returncode != 0:
        raise RuntimeError(f"loudnorm measurement failed (exit {out.returncode}): {out.stderr[-2000:]}")
    return loudnorm_pass2_filter(parse_loudnorm_json(out.stderr), lufs, tp)


def run_checked(cmd: list[str], what: str, env: dict[str, str] | None = None) -> str:
    """Run any subprocess; nonzero exit raises with the command and stderr. Returns stdout."""
    proc = subprocess.run(cmd, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        raise RuntimeError(
            f"{what} failed (exit {proc.returncode})\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr: {proc.stderr.strip()[-4000:] or '<empty>'}"
        )
    return proc.stdout


def ff_time(seconds: float) -> str:
    """Seconds → a plain ffmpeg time string with microsecond resolution."""
    return f"{seconds:.6f}"


def frame_exact(output_in: float, output_out: float, fps: float) -> str:
    """Filter chain (after decode) that makes one cut segment exactly the frames its OUTPUT-timeline
    span owns. `-ss/-t` + `fps` rounds every segment up to a whole frame, so a concat of N cuts
    drifts ~N/2 frames from the sample-exact audio (measured: +6 frames over 15 cuts). Snapping
    both boundaries to the output frame grid keeps the total error under one frame; `tpad` clones
    the last frame so a segment that rounded down still reaches its count."""
    frames = round(output_out * fps) - round(output_in * fps)
    if frames < 1:
        raise ValueError(f"segment {output_in:.3f}-{output_out:.3f}s spans no frame at {fps:g} fps")
    return f"fps={fps:g},tpad=stop_mode=clone:stop=1,trim=end_frame={frames},setpts=PTS-STARTPTS"


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError(f"unparseable colour {value!r} — expected #RRGGBB")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def ass_color(value: str, alpha: int = 0) -> str:
    """`#RRGGBB` → `&HAABBGGRR` (ASS byte order, AA is *inverse* alpha)."""
    r, g, b = parse_hex_color(value)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
