"""Shared render-stage helpers: pipeline config, platform profiles, ffmpeg driving.

Imported by the stage-8 entry scripts (`assemble_audio.py`, `extract_segments.py`,
`align_subtitles.py`) the same way they import `pslib` — the script directory is on
sys.path. This module is not itself executable.

Every helper here fails loudly: a missing file, a missing config block, a nonzero
ffmpeg exit or an unparseable crop is an exception with the offending value in the
message, never a default that lets a wrong render proceed.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

import yaml
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
    max_lines: int
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


class PipelineConfig(Loose):
    transcription: TranscriptionConfig
    subtitles: SubtitleConfig
    safe_zones: SafeZones
    render: RenderConfig


def load_config(path: str | Path | None = None) -> PipelineConfig:
    p = Path(path) if path is not None else DEFAULT_CONFIG
    if not p.is_file():
        raise FileNotFoundError(f"missing pipeline config: {p} — pass --config or restore config/defaults.yaml")
    return PipelineConfig.model_validate(yaml.safe_load(p.read_text()))


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

FFMPEG_BASE = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-y"]


def run_ffmpeg(args: list[str], what: str) -> None:
    """Run ffmpeg with explicit args. Nonzero exit raises with the command and stderr."""
    cmd = [*FFMPEG_BASE, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed while {what} (exit {proc.returncode})\n"
            f"  command: {' '.join(cmd)}\n"
            f"  stderr: {proc.stderr.strip() or '<empty>'}"
        )


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


def parse_hex_color(value: str) -> tuple[int, int, int]:
    text = value.strip().lstrip("#")
    if len(text) != 6 or any(c not in "0123456789abcdefABCDEF" for c in text):
        raise ValueError(f"unparseable colour {value!r} — expected #RRGGBB")
    return int(text[0:2], 16), int(text[2:4], 16), int(text[4:6], 16)


def ass_color(value: str, alpha: int = 0) -> str:
    """`#RRGGBB` → `&HAABBGGRR` (ASS byte order, AA is *inverse* alpha)."""
    r, g, b = parse_hex_color(value)
    return f"&H{alpha:02X}{b:02X}{g:02X}{r:02X}"
