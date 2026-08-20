#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "httpx>=0.27",
# ]
# ///
"""Stage 8 step 3 — force-align the manifest's verbatim text to the FINAL audio.

Word timings come from exactly one source, named explicitly:

* `--words-json PATH` — a transcript.json-shaped `words` array **for this audio**
  (the documented input mode when timings already exist), or
* re-transcription of `--audio` with the configured engine (`assemblyai`, which
  needs `ASSEMBLYAI_API_KEY`, or `mlx-whisper`, which runs locally).

There is no fallback between them: a missing key or an unavailable engine is an
error, never a silent switch to the other path.

The manifest's expected text (the concatenation of `subtitles.lines[].text` in
output order) is aligned to the hypothesis with `difflib.SequenceMatcher` over
normalised tokens. Each line's display window is first-matched-word start →
last-matched-word end, clamped non-overlapping and to the configured minimum
display time. If more than 10% of the expected words do not match, the render's
audio does not say what the manifest claims — that is an upstream bug and this
script exits 1 with the unmatched spans rather than papering over it.

Output: `subtitles/v<N>.ass`, PlayRes = the profile resolution, styled from
`clip.subtitles` + `config/defaults.yaml`, with per-word emphasis as inline
override tags (`{\\b1\\c&H..&}word{\\r}`).
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from pslib import (
    EPSILON,
    Clip,
    SubtitleLine,
    fmt_mmss,
    load_clip,
    load_episode,
    tokenize,
)
from psmedia import (
    SafeZones,
    SubtitleConfig,
    ass_color,
    episode_root_for,
    load_config,
    parse_hex_color,
    profile_dims,
    resolve_profile,
    run_checked,
)

console = Console()
app = typer.Typer(add_completion=False)

UNMATCHED_FRACTION_LIMIT = 0.10
MIDDLE_LOWER_HEIGHT_FRACTION = 0.38   # MarginV for `middle-lower`, as a fraction of PlayResY
FONT_SIZE_HEIGHT_FRACTION = 0.0437    # 84px at 1920 — the storyboard's reference size (an upper bound)
MIN_FONT_HEIGHT_FRACTION = 0.015      # ~29px at 1920: below this the line is unreadable, not "smaller"

# Glyph advances in em for Inter Semibold, bucketed. Used to size the font so a legal
# line cannot soft-wrap inside the Remotion subtitle box (which is exactly the
# horizontal safe zone: PlayResX − MarginL − MarginR). Deliberately generous — an
# overestimate shrinks the font, an underestimate lets a line wrap unexpectedly.
NARROW_CHARS = "ijltfrI.,;:!'|()[]{}/\\ "
WIDE_CHARS = "mwMW@%"
ADVANCE_NARROW, ADVANCE_DEFAULT, ADVANCE_UPPER, ADVANCE_WIDE = 0.34, 0.56, 0.68, 0.92
ASSEMBLYAI_BASE = "https://api.assemblyai.com/v2"

NAMED_COLORS: dict[str, str] = {
    "gold": "#FFD34D", "amber": "#FFBF00", "yellow": "#FFE44D", "orange": "#FF9E4D",
    "red": "#FF5A4D", "pink": "#FF7AC8", "magenta": "#E24DFF", "purple": "#9B6DFF",
    "blue": "#4DA6FF", "cyan": "#4DE8FF", "teal": "#4DE0C0", "green": "#6BE04D",
    "lime": "#C6FF4D", "white": "#FFFFFF",
}
PALETTE_MATCH_LIMIT = 160.0   # max RGB distance between a style's colour name and a palette entry
BOLD_WEIGHTS = {"bold", "semibold", "heavy", "black"}
PLAIN_WEIGHTS = {"regular", "normal", "book", "light"}


@dataclass
class HypWord:
    token: str
    start: float
    end: float
    raw: str


@dataclass
class AlignedLine:
    index: int
    line: SubtitleLine
    start: float
    end: float
    matched: int
    expected: int
    display_lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Word timings
# ---------------------------------------------------------------------------


def words_from_payload(payload: object, where: str) -> list[HypWord]:
    if isinstance(payload, dict):
        if "words" not in payload:
            raise ValueError(f"{where}: object has no `words` key (keys: {sorted(payload)})")
        raw_words = payload["words"]
    elif isinstance(payload, list):
        raw_words = payload
    else:
        raise ValueError(f"{where}: expected a transcript.json object or a bare words array, got {type(payload).__name__}")
    if not raw_words:
        raise ValueError(f"{where}: the words array is empty — there is nothing to align against")

    out: list[HypWord] = []
    for i, item in enumerate(raw_words):
        if not isinstance(item, dict):
            raise ValueError(f"{where}: words[{i}] is {type(item).__name__}, expected an object")
        text = next((item[k] for k in ("w", "word", "text") if k in item), None)
        if text is None:
            raise ValueError(f"{where}: words[{i}] has no `w`/`word`/`text` key (keys: {sorted(item)})")
        for key in ("start", "end"):
            if key not in item:
                raise ValueError(f"{where}: words[{i}] ({text!r}) has no `{key}` — word timings are required")
        start, end = float(item["start"]), float(item["end"])
        if end < start:
            raise ValueError(f"{where}: words[{i}] ({text!r}) ends {end}s before it starts {start}s")
        # One source word can normalise to several tokens ("well-known"); each carries the word's span.
        out += [HypWord(token=tok, start=start, end=end, raw=str(text)) for tok in tokenize(str(text))]
    if not out:
        raise ValueError(f"{where}: no alignable tokens after normalisation — the words array is all punctuation")
    return out


def load_words_json(path: Path) -> list[HypWord]:
    if not path.is_file():
        raise typer.BadParameter(f"--words-json {path} does not exist")
    return words_from_payload(json.loads(path.read_text()), f"--words-json {path}")


def transcribe_assemblyai(audio: Path, language: str, poll_seconds: float) -> list[HypWord]:
    import httpx

    key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not key:
        raise RuntimeError(
            "engine assemblyai needs ASSEMBLYAI_API_KEY in the environment — export it, "
            "or run with --engine mlx-whisper, or supply --words-json"
        )
    headers = {"authorization": key}
    with httpx.Client(timeout=httpx.Timeout(600.0)) as client:
        logger.info(f"uploading {audio.name} ({audio.stat().st_size / 1e6:.1f} MB) to AssemblyAI")
        up = client.post(f"{ASSEMBLYAI_BASE}/upload", headers=headers, content=audio.read_bytes())
        up.raise_for_status()
        audio_url = up.json()["upload_url"]

        created = client.post(
            f"{ASSEMBLYAI_BASE}/transcript",
            headers=headers,
            json={"audio_url": audio_url, "language_code": language, "punctuate": True, "format_text": True},
        )
        created.raise_for_status()
        tid = created.json()["id"]
        logger.info(f"assemblyai transcript {tid} queued")
        while True:
            got = client.get(f"{ASSEMBLYAI_BASE}/transcript/{tid}", headers=headers)
            got.raise_for_status()
            body = got.json()
            if body["status"] == "completed":
                break
            if body["status"] == "error":
                raise RuntimeError(f"assemblyai transcript {tid} failed: {body.get('error')}")
            time.sleep(poll_seconds)
    words = [{"w": w["text"], "start": w["start"] / 1000.0, "end": w["end"] / 1000.0} for w in body["words"]]
    return words_from_payload({"words": words}, f"assemblyai transcript {tid}")


MLX_DRIVER = """
import json, sys
import mlx_whisper
audio, model, out = sys.argv[1], sys.argv[2], sys.argv[3]
# condition_on_previous_text=False is NOT a tuning preference — with the default (True) the
# decoder conditions each window on its own prior output and can silently DROP a passage it
# considers redundant. Measured: 7 seconds of speech vanished from one clip (88.4-94.4s);
# transcribing that window alone returned the sentence perfectly. The audio was fine.
# The failure then surfaces downstream as "these subtitle lines matched no words at all",
# which reads like a manifest error and sends you to debug the wrong file.
result = mlx_whisper.transcribe(
    audio, path_or_hf_repo=model, word_timestamps=True, condition_on_previous_text=False
)
words = [
    {"w": w["word"], "start": float(w["start"]), "end": float(w["end"])}
    for seg in result["segments"] for w in seg.get("words", [])
]
with open(out, "w") as fh:
    json.dump({"words": words}, fh)
"""


def transcribe_mlx_whisper(audio: Path, model: str, pin: str) -> list[HypWord]:
    out_json = audio.parent / f".{audio.stem}.mlx-words.json"
    logger.info(f"transcribing {audio.name} locally with mlx-whisper ({model})")
    run_checked(
        ["uv", "run", "--quiet", "--with", pin, "python", "-c", MLX_DRIVER, str(audio), model, str(out_json)],
        what=f"mlx-whisper transcription of {audio}",
    )
    words = words_from_payload(json.loads(out_json.read_text()), f"mlx-whisper output for {audio}")
    out_json.unlink()
    return words


# ---------------------------------------------------------------------------
# Alignment
# ---------------------------------------------------------------------------


def expected_tokens(clip: Clip) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for idx, line in enumerate(clip.subtitles.lines):
        toks = tokenize(line.text)
        if not toks:
            raise ValueError(f"subtitle line {idx + 1} has no words: {line.text!r}")
        out += [(idx, tok) for tok in toks]
    if not out:
        raise ValueError("clip.yaml subtitles.lines is empty — nothing to align")
    return out


def match_map(expected: list[str], hypothesis: list[str]) -> dict[int, int]:
    matcher = SequenceMatcher(None, expected, hypothesis, autojunk=False)
    return {
        i + k: j + k
        for i, j, size in matcher.get_matching_blocks()
        for k in range(size)
    }


def unmatched_spans(
    expected: list[tuple[int, str]], matched: dict[int, int], lines: list[SubtitleLine]
) -> list[str]:
    # Group consecutive tokens by (matched?, line): each unmatched group is one span,
    # and a span never straddles two subtitle lines.
    keyed = [(i in matched, line_idx, token) for i, (line_idx, token) in enumerate(expected)]
    return [
        f"line {line_idx + 1} ({lines[line_idx].text!r}): unmatched "
        f"{' '.join(token for _, _, token in group)!r}"
        for (is_matched, line_idx), group in groupby(keyed, key=lambda row: (row[0], row[1]))
        if not is_matched
    ]


def align(clip: Clip, hyp: list[HypWord]) -> tuple[list[AlignedLine], list[str], float]:
    expected = expected_tokens(clip)
    matched = match_map([t for _, t in expected], [w.token for w in hyp])
    fraction = 1.0 - (len(matched) / len(expected))
    spans = unmatched_spans(expected, matched, clip.subtitles.lines)

    aligned: list[AlignedLine] = []
    for idx, line in enumerate(clip.subtitles.lines):
        own = [i for i, (line_idx, _) in enumerate(expected) if line_idx == idx]
        hits = [matched[i] for i in own if i in matched]
        aligned.append(
            AlignedLine(
                index=idx,
                line=line,
                start=min(hyp[h].start for h in hits) if hits else -1.0,
                end=max(hyp[h].end for h in hits) if hits else -1.0,
                matched=len(hits),
                expected=len(own),
            )
        )
    return aligned, spans, fraction


def clamp_windows(
    aligned: list[AlignedLine],
    min_display: float,
    clip_duration: float,
    max_cps: float | None = None,
) -> None:
    """Non-overlapping, ordered, at least `min_display` long, inside the clip.

    A card's natural window is first-matched-word start → last-matched-word end, which
    ignores the silence AFTER the line. When the speaker then pauses, the card is forced
    to be faster than it needs to be, and the only way to satisfy a chars-per-second limit
    is to delete words from the caption — so the subtitle stops matching the audio. That
    is a fidelity loss caused purely by timing bookkeeping.

    So when `max_cps` is given, each card may hold into the gap before the next card
    (or the end of the clip) for exactly as long as its own reading speed requires. The
    hold never overlaps the next card, never invents time that is not there, and never
    extends a card that already reads comfortably.
    """
    problems: list[str] = []
    previous_end = 0.0
    for n, item in enumerate(aligned):
        start = max(item.start, previous_end)
        end = max(item.end, start + min_display)
        if max_cps and max_cps > 0:
            visible = len(item.line.text)
            needed = start + visible / max_cps
            if needed > end:
                # Only into real silence: stop at the next card's start (or the clip end).
                ceiling = aligned[n + 1].start if n + 1 < len(aligned) else clip_duration
                end = min(needed, max(end, ceiling))
        if end > clip_duration + EPSILON:
            end = clip_duration
        if end - start < min_display - EPSILON:
            problems.append(
                f"line {item.index + 1} ({item.line.text!r}) can only occupy "
                f"{max(end - start, 0.0):.3f}s at {start:.3f}s — the configured minimum display is "
                f"{min_display:.3f}s and the clip ends at {clip_duration:.3f}s; the manifest asks for "
                f"more subtitle lines than the audio has room for"
            )
        item.start, item.end = start, end
        previous_end = end
    if problems:
        raise ValueError("subtitle windows cannot satisfy the readability limits:\n  " + "\n  ".join(problems))


# ---------------------------------------------------------------------------
# Styling
# ---------------------------------------------------------------------------


def resolve_emphasis_color(style: str, palette: list[str]) -> tuple[bool, str]:
    """`bold-gold` + the episode palette → (bold, "#RRGGBB"). Unknown names fail loudly."""
    weight, _, color_name = style.partition("-")
    if not color_name:
        raise ValueError(f"emphasis style {style!r} — expected `<weight>-<colour>`, e.g. bold-gold")
    if weight in BOLD_WEIGHTS:
        bold = True
    elif weight in PLAIN_WEIGHTS:
        bold = False
    else:
        raise ValueError(
            f"emphasis style {style!r}: unknown weight {weight!r} "
            f"(known: {sorted(BOLD_WEIGHTS | PLAIN_WEIGHTS)})"
        )
    if color_name not in NAMED_COLORS:
        raise ValueError(
            f"emphasis style {style!r}: unknown colour {color_name!r} (known: {sorted(NAMED_COLORS)})"
        )
    if not palette:
        raise ValueError("clip.yaml subtitles.emphasis_palette is empty but a line requests emphasis")
    want = parse_hex_color(NAMED_COLORS[color_name])
    scored = sorted(
        ((sum((a - b) ** 2 for a, b in zip(want, parse_hex_color(entry))) ** 0.5, entry) for entry in palette)
    )
    distance, chosen = scored[0]
    if distance > PALETTE_MATCH_LIMIT:
        raise ValueError(
            f"emphasis style {style!r} names {NAMED_COLORS[color_name]} but the episode "
            f"emphasis_palette is {palette} — add the colour to the palette or restyle the line"
        )
    return bold, chosen


def emphasis_runs(raw_tokens: list[str], line: SubtitleLine) -> dict[int, tuple[int, str]]:
    """token index → (run length, style) for every emphasised word occurrence in the line."""
    normalised = [tokenize(t) for t in raw_tokens]
    flat = [n[0] if n else "" for n in normalised]
    runs: dict[int, tuple[int, str]] = {}
    for emph in line.emphasis:
        needle = tokenize(emph.word)
        if not needle:
            raise ValueError(f"emphasis word {emph.word!r} normalises to nothing")
        hits = [i for i in range(len(flat) - len(needle) + 1) if flat[i:i + len(needle)] == needle]
        if not hits:
            raise ValueError(
                f"emphasis word {emph.word!r} does not appear in subtitle text {line.text!r} — "
                "clip.yaml disagrees with itself (validate_clip.py invariant 8)"
            )
        for i in hits:
            runs[i] = (len(needle), emph.style)
    return runs


def wrap_tokens(raw_tokens: list[str], max_chars: int, max_lines: int, where: str) -> list[list[int]]:
    """Split token indices into ≤ max_lines display lines, breaking at natural phrase ends."""
    text = " ".join(raw_tokens)
    if len(text) <= max_chars:
        return [list(range(len(raw_tokens)))]
    if max_lines < 2:
        raise ValueError(f"{where}: {len(text)} chars exceeds max_chars_per_line {max_chars} and max_lines is 1")

    def width(lo: int, hi: int) -> int:
        return len(" ".join(raw_tokens[lo:hi]))

    candidates = [
        (
            abs(width(0, i) - width(i, len(raw_tokens)))
            - (12 if raw_tokens[i - 1].rstrip().endswith((",", ";", ":", "—", "-", ".", "?", "!")) else 0),
            i,
        )
        for i in range(1, len(raw_tokens))
        if width(0, i) <= max_chars and width(i, len(raw_tokens)) <= max_chars
    ]
    if not candidates:
        raise ValueError(
            f"{where}: {text!r} ({len(text)} chars) cannot be wrapped into {max_lines} lines of "
            f"{max_chars} chars — shorten the subtitle line in clip.yaml"
        )
    split = min(candidates)[1]
    return [list(range(split)), list(range(split, len(raw_tokens)))]


def escape_ass(text: str) -> str:
    if "{" in text or "}" in text:
        raise ValueError(f"subtitle text may not contain braces (ASS override delimiters): {text!r}")
    return text


def render_text(line: SubtitleLine, cfg: SubtitleConfig, palette: list[str], where: str) -> list[str]:
    raw_tokens = escape_ass(line.text).split()
    runs = emphasis_runs(raw_tokens, line)
    rendered: list[str] = []
    i = 0
    while i < len(raw_tokens):
        run = runs.get(i)
        if run is None:
            rendered.append(raw_tokens[i])
            i += 1
            continue
        length, style = run
        bold, color = resolve_emphasis_color(style, palette)
        body = " ".join(raw_tokens[i:i + length])
        rendered.append(f"{{\\b{1 if bold else 0}\\c{ass_color(color)}&}}{body}{{\\r}}")
        i += length
    groups = wrap_tokens(raw_tokens, cfg.max_chars_per_line, cfg.max_lines, where)
    return [" ".join(rendered[j] for j in group) for group in groups]


_OVERRIDE_BLOCK = re.compile(r"\{[^}]*\}")


def plain_text(rendered: str) -> str:
    """A rendered display line minus its override tags — what the viewer actually sees."""
    return _OVERRIDE_BLOCK.sub("", rendered)


def em_width(text: str) -> float:
    """Rendered width of `text` in em, estimated from the glyph-advance buckets."""
    return sum(
        ADVANCE_NARROW if c in NARROW_CHARS
        else ADVANCE_WIDE if c in WIDE_CHARS
        else ADVANCE_UPPER if c.isupper()
        else ADVANCE_DEFAULT
        for c in text
    )


def fit_font_size(aligned: list[AlignedLine], box_w: int, play_h: int) -> tuple[int, str]:
    """Largest font size at which no rendered line soft-wraps inside the safe box.

    The design size (`FONT_SIZE_HEIGHT_FRACTION` of the frame) is an upper bound, not a
    target: the composition wraps text at `PlayResX − MarginL − MarginR`, so a legal
    42-char line rendered too large would wrap where nobody asked it to.
    """
    design = int(round(play_h * FONT_SIZE_HEIGHT_FRACTION))
    widest_text = max(
        (plain_text(line) for item in aligned for line in item.display_lines), key=em_width
    )
    widest = em_width(widest_text)
    fitted = int(box_w / widest)
    size = min(design, fitted)
    floor = int(round(play_h * MIN_FONT_HEIGHT_FRACTION))
    if size < floor:
        raise ValueError(
            f"the longest subtitle line ({widest_text!r}, {len(widest_text)} chars ≈ {widest:.1f} em) "
            f"only fits the {box_w}px safe box at {size}px, below the {floor}px readability floor — "
            f"shorten the subtitle lines in clip.yaml"
        )
    why = (
        f"design size {design}px (fits the {box_w}px box, which allows {int(box_w / design)} em)"
        if size == design
        else f"{fitted}px — the {box_w}px safe box divided by the widest line ({widest:.1f} em: {widest_text!r})"
    )
    return size, why


def ass_timestamp(seconds: float) -> str:
    hundredths = int(round(seconds * 100))
    h, rem = divmod(hundredths, 360_000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(
    clip: Clip,
    aligned: list[AlignedLine],
    zones: SafeZones,
    play_w: int,
    play_h: int,
    font_size: int,
    style: SubtitleConfig,
) -> str:
    # Two objects, two responsibilities, and they are NOT interchangeable:
    #   `clip.subtitles` (SubtitleSpec, from clip.yaml) owns WHAT the captions say and where —
    #       font, base_color, emphasis_palette, position_default, lines.
    #   `style` (SubtitleConfig, from config/defaults.yaml) owns HOW they are drawn —
    #       outline weight and colour, shadow, border style, plate opacity.
    # Reading a drawing field off the manifest object raises AttributeError at the first one.
    subs = clip.subtitles
    # `border_style: plate` writes a well-formed .ass that NOTHING RENDERS. The Remotion template
    # is the renderer, and it reads exactly three style fields out of this file — Outline,
    # OutlineColour, Shadow (gen-props.mjs) — then draws the caption in CSS. It never reads
    # BorderStyle or BackColour, and Subtitles.tsx has no background-box code at all. So a plate
    # would validate clean, render invisibly, and read as a styling disagreement rather than a bug.
    # Fail here until the plate is wired through the template.
    if style.border_style == "plate":
        raise SystemExit(
            "config subtitles.border_style: plate is NOT IMPLEMENTED — the Remotion template "
            "draws captions in CSS and ignores the .ass BorderStyle/BackColour fields, so a "
            "plate would silently not appear. Use border_style: outline (raise outline_fraction "
            "for more weight), or implement the plate in remotion/src/Subtitles.tsx and pass it "
            "through remotion/gen-props.mjs first."
        )
    header = [
        "[Script Info]",
        "; generated by scripts/align_subtitles.py — timing truth for the render",
        f"Title: {clip.clip.id}",
        "ScriptType: v4.00+",
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        f"PlayResX: {play_w}",
        f"PlayResY: {play_h}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        ",".join(
            [
                "Style: Default", subs.font, str(font_size), ass_color(subs.base_color),
                ass_color(subs.base_color), ass_color(style.outline_color),
                # ASS alpha is INVERSE: 0x00 is opaque, 0xFF fully transparent.
                ass_color("#000000", alpha=max(0, min(255, round((1.0 - style.plate_opacity) * 255)))),
                "0", "0", "0", "0", "100", "100", "0", "0",
                "1",  # plate (3) is rejected above — the template cannot draw it
                f"{max(2, round(font_size * style.outline_fraction))}",
                f"{max(1, round(font_size * style.shadow_fraction))}",
                "2", str(zones.left), str(zones.right), str(zones.bottom), "1",
            ]
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    middle_lower = int(round(play_h * MIDDLE_LOWER_HEIGHT_FRACTION))
    events = [
        "Dialogue: "
        + ",".join(
            [
                "0", ass_timestamp(item.start), ass_timestamp(item.end), "Default", "",
                "0", "0", str(middle_lower if item.line.position == "middle-lower" else 0), "",
                "\\N".join(item.display_lines),
            ]
        )
        for item in aligned
    ]
    return "\n".join([*header, *events]) + "\n"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    audio: Path = typer.Option(..., "--audio", help="The FINAL assembled audio these subtitles must match"),
    version: int = typer.Option(None, "--version", "-v", help="Render version (default: len(render.versions)+1)"),
    words_json: Path = typer.Option(None, "--words-json", help="Existing word timings for --audio (transcript.json-shaped)"),
    engine: str = typer.Option(None, "--engine", help="Re-transcription engine: assemblyai | mlx-whisper (default: config transcription.engine)"),
    whisper_model: str = typer.Option("mlx-community/whisper-tiny", "--whisper-model", help="mlx-whisper model repo"),
    mlx_pin: str = typer.Option("mlx-whisper==0.4.3", "--mlx-pin", help="Pinned mlx-whisper requirement used for the local run"),
    profile_name: str = typer.Option("youtube-shorts", "--profile", help="Platform profile name from episode.yaml"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"),
    config_path: Path = typer.Option(None, "--config", help="Pipeline config (default: config/defaults.yaml)"),
    poll_seconds: float = typer.Option(3.0, "--poll-seconds", help="AssemblyAI poll interval"),
) -> None:
    """Force-align CLIP_DIR's verbatim subtitle text to --audio and emit subtitles/v<N>.ass."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    audio_path = audio if audio.is_absolute() else clip_dir / audio
    if not audio_path.is_file():
        raise typer.BadParameter(f"--audio {audio_path} does not exist — run assemble_audio.py first")
    if words_json is not None and engine is not None:
        raise typer.BadParameter(
            "--words-json and --engine name two different timing sources; pass exactly one"
        )

    root = episode_root_for(clip_dir, episode_root)
    config = load_config(config_path)
    clip = load_clip(clip_dir / "clip.yaml")
    episode = load_episode(root / "episode.yaml")
    profile = resolve_profile(episode, profile_name)
    play_w, play_h = profile_dims(profile)
    cfg = config.subtitles

    if words_json is not None:
        hyp = load_words_json(words_json)
        source = f"--words-json {words_json}"
    else:
        chosen = engine or config.transcription.engine
        if chosen == "assemblyai":
            hyp = transcribe_assemblyai(audio_path, config.transcription.language, poll_seconds)
        elif chosen == "mlx-whisper":
            hyp = transcribe_mlx_whisper(audio_path, whisper_model, mlx_pin)
        else:
            raise typer.BadParameter(
                f"unknown transcription engine {chosen!r} — expected assemblyai or mlx-whisper"
            )
        source = f"engine {chosen}"
    logger.info(f"{len(hyp)} hypothesis tokens from {source}")

    aligned, spans, fraction = align(clip, hyp)
    console.print(
        f"aligned {clip.clip.id}: {100 * (1 - fraction):.1f}% of expected words matched "
        f"({len(clip.subtitles.lines)} lines, {len(hyp)} hypothesis tokens, source: {source})"
    )
    if fraction > UNMATCHED_FRACTION_LIMIT:
        console.print(
            f"[bold red]FAIL[/] {100 * fraction:.1f}% of the manifest's words are absent from the "
            f"rendered audio (limit {100 * UNMATCHED_FRACTION_LIMIT:.0f}%) — the audio does not say what "
            f"clip.yaml claims. Fix the manifest or the edit; do not re-time around it."
        )
        for span in spans:
            console.print(f"  [red]•[/] {span}")
        raise typer.Exit(1)
    empty = [a for a in aligned if a.matched == 0]
    if empty:
        console.print("[bold red]FAIL[/] these subtitle lines matched no words at all, so they cannot be timed:")
        for a in empty:
            console.print(f"  [red]•[/] line {a.index + 1}: {a.line.text!r}")
        raise typer.Exit(1)

    clamp_windows(aligned, cfg.min_display_seconds, clip.output.duration_s,
                  cfg.max_chars_per_second)
    for item in aligned:
        item.display_lines = render_text(
            item.line, cfg, clip.subtitles.emphasis_palette, f"subtitle line {item.index + 1}"
        )
    box_w = play_w - config.safe_zones.left - config.safe_zones.right
    font_size, why = fit_font_size(aligned, box_w, play_h)
    logger.info(f"font size {font_size}px: {why}")

    emphasised = sum(len(tokenize(e.word)) for line in clip.subtitles.lines for e in line.emphasis)
    total_words = sum(len(tokenize(line.text)) for line in clip.subtitles.lines)
    if emphasised > cfg.emphasis_max_word_fraction * total_words:
        logger.warning(
            f"{emphasised}/{total_words} words emphasised "
            f"({emphasised / total_words:.0%} > {cfg.emphasis_max_word_fraction:.0%} guideline)"
        )
    if cfg.font != clip.subtitles.font:
        logger.info(f"clip.yaml font {clip.subtitles.font!r} overrides the config default {cfg.font!r}")
    if cfg.font_fallbacks:
        logger.info(f"font fallbacks (must be installed where the render runs): {cfg.font_fallbacks}")

    n = version if version is not None else len(clip.render.versions) + 1
    out_path = clip_dir / "subtitles" / f"v{n}.ass"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        logger.info(f"regenerating {out_path} from {audio_path.name}")
    out_path.write_text(build_ass(clip, aligned, config.safe_zones, play_w, play_h, font_size, config.subtitles))

    table = RichTable(title=f"Aligned subtitles — {clip.clip.id} v{n}", header_style="bold cyan")
    for column, kwargs in (
        ("#", {"no_wrap": True}), ("Window", {"no_wrap": True}), ("Dur", {"justify": "right"}),
        ("Matched", {"justify": "right"}), ("Pos", {}), ("Text", {}),
    ):
        table.add_column(column, **kwargs)
    for item in aligned:
        table.add_row(
            str(item.index + 1),
            f"{fmt_mmss(item.start)}-{fmt_mmss(item.end)}",
            f"{item.end - item.start:.2f}s",
            f"{item.matched}/{item.expected}",
            item.line.position,
            " / ".join(item.display_lines),
        )
    console.print(table)
    console.print(
        f"[bold green]OK[/] {out_path} — PlayRes {play_w}x{play_h}, font {clip.subtitles.font} "
        f"{font_size}px, {len(aligned)} events"
    )


if __name__ == "__main__":
    app()
