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
"""Validate an aligned `.ass` against the readability limits, safe zones and manifest.

Canonical rules: `references/storyboard.md` § Stage 6 (readability limits, safe zones)
and `references/schemas.md` (clip.yaml `subtitles.lines`). Limits and safe zones come
from `config/defaults.yaml`; frame geometry from the named platform profile in
`episode.yaml`. The file under test is the one `align_subtitles.py` emits — parsing is
done with `pysubs2`, not a hand-rolled reader.

Checks performed (every one, always — a check that cannot run raises, it never passes
quietly):

    max_lines            <= subtitles.max_lines lines per event
    max_chars_per_line   <= subtitles.max_chars_per_line per rendered line
    reading_speed        visible chars / display seconds <= subtitles.max_chars_per_second
    min_display          display duration >= subtitles.min_display_seconds
    no_overlap           events never overlap in time
    manifest_coverage    every clip.yaml subtitles.lines[].text lands in EXACTLY one event
    safe_zones           rendered text band and wrap box inside the profile's safe region
    within_duration      every event inside [0, clip.output.duration_s]

`qc_render.py` imports `validate()` from this module to re-run the same checks against
the final rendered timing; keep the two in lockstep by changing only this file.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pysubs2
import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import EPSILON, Clip, PlatformProfile, load_clip, load_episode, tokenize
from psmedia import (
    PipelineConfig,
    SafeZones,
    SubtitleConfig,
    episode_root_for,
    load_config,
    profile_dims,
    resolve_profile,
)

console = Console()
app = typer.Typer(add_completion=False)

# --------------------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------------------

#: `safe_zones` in config/defaults.yaml are pixels in this reference frame; they are
#: scaled proportionally when the target profile has a different resolution.
SAFE_ZONE_REFERENCE_W = 1080
SAFE_ZONE_REFERENCE_H = 1920

#: Rendered line box height as a multiple of the style font size. libass draws a line at
#: roughly 1.2x the nominal size once ascender/descender/leading are counted; using the
#: nominal size alone would under-report a two-line block and let it sit lower than it
#: really renders.
LINE_HEIGHT_FACTOR = 1.20

_POS_RE = re.compile(r"\\pos\(\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\)")
_AN_RE = re.compile(r"\\an([1-9])")
_LEGACY_A_RE = re.compile(r"\\a(?!n)(\d+)")


# --------------------------------------------------------------------------------------
# .ass reading
# --------------------------------------------------------------------------------------


@dataclass
class Event:
    index: int
    start: float
    end: float
    lines: list[str]
    style_name: str
    font_size: float
    alignment: int
    margin_v: float
    margin_l: float
    margin_r: float
    pos: tuple[float, float] | None
    legacy_alignment_tag: str | None

    @property
    def duration(self) -> float:
        return self.end - self.start

    @property
    def visible_text(self) -> str:
        return " ".join(self.lines)

    @property
    def char_count(self) -> int:
        return sum(len(line) for line in self.lines)

    @property
    def longest_line(self) -> int:
        return max((len(line) for line in self.lines), default=0)


@dataclass
class Script:
    play_res_x: int
    play_res_y: int
    events: list[Event]


def _info_value(info: dict[str, str], key: str) -> str | None:
    return {k.strip().lower(): v for k, v in info.items()}.get(key.lower())


def read_script(ass_path: str | Path) -> Script:
    """Parse the .ass. Anything structurally missing is a loud error, not a default."""
    path = Path(ass_path)
    if not path.is_file():
        raise FileNotFoundError(f"missing subtitle file: {path} — run align_subtitles.py first")
    head = path.read_text(encoding="utf-8", errors="replace")[:4096]
    if "[Script Info]" not in head:
        raise ValueError(
            f"{path} is not an Advanced SubStation Alpha file — no [Script Info] section in the "
            f"first 4KB. This stage validates the .ass that align_subtitles.py emits; point "
            f"--ass at subtitles/v<N>.ass."
        )

    subs = pysubs2.load(str(path), encoding="utf-8")

    play_res_x_raw = _info_value(subs.info, "PlayResX")
    play_res_y_raw = _info_value(subs.info, "PlayResY")
    if play_res_x_raw is None or play_res_y_raw is None:
        raise ValueError(
            f"{path}: [Script Info] must declare PlayResX and PlayResY — without them no "
            f"safe-zone check is possible (found keys: {sorted(subs.info)})"
        )
    play_res_x, play_res_y = int(float(play_res_x_raw)), int(float(play_res_y_raw))
    if play_res_x <= 0 or play_res_y <= 0:
        raise ValueError(f"{path}: PlayResX/PlayResY must be positive, got {play_res_x}x{play_res_y}")

    events: list[Event] = []
    for index, ev in enumerate((e for e in subs.events if not e.is_comment), start=1):
        style = subs.styles.get(ev.style)
        if style is None:
            raise ValueError(
                f"{path}: Dialogue #{index} references unknown style {ev.style!r} "
                f"(defined styles: {sorted(subs.styles)})"
            )
        lines = [ln.strip() for ln in ev.plaintext.split("\n")]
        while lines and lines[-1] == "":
            lines.pop()
        pos_match = _POS_RE.search(ev.text)
        an_match = _AN_RE.search(ev.text)
        legacy = _LEGACY_A_RE.search(ev.text)
        events.append(
            Event(
                index=index,
                start=ev.start / 1000.0,
                end=ev.end / 1000.0,
                lines=lines,
                style_name=ev.style,
                font_size=float(style.fontsize),
                alignment=int(an_match.group(1)) if an_match else int(style.alignment),
                # An event margin of 0 means "inherit the style" in .ass, not "zero margin".
                margin_v=float(ev.marginv or style.marginv),
                margin_l=float(ev.marginl or style.marginl),
                margin_r=float(ev.marginr or style.marginr),
                pos=(float(pos_match.group(1)), float(pos_match.group(2))) if pos_match else None,
                legacy_alignment_tag=legacy.group(0) if legacy else None,
            )
        )

    if not events:
        raise ValueError(f"{path}: no Dialogue events — an empty subtitle track is never a pass")
    return Script(play_res_x=play_res_x, play_res_y=play_res_y, events=events)


# --------------------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------------------


@dataclass
class Finding:
    check: str
    where: str
    expected: str
    actual: str


def _where(ev: Event) -> str:
    return f"event {ev.index} @{ev.start:.2f}-{ev.end:.2f}"


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def check_max_lines(script: Script, limits: SubtitleConfig) -> list[Finding]:
    return [
        Finding("max_lines", _where(ev), f"<= {limits.max_lines} lines", f"{len(ev.lines)} lines: {ev.lines}")
        for ev in script.events
        if len(ev.lines) > limits.max_lines
    ]


def check_max_chars_per_line(script: Script, limits: SubtitleConfig) -> list[Finding]:
    return [
        Finding(
            "max_chars_per_line",
            f"{_where(ev)} line {n}",
            f"<= {limits.max_chars_per_line} chars",
            f"{len(line)} chars: {line!r}",
        )
        for ev in script.events
        for n, line in enumerate(ev.lines, start=1)
        if len(line) > limits.max_chars_per_line
    ]


def check_reading_speed(script: Script, limits: SubtitleConfig) -> list[Finding]:
    out: list[Finding] = []
    for ev in script.events:
        if ev.duration <= 0:
            out.append(Finding("reading_speed", _where(ev), "end > start", f"duration {ev.duration:.3f}s"))
            continue
        cps = ev.char_count / ev.duration
        if cps > limits.max_chars_per_second + EPSILON:
            out.append(
                Finding(
                    "reading_speed",
                    _where(ev),
                    f"<= {limits.max_chars_per_second:g} chars/sec",
                    f"{cps:.1f} chars/sec ({ev.char_count} chars in {ev.duration:.2f}s): {ev.visible_text!r}",
                )
            )
    return out


def check_min_display(script: Script, limits: SubtitleConfig) -> list[Finding]:
    return [
        Finding(
            "min_display",
            _where(ev),
            f">= {limits.min_display_seconds:g}s on screen",
            f"{ev.duration:.3f}s: {ev.visible_text!r}",
        )
        for ev in script.events
        if ev.duration < limits.min_display_seconds - EPSILON
    ]


def check_no_overlap(script: Script) -> list[Finding]:
    ordered = sorted(script.events, key=lambda e: (e.start, e.end))
    return [
        Finding(
            "no_overlap",
            f"events {a.index}/{b.index}",
            f"next start >= {a.end:.3f}",
            f"next starts at {b.start:.3f} — overlap of {a.end - b.start:.3f}s",
        )
        for a, b in zip(ordered, ordered[1:])
        if b.start < a.end - EPSILON
    ]


def check_within_duration(script: Script, clip: Clip) -> list[Finding]:
    duration = clip.output.duration_s
    out: list[Finding] = []
    for ev in script.events:
        if ev.start < -EPSILON:
            out.append(Finding("within_duration", _where(ev), "start >= 0", f"{ev.start:.3f}"))
        if ev.end > duration + EPSILON:
            out.append(
                Finding(
                    "within_duration",
                    _where(ev),
                    f"end <= clip.output.duration_s ({duration:.3f}s)",
                    f"{ev.end:.3f}s — {ev.end - duration:.3f}s past the end of the clip",
                )
            )
    return out


def _contains_tokens(haystack: list[str], needle: list[str]) -> bool:
    if not needle:
        return False
    return any(haystack[i : i + len(needle)] == needle for i in range(len(haystack) - len(needle) + 1))


def check_manifest_coverage(script: Script, clip: Clip) -> list[Finding]:
    """Every manifest line lands in exactly one event (compared on lowercased word tokens)."""
    event_tokens = [(ev, tokenize(ev.visible_text)) for ev in script.events]
    out: list[Finding] = []
    for n, line in enumerate(clip.subtitles.lines, start=1):
        needle = tokenize(line.text)
        if not needle:
            out.append(Finding("manifest_coverage", f"clip.yaml subtitle line {n}", "non-empty text", repr(line.text)))
            continue
        # Exact token equality first, containment only as a fallback. Containment alone
        # reports a false failure whenever one card's text is a subsequence of another's
        # ("and I thought" inside "And I thought, right."), and the ONLY workaround available
        # to an editor is to merge or delete words — so a checker bug becomes an editorial
        # decision. That happened to four independent agents on real clips before this fix.
        exact = [ev for ev, toks in event_tokens if toks == needle]
        matches = exact if len(exact) == 1 else [
            ev for ev, toks in event_tokens if _contains_tokens(toks, needle)
        ]
        if len(matches) == 1:
            continue
        detail = (
            "present in no event"
            if not matches
            else f"present in {len(matches)} events: {[m.index for m in matches]}"
        )
        out.append(
            Finding(
                "manifest_coverage",
                f"clip.yaml subtitle line {n} ({line.output_range[0]:.2f}-{line.output_range[1]:.2f})",
                f"exactly one .ass event carrying {line.text!r}",
                detail,
            )
        )
    return out


# --------------------------------------------------------------------------------------
# Safe zones
# --------------------------------------------------------------------------------------


@dataclass
class SafeRegion:
    top: float
    bottom: float
    left: float
    right: float
    frame_w: int
    frame_h: int


def safe_region(zones: SafeZones, profile: PlatformProfile) -> SafeRegion:
    """The profile's safe rectangle in target-frame pixels, scaled from the 1080x1920 reference."""
    frame_w, frame_h = profile_dims(profile)
    return SafeRegion(
        top=zones.top * frame_h / SAFE_ZONE_REFERENCE_H,
        bottom=frame_h - zones.bottom * frame_h / SAFE_ZONE_REFERENCE_H,
        left=zones.left * frame_w / SAFE_ZONE_REFERENCE_W,
        right=frame_w - zones.right * frame_w / SAFE_ZONE_REFERENCE_W,
        frame_w=frame_w,
        frame_h=frame_h,
    )


@dataclass
class Band:
    """Where an event renders, in target-frame pixels."""

    top: float
    bottom: float
    box_left: float
    box_right: float


def event_band(ev: Event, script: Script, region: SafeRegion) -> Band:
    """Vertical text band and horizontal wrap box of an event, in target-frame pixels.

    Vertical placement follows the .ass anchor rules: alignment 1-3 put the block's
    bottom `MarginV` above the frame bottom, 4-6 centre it, 7-9 put its top `MarginV`
    below the frame top; a `\\pos` override replaces the margin with an explicit anchor.

    Horizontally the checked quantity is the **wrap box** (`MarginL` .. `PlayResX -
    MarginR`), not an estimated glyph extent: libass wraps inside that box, and guessing
    a glyph advance would invent font metrics the file does not carry. Overlong lines are
    already caught by `max_chars_per_line`.
    """
    scale_x = region.frame_w / script.play_res_x
    scale_y = region.frame_h / script.play_res_y
    block_h = max(len(ev.lines), 1) * ev.font_size * LINE_HEIGHT_FACTOR
    vertical_band = (ev.alignment - 1) // 3  # 0 = bottom (1-3), 1 = middle (4-6), 2 = top (7-9)

    if ev.pos is not None:
        anchor_y = ev.pos[1]
        top = {0: anchor_y - block_h, 1: anchor_y - block_h / 2, 2: anchor_y}[vertical_band]
    else:
        top = {
            0: script.play_res_y - ev.margin_v - block_h,
            1: (script.play_res_y - block_h) / 2,
            2: ev.margin_v,
        }[vertical_band]

    return Band(
        top=top * scale_y,
        bottom=(top + block_h) * scale_y,
        box_left=ev.margin_l * scale_x,
        box_right=(script.play_res_x - ev.margin_r) * scale_x,
    )


def check_safe_zones(script: Script, zones: SafeZones, profile: PlatformProfile) -> list[Finding]:
    region = safe_region(zones, profile)
    out: list[Finding] = []
    for ev in script.events:
        if ev.legacy_alignment_tag is not None:
            out.append(
                Finding(
                    "safe_zones",
                    _where(ev),
                    "alignment via \\an<1-9> (the tag this pipeline emits)",
                    f"legacy {ev.legacy_alignment_tag} tag — position cannot be verified; re-emit with \\an",
                )
            )
            continue
        if not 1 <= ev.alignment <= 9:
            out.append(Finding("safe_zones", _where(ev), "alignment in 1..9", str(ev.alignment)))
            continue
        band = event_band(ev, script, region)
        placement = (
            f"an{ev.alignment}, "
            + (f"pos={ev.pos}" if ev.pos else f"MarginV={ev.margin_v:g}")
            + f", {len(ev.lines)} line(s) @ {ev.font_size:g}px"
        )
        if band.bottom > region.bottom + EPSILON:
            out.append(
                Finding(
                    "safe_zones",
                    _where(ev),
                    f"text bottom <= {region.bottom:.0f}px (frame {region.frame_h}px less the "
                    f"{zones.bottom}px bottom UI zone)",
                    f"{band.bottom:.0f}px — {band.bottom - region.bottom:.0f}px into the bottom UI zone ({placement})",
                )
            )
        if band.top < region.top - EPSILON:
            out.append(
                Finding(
                    "safe_zones",
                    _where(ev),
                    f"text top >= {region.top:.0f}px (top UI zone)",
                    f"{band.top:.0f}px — {region.top - band.top:.0f}px into the top UI zone ({placement})",
                )
            )
        if band.box_right > region.right + EPSILON:
            out.append(
                Finding(
                    "safe_zones",
                    _where(ev),
                    f"wrap box right edge <= {region.right:.0f}px (engagement rail)",
                    f"{band.box_right:.0f}px (MarginR={ev.margin_r:g})",
                )
            )
        if band.box_left < region.left - EPSILON:
            out.append(
                Finding(
                    "safe_zones",
                    _where(ev),
                    f"wrap box left edge >= {region.left:.0f}px",
                    f"{band.box_left:.0f}px (MarginL={ev.margin_l:g})",
                )
            )
    return out


# --------------------------------------------------------------------------------------
# Entry points
# --------------------------------------------------------------------------------------


def validate(
    ass_path: str | Path, clip: Clip, config: PipelineConfig, profile: PlatformProfile
) -> list[Finding]:
    """Run every subtitle check. Returns findings; an empty list means green."""
    script = read_script(ass_path)
    limits = config.subtitles
    return [
        *check_max_lines(script, limits),
        *check_max_chars_per_line(script, limits),
        *check_reading_speed(script, limits),
        *check_min_display(script, limits),
        *check_no_overlap(script),
        *check_manifest_coverage(script, clip),
        *check_safe_zones(script, config.safe_zones, profile),
        *check_within_duration(script, clip),
    ]


def render_findings(findings: list[Finding]) -> None:
    table = RichTable(title="Subtitle validation failures", header_style="bold red")
    table.add_column("Check", style="bold red", no_wrap=True)
    table.add_column("Where", style="cyan", no_wrap=True)
    table.add_column("Expected", style="green")
    table.add_column("Actual", style="yellow")
    for f in findings:
        table.add_row(f.check, f.where, f.expected, f.actual)
    console.print(table)


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    ass: Path = typer.Option(..., "--ass", help="Aligned .ass subtitle file to validate"),
    profile: str = typer.Option("youtube-shorts", "--profile", help="Platform profile providing frame geometry"),
    episode_root: Path = typer.Option(
        None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"
    ),
    config: Path = typer.Option(None, "--config", help="Pipeline config (default: skill config/defaults.yaml)"),
) -> None:
    """Check an aligned .ass against readability limits, safe zones and the clip manifest."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    clip_path = clip_dir / "clip.yaml"
    if not clip_path.is_file():
        raise typer.BadParameter(f"missing required file: {clip_path}")
    if not ass.is_file():
        raise typer.BadParameter(f"missing subtitle file: {ass}")

    root = episode_root_for(clip_dir, episode_root)
    settings = load_config(config)
    target = resolve_profile(load_episode(root / "episode.yaml"), profile)
    clip = load_clip(clip_path)

    logger.info(f"clip={clip_path} ass={ass} profile={target.name} ({target.resolution})")
    script = read_script(ass)
    findings = validate(ass, clip, settings, target)

    if findings:
        render_findings(findings)
        console.print(
            f"[bold red]FAIL[/] {clip.clip.id}: {len(findings)} finding(s) across checks "
            f"{sorted({f.check for f in findings})}"
        )
        raise typer.Exit(1)

    longest = max((ev.longest_line for ev in script.events), default=0)
    fastest = max((ev.char_count / ev.duration for ev in script.events if ev.duration > 0), default=0.0)
    console.print(
        f"[bold green]PASS[/] {clip.clip.id}: {len(script.events)} events, "
        f"{len(clip.subtitles.lines)} manifest line(s) matched, longest line {longest} chars, "
        f"peak reading speed {fastest:.1f} chars/sec, all inside the {target.name} safe zones"
    )


if __name__ == "__main__":
    app()
