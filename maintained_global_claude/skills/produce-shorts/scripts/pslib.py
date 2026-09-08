"""Shared library for the produce-shorts pipeline.

Canonical spec: ../references/schemas.md. Every model, invariant constant and parse
contract here comes from that file. Sibling entry scripts import this module (the
script directory is on sys.path); this module is not itself executable.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EPSILON = 0.01

EPISODE_STAGE_ORDER: list[str] = [
    "ingested",
    "mined",
    "selected",
    "storyboarded",
    "assets_acquired",
    "critiqued",
    "approved_for_render",
    "rendered",
    "qc_passed",
]

CLIP_STATUS_ORDER: list[str] = [
    "proposed",
    "approved_edit",
    "storyboarded",
    "assets_ready",
    "critiqued",
    "approved_render",
    "rendered",
    "qc_passed",
    "delivered",
]

TIMELINE_HEADERS = [
    "Segment",
    "Output",
    "Source",
    "Visual",
    "Audio/Dialogue",
    "Speaker",
    "Shot/Transition",
]

SUBTITLE_HEADERS = ["Output", "Verbatim text", "Emphasis", "Position", "Notes"]


class Strict(BaseModel):
    """Base model: unknown keys are a loud error, never a silent drop."""

    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# episode.yaml
# ---------------------------------------------------------------------------


class EpisodeMeta(Strict):
    id: str
    title: str
    source_url: str
    authorized: bool
    created: str


class PlatformProfile(Strict):
    name: str
    aspect: str
    resolution: str
    fps: float
    max_duration_s: float
    container: str
    video_codec: str
    audio_codec: str
    loudness_lufs: float
    true_peak_dbtp: float


class Speaker(Strict):
    id: str
    name: str
    camera_file: str | None = None
    preferred_crop: str | None = None


class MediaProbe(Strict):
    duration_s: float
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    audio_channels: int | None = None
    sample_rate: int | None = None


class MediaSpec(Strict):
    episode_video: str
    episode_audio: str | None = None
    probes: dict[str, MediaProbe] = Field(default_factory=dict)


class SyncGap(Strict):
    camera_s: float
    duration_s: float


class SyncEntry(Strict):
    file: str
    offset_s: float
    confidence: float
    method: str
    gaps: list[SyncGap] = Field(default_factory=list)
    verified: bool


class TranscriptRef(Strict):
    # `json` is the YAML key; the attribute is renamed to avoid shadowing BaseModel.json
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    json_file: str = Field(alias="json")
    md: str
    engine: str
    language: str
    word_count: int


class EpisodeStatus(Strict):
    stage: Literal[
        "ingested",
        "mined",
        "selected",
        "storyboarded",
        "assets_acquired",
        "critiqued",
        "approved_for_render",
        "rendered",
        "qc_passed",
    ]


class Episode(Strict):
    episode: EpisodeMeta
    platform_profiles: list[PlatformProfile]
    speakers: list[Speaker]
    media: MediaSpec
    sync: list[SyncEntry] = Field(default_factory=list)
    transcript: TranscriptRef
    status: EpisodeStatus

    def speaker_ids(self) -> set[str]:
        return {s.id for s in self.speakers}


# ---------------------------------------------------------------------------
# transcript.json
# ---------------------------------------------------------------------------


class Word(Strict):
    w: str
    start: float
    end: float
    speaker: str
    conf: float | None = None


class TranscriptSegment(Strict):
    start: float
    end: float
    speaker: str
    text: str


class Transcript(Strict):
    engine: str
    language: str
    audio_file: str
    words: list[Word] = Field(default_factory=list)
    segments: list[TranscriptSegment] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# candidates.yaml
# ---------------------------------------------------------------------------


class CoverageChunk(Strict):
    start_s: float
    end_s: float
    overlap_next_s: float


class Coverage(Strict):
    chunks: list[CoverageChunk] = Field(default_factory=list)


class CandidateScores(Strict):
    hook: int
    standalone: int
    central_idea: int
    payoff: int
    edit_boundaries: int
    visual_potential: int
    missing_context: int
    redundancy: int
    risk: int


class Candidate(Strict):
    id: str
    slug: str
    source_in: float
    source_out: float
    context_before: str
    context_after: str
    summary: str
    hook_text: str
    scores: CandidateScores
    notes: str
    verdict: str | None = None


class CandidateSet(Strict):
    coverage: Coverage
    candidates: list[Candidate] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# clip.yaml
# ---------------------------------------------------------------------------


class ClipMeta(Strict):
    id: str
    title: str
    status: Literal[
        "proposed",
        "approved_edit",
        "storyboarded",
        "assets_ready",
        "critiqued",
        "approved_render",
        "rendered",
        "qc_passed",
        "delivered",
    ]
    logline: str
    audience_response: str
    hook: str
    payoff: str


class VisualSpec(Strict):
    kind: Literal["aroll", "broll"]
    treatment: str
    asset_id: str | None = None
    motion: str | None = None
    #: Per-segment crop `x=<n>:y=<n>:w=<n>:h=<n>`, overriding the speaker's `preferred_crop`.
    #: One crop per speaker cannot track someone who moves over a 99-minute recording — the
    #: same correct crop that frames a speaker sitting back clips their head when they lean in.
    crop: str | None = None


class TimelineSegment(Strict):
    id: str
    source_file: str
    source_in: float
    source_out: float
    output_in: float
    output_out: float
    dialogue: str
    speaker: str
    audio: Literal["as-recorded", "duck", "mute"]
    visual: VisualSpec
    transition: str

    @property
    def source_duration(self) -> float:
        return self.source_out - self.source_in

    @property
    def output_duration(self) -> float:
        return self.output_out - self.output_in


class Emphasis(Strict):
    word: str
    style: str


class SubtitleLine(Strict):
    output_range: list[float]
    text: str
    emphasis: list[Emphasis] = Field(default_factory=list)
    position: Literal["bottom-center", "middle-lower"]
    note: str | None = None


class SubtitleSpec(Strict):
    font: str
    base_color: str
    emphasis_palette: list[str]
    position_default: Literal["bottom-center", "middle-lower"]
    lines: list[SubtitleLine] = Field(default_factory=list)


class Asset(Strict):
    id: str
    provider: str
    provider_asset_id: str
    source_url: str
    license: str
    entitlement: Literal["free", "subscription", "purchased"]
    download_date: str
    creator: str
    credit_required: bool
    width: int
    height: int
    fps: float
    duration_s: float
    file: str
    sha256: str | None = None
    used_in_segments: list[str] = Field(default_factory=list)


class OutputSpec(Strict):
    aspect: str
    resolution: str
    fps: float
    duration_s: float


class ThumbnailSpec(Strict):
    first_frame_text: str
    hierarchy: str
    placement: str


class RenderVersion(Strict):
    version: int
    preview: str | None = None
    finals: dict[str, str] = Field(default_factory=dict)
    rendered_at: str
    qc: str | None = None


class RenderSpec(Strict):
    versions: list[RenderVersion] = Field(default_factory=list)


class Clip(Strict):
    clip: ClipMeta
    timeline: list[TimelineSegment]
    subtitles: SubtitleSpec
    assets: list[Asset] = Field(default_factory=list)
    output: OutputSpec
    thumbnail: ThumbnailSpec
    render: RenderSpec


# ---------------------------------------------------------------------------
# Loaders / savers
# ---------------------------------------------------------------------------


def _read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"missing YAML file: {path} — create it before running this step")
    return yaml.safe_load(path.read_text())


def _write_yaml(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=10_000))


def _dump(model: BaseModel) -> Any:
    return model.model_dump(mode="json", by_alias=True)


def load_episode(path: str | Path) -> Episode:
    return Episode.model_validate(_read_yaml(Path(path)))


def save_episode(path: str | Path, episode: Episode) -> None:
    _write_yaml(Path(path), _dump(episode))


def load_clip(path: str | Path) -> Clip:
    return Clip.model_validate(_read_yaml(Path(path)))


def save_clip(path: str | Path, clip: Clip) -> None:
    _write_yaml(Path(path), _dump(clip))


def load_candidates(path: str | Path) -> CandidateSet:
    return CandidateSet.model_validate(_read_yaml(Path(path)))


def save_candidates(path: str | Path, candidates: CandidateSet) -> None:
    _write_yaml(Path(path), _dump(candidates))


def load_transcript(path: str | Path) -> Transcript:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"missing transcript: {p} — run the transcription step first")
    return Transcript.model_validate(json.loads(p.read_text()))


def save_transcript(path: str | Path, transcript: Transcript) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_dump(transcript), indent=2) + "\n")


def load_coverage(path: str | Path) -> Coverage:
    raw = _read_yaml(Path(path))
    if "coverage" not in raw:
        raise ValueError(f"{path}: missing top-level `coverage` block")
    return Coverage.model_validate(raw["coverage"])


def save_coverage(path: str | Path, coverage: Coverage) -> None:
    _write_yaml(Path(path), {"coverage": _dump(coverage)})


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------

_TIME_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{1,2}(?:\.\d{1,6})?)$")


def parse_mmss(s: str) -> float:
    """`MM:SS.mmm`, `M:SS` or `HH:MM:SS.mmm` → seconds."""
    text = s.strip()
    m = _TIME_RE.match(text)
    if not m:
        raise ValueError(f"unparseable timestamp {s!r} — expected MM:SS.mmm, M:SS or HH:MM:SS.mmm")
    hours, minutes, seconds = m.group(1), int(m.group(2)), float(m.group(3))
    if seconds >= 60.0:
        raise ValueError(f"timestamp {s!r} has seconds >= 60")
    if hours is not None and minutes >= 60:
        raise ValueError(f"timestamp {s!r} has minutes >= 60 alongside an hours field")
    return int(hours or 0) * 3600 + minutes * 60 + seconds


def fmt_mmss(seconds: float) -> str:
    """seconds → `MM:SS.mmm`, or `H:MM:SS.mmm` at/over one hour."""
    if seconds < 0:
        raise ValueError(f"cannot format negative time {seconds}")
    ms_total = int(round(seconds * 1000))
    hours, rem = divmod(ms_total, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}.{ms:03d}"
    return f"{minutes:02d}:{secs:02d}.{ms:03d}"


def parse_range(s: str) -> tuple[float, float]:
    """`A-B` where A and B are timestamps → (start_s, end_s)."""
    parts = [p for p in s.strip().split("-") if p.strip()]
    if len(parts) != 2:
        raise ValueError(f"unparseable range {s!r} — expected `MM:SS.mmm-MM:SS.mmm`")
    start, end = parse_mmss(parts[0]), parse_mmss(parts[1])
    if end < start:
        raise ValueError(f"range {s!r} ends before it starts")
    return start, end


def fmt_range(start: float, end: float) -> str:
    return f"{fmt_mmss(start)}-{fmt_mmss(end)}"


def close(a: float, b: float, eps: float = EPSILON) -> bool:
    return abs(a - b) <= eps


def tokenize(text: str) -> list[str]:
    """Lowercased word tokens — the unit of text comparison across surfaces."""
    return re.findall(r"[a-z0-9']+", text.lower())


def is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    it = iter(haystack)
    return all(tok in it for tok in needle)


# ---------------------------------------------------------------------------
# Markdown tables
# ---------------------------------------------------------------------------


@dataclass
class Table:
    headers: list[str]
    rows: list[list[str]]
    line_no: int = 0

    def row_dicts(self) -> list[dict[str, str]]:
        return [dict(zip(self.headers, row)) for row in self.rows]


_CELL_SPLIT = re.compile(r"(?<!\\)\|")
_SEP_CELL = re.compile(r"^:?-{1,}:?$")


def _split_row(line: str) -> list[str]:
    text = line.strip().removeprefix("|").removesuffix("|")
    return [c.strip().replace("\\|", "|") for c in _CELL_SPLIT.split(text)]


def _is_separator(cells: list[str]) -> bool:
    return bool(cells) and all(_SEP_CELL.match(c.replace(" ", "")) for c in cells)


def _is_table_line(line: str) -> bool:
    return "|" in line and bool(line.strip())


def parse_md_tables(md_text: str) -> list[Table]:
    """Every pipe table in `md_text`. Leading/trailing pipes and padding optional.

    A table is a run of adjacent pipe-bearing lines whose second line is a `|---|`
    separator. Runs without one are prose, not tables, and are left alone; a table's
    rows must all carry the header's cell count or parsing fails loudly.
    """
    lines = md_text.splitlines()
    tables: list[Table] = []
    i = 0
    while i < len(lines):
        if not _is_table_line(lines[i]):
            i += 1
            continue
        block_start = i
        block = []
        while i < len(lines) and _is_table_line(lines[i]):
            block.append(lines[i])
            i += 1
        if len(block) < 2 or not _is_separator(_split_row(block[1])):
            continue
        headers = _split_row(block[0])
        rows = []
        for offset, raw in enumerate(block[2:], start=block_start + 3):
            cells = _split_row(raw)
            if len(cells) != len(headers):
                raise ValueError(
                    f"markdown table row at line {offset} has {len(cells)} cells but the "
                    f"header has {len(headers)}: {raw.strip()!r}"
                )
            rows.append(cells)
        tables.append(Table(headers=headers, rows=rows, line_no=block_start + 1))
    return tables


def _norm(h: str) -> str:
    return h.strip().lower()


def find_table(tables: list[Table], required_headers: list[str]) -> Table:
    """The one table carrying `required_headers` in that order. Fails loudly otherwise."""
    want = [_norm(h) for h in required_headers]
    matches = [t for t in tables if [_norm(h) for h in t.headers] == want]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        raise ValueError(
            f"found {len(matches)} tables with headers {required_headers} — "
            "the parse contract requires exactly one"
        )
    best, best_missing = None, None
    for t in tables:
        present = {_norm(h) for h in t.headers}
        missing = [h for h in required_headers if _norm(h) not in present]
        if best_missing is None or len(missing) < len(best_missing):
            best, best_missing = t, missing
    if best is None:
        raise ValueError(
            f"no markdown tables found; expected one with headers {required_headers}"
        )
    if best_missing:
        raise ValueError(
            f"no table with headers {required_headers}; closest is the table at line "
            f"{best.line_no} with headers {best.headers} — missing columns: {best_missing}"
        )
    raise ValueError(
        f"no table with headers {required_headers} in that order; closest is the table at "
        f"line {best.line_no} with headers {best.headers} — reorder its columns to match"
    )


# ---------------------------------------------------------------------------
# Files and media
# ---------------------------------------------------------------------------


def sha256_file(path: str | Path) -> str:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cannot hash missing file: {p}")
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _fraction(value: str) -> float:
    num, _, den = value.partition("/")
    denom = float(den) if den else 1.0
    if denom == 0.0:
        raise ValueError(f"ffprobe returned a zero-denominator frame rate: {value!r}")
    return float(num) / denom


def ffprobe_media(path: str | Path) -> MediaProbe:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"cannot probe missing media file: {p}")
    cmd = [
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(p),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe failed on {p} (exit {proc.returncode}): {proc.stderr.strip()}")
    data = json.loads(proc.stdout)
    streams = data.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = data.get("format", {}).get("duration")
    if duration is None:
        raise RuntimeError(f"ffprobe reported no container duration for {p}")
    return MediaProbe(
        duration_s=round(float(duration), 3),
        width=int(video["width"]) if video else None,
        height=int(video["height"]) if video else None,
        fps=round(_fraction(video["r_frame_rate"]), 4) if video else None,
        video_codec=video["codec_name"] if video else None,
        audio_codec=audio["codec_name"] if audio else None,
        audio_channels=int(audio["channels"]) if audio else None,
        sample_rate=int(audio["sample_rate"]) if audio else None,
    )
