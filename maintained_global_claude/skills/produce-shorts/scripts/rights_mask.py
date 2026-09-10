#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
# ]
# ///
"""Build a "rights mask" for a raw multitrack recording against its PUBLISHED video.

Given a raw transcript (word-level timings) and the published YouTube video, this
determines which spans of the raw recording actually SURVIVED to publication.
Anything that did not survive must never appear in a produced clip.

Method: download the published video's auto-captions (word sequence), align the
raw word sequence against it with difflib.SequenceMatcher, and map the matched
raw words back to raw timestamps. Matched runs -> `published_spans`; the
complement -> `cut_spans`.

FAIL LOUD: if alignment coverage is too low, or the cut total is wildly off the
expected released/raw duration delta, this errors rather than emitting a
permissive mask. A mask that wrongly authorizes unpublished material is the worst
possible output, so every judgement call is biased toward marking a span CUT.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

console = Console()
app = typer.Typer(add_completion=False, help=__doc__)

# --- Tunables -----------------------------------------------------------------

# We align raw<->published word sequences and track cumulative DRIFT
# D(i) = raw_time(i) - published_time(i) at each matched anchor. D rises by exactly
# the length of every editorial removal (raw keeps advancing while published does
# not), so the total cut equals D at the final anchor. Real cuts are sustained
# upward STEPS in D; caption-timing jitter is small non-sustained wiggle.
#
# A step counts as a cut only when D rises by more than this, AND the elevation is
# sustained (see SMOOTH_WINDOW) so a single anomalous anchor cannot invent a cut.
CUT_THRESHOLD_S = 8.0

# Require the elevated drift to hold for this many consecutive anchors (via a
# forward-minimum) before believing it — rejects single-word timestamp spikes.
SMOOTH_WINDOW = 3

# Published spans shorter than this (between two cuts) are absorbed as noise.
MIN_SPAN_S = 1.0

# Final published-span floor, applied AFTER run-validation as a second, independent
# safety layer (defense by construction, not by luck). Nothing shippable is shorter
# than this, so any surviving sub-floor island is dropped into cut_spans rather than
# left as a window a short candidate could fit wholly inside and be wrongly
# authorized. On a clean alignment this removes nothing and barely moves cut_total —
# which is itself a check that such islands are noise, not content.
MIN_PUBLISHED_SPAN_S = 15.0

# --- Boundary corroboration (evidence the method LOCATES cuts, not just counts) ---
# On episode-deutsch-raw, candidate A03 ("a-false-claim-about-how-the-mind-works")
# begins at raw 946.1s; the largest detected removal ends at 946.6s. An independent
# word-level alignment landing on an editorial boundary to within 0.5s is strong
# evidence the drift method finds where cuts actually are, not merely how much was
# cut. Cheap to state here, expensive to rediscover.

# A region only counts as PUBLISHED if it contains at least one VERBATIM matched
# run of this many consecutive words. This is the load-bearing safety rule: the
# drift walk alone can leave a "published" island floating on scattered
# function-word coincidences ("in the", "of", "you"), which — inside cut pre-roll —
# would falsely authorize unreleased audio. Real aired content always carries long
# verbatim runs (median matched block here is 6 words, top blocks 100+); isolated
# 1-2 word hits never reach 8. Any span without such a run is reclassified CUT.
# The two error directions are asymmetric: over-cutting loses a candidate, a false
# publish leaks removed words — so we demand positive evidence before authorizing.
MIN_MATCHED_RUN = 8

# Tolerance applied when TESTING a candidate range against the mask. Alignment is
# word-level, so a published-span boundary can be off by up to roughly one word's
# duration. We allow a range to poke this far past a published-span edge before we
# call it cut. Kept small (< a word) so a real cut is never waved through.
PUBLISH_TOLERANCE_S = 0.75

# Minimum published-word match rate below which the alignment is untrustworthy.
# Auto-captions differ lexically from the raw transcript (disfluencies, ASR
# variance), so ~80% is normal and healthy; the cut-total sanity window is the
# stronger guard. Below 0.70 the alignment is too sparse to trust.
MIN_COVERAGE = 0.70

# Expected cut total sanity window (raw_dur - published_dur should land here).
CUT_MIN_S = 700.0
CUT_MAX_S = 1200.0


# --- VTT / transcript parsing -------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WORD_RE = re.compile(r"[a-z0-9']+")


def _words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


_CUE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2}\.\d{3}) --> ")
_TIME_RE = re.compile(r"<(\d{2}):(\d{2}):(\d{2}\.\d{3})>")


def _hms(h: str, m: str, s: str) -> float:
    return int(h) * 3600 + int(m) * 60 + float(s)


def parse_published_vtt(path: Path) -> tuple[list[str], list[float]]:
    """Ordered published (word, time_s) sequence from a YouTube auto-caption VTT.

    YouTube rolling captions repeat each line: a plain "rolled-up" display line
    plus a line carrying inline `<HH:MM:SS.mmm><c>word</c>` markup with the NEW
    words and their timings. We take only the inline-timed lines so every word
    appears exactly once, carrying its own timestamp.
    """
    if not path.is_file():
        raise FileNotFoundError(f"missing published captions: {path}")
    words: list[str] = []
    times: list[float] = []
    cur: float | None = None
    for line in path.read_text().splitlines():
        m = _CUE_RE.match(line)
        if m:
            cur = _hms(*m.groups())
            continue
        if "<c>" not in line:
            continue
        segs = _TIME_RE.split(line)
        # split() with 3 groups yields: text, h, m, s, text, h, m, s, ...
        seg_times = [cur if cur is not None else 0.0]
        seg_texts = [segs[0]]
        for i in range(1, len(segs), 4):
            seg_times.append(_hms(segs[i], segs[i + 1], segs[i + 2]))
            seg_texts.append(segs[i + 3])
        for t, seg in zip(seg_times, seg_texts):
            for w in _words(_TAG_RE.sub("", seg)):
                words.append(w)
                times.append(t)
    if not words:
        raise ValueError(
            f"{path}: no timed caption lines found — not a YouTube auto-caption VTT"
        )
    return words, times


@dataclass
class RawWord:
    w: str
    start: float
    end: float


def load_raw_words(transcript_json: Path) -> list[RawWord]:
    if not transcript_json.is_file():
        raise FileNotFoundError(f"missing raw transcript: {transcript_json}")
    data = json.loads(transcript_json.read_text())
    words = data.get("words")
    if not words:
        raise ValueError(f"{transcript_json}: no word-level timings (`words` empty)")
    return [RawWord(w=w["w"], start=float(w["start"]), end=float(w["end"])) for w in words]


# --- Subtitle download --------------------------------------------------------

def download_captions(url: str, out_dir: Path) -> Path:
    """Fetch published auto-captions via yt-dlp. Returns the VTT path.

    Prefers the word-timed `en-orig` (auto) track; falls back to `en`. STOPS
    loudly if no captions exist at all — we never transcribe audio locally.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = out_dir / "published"
    existing = sorted(out_dir.glob("published*.vtt"))
    if not existing:
        cmd = [
            "yt-dlp", "--write-auto-subs", "--write-subs",
            "--sub-format", "vtt", "--skip-download",
            "--sub-langs", "en.*", "-o", str(stem), url,
        ]
        logger.info("downloading captions: {}", " ".join(cmd))
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"yt-dlp failed ({res.returncode}):\n{res.stderr}")
        existing = sorted(out_dir.glob("published*.vtt"))
    if not existing:
        raise RuntimeError(
            f"no captions available for {url} — refusing to transcribe audio "
            "locally. STOP: cannot build a rights mask without a published word "
            "sequence."
        )
    # Prefer the auto (en-orig) word-timed track.
    for p in existing:
        if "orig" in p.name:
            return p
    return existing[0]


# --- Alignment ----------------------------------------------------------------

@dataclass
class Alignment:
    published_spans: list[tuple[float, float]]
    cut_spans: list[tuple[float, float]]
    coverage: float
    matched_pub_words: int
    total_pub_words: int
    n_internal_cuts: int


def align(raw: list[RawWord], pub_words: list[str], pub_times: list[float],
          source_duration: float) -> Alignment:
    # Flatten raw to a token stream, remembering each token's raw start/end time.
    flat: list[str] = []
    raw_t: list[float] = []
    raw_end: list[float] = []
    for w in raw:
        for tok in _words(w.w):
            flat.append(tok)
            raw_t.append(w.start)
            raw_end.append(w.end)

    sm = SequenceMatcher(a=flat, b=pub_words, autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size > 0]

    # Raw-time interval of every SUBSTANTIAL matched run — the positive evidence a
    # span actually aired. (raw_start_of_first_word, raw_end_of_last_word, size).
    runs = [(raw_t[b.a], raw_end[b.a + b.size - 1], b.size)
            for b in blocks if b.size >= MIN_MATCHED_RUN]

    def has_substantial_run(s: float, e: float) -> bool:
        """True if a MIN_MATCHED_RUN+ verbatim run lies inside [s, e]."""
        return any(s - 0.01 <= rs and re_ <= e + 0.01 for rs, re_, _ in runs)

    # Dense anchors: every matched token pair -> (raw_time, published_time),
    # monotonic in both axes (matching blocks are strictly increasing).
    anchors: list[tuple[float, float]] = []
    matched_pub_words = 0
    for b in blocks:
        matched_pub_words += b.size
        for k in range(b.size):
            anchors.append((raw_t[b.a + k], pub_times[b.b + k]))

    if len(anchors) < 2:
        raise RuntimeError("alignment produced <2 anchors — cannot build a mask")

    coverage = matched_pub_words / max(1, len(pub_words))

    # Cumulative drift per anchor, smoothed by a forward-minimum so a lone spike
    # in D cannot register as a cut (the elevation must persist SMOOTH_WINDOW long).
    drift = [r - p for r, p in anchors]
    n = len(drift)
    smooth = [min(drift[i:i + SMOOTH_WINDOW]) for i in range(n)]

    # Walk anchors; every sustained upward step in drift beyond CUT_THRESHOLD_S is a
    # cut of that step's height, placed ending at the current raw time. The running
    # plateau telescopes so total cut == final smoothed drift ~= raw_dur - pub_dur.
    cut: list[list[float]] = []
    plateau = 0.0
    for (r, _p), d in zip(anchors, smooth):
        if d > plateau + CUT_THRESHOLD_S:
            cut.append([max(0.0, r - (d - plateau)), r])
            plateau = d
    # Tail: any raw time past the final anchor the published side never reached.
    rN = anchors[-1][0]
    if source_duration - rN > CUT_THRESHOLD_S:
        cut.append([rN, source_duration])

    # Merge touching/overlapping cuts.
    cut.sort()
    merged: list[list[float]] = []
    for s, e in cut:
        if merged and s <= merged[-1][1] + 0.001:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])

    # Candidate published spans = complement of the drift cuts.
    candidates: list[tuple[float, float]] = []
    prev = 0.0
    for s, e in merged:
        if s - prev >= MIN_SPAN_S:
            candidates.append((prev, s))
        prev = e
    if source_duration - prev >= MIN_SPAN_S:
        candidates.append((prev, source_duration))

    # SAFETY GATE: a candidate is PUBLISHED only if it carries a substantial
    # verbatim run. Islands held up by scattered function-word hits (the pre-roll
    # failure mode) fail this and are reclassified CUT. cut_spans is then rebuilt
    # as the exact complement of the validated published spans, so the mask is
    # internally consistent and every published second is positively evidenced.
    # Two independent gates, both required: a substantial verbatim run AND a
    # minimum span length. Either alone would clear the pre-roll here; together the
    # mask is safe by construction rather than by no candidate being small enough.
    published_spans = [(round(s, 3), round(e, 3)) for s, e in candidates
                       if has_substantial_run(s, e) and (e - s) >= MIN_PUBLISHED_SPAN_S]
    reclassified = len(candidates) - len(published_spans)
    dropped_short = sum(1 for s, e in candidates
                        if has_substantial_run(s, e) and (e - s) < MIN_PUBLISHED_SPAN_S)

    cut_list: list[tuple[float, float]] = []
    prev = 0.0
    for s, e in published_spans:
        if s - prev > 0.01:
            cut_list.append((round(prev, 3), round(s, 3)))
        prev = e
    if source_duration - prev > 0.01:
        cut_list.append((round(prev, 3), round(source_duration, 3)))
    cut_spans = cut_list

    if reclassified:
        logger.info("reclassified {} island(s) as CUT ({} lacked a >={}-word run, "
                    "{} were < {}s)", reclassified, reclassified - dropped_short,
                    MIN_MATCHED_RUN, dropped_short, MIN_PUBLISHED_SPAN_S)

    n_internal = sum(1 for s, e in cut_spans
                     if s > CUT_THRESHOLD_S and e < source_duration - CUT_THRESHOLD_S)

    return Alignment(
        published_spans=published_spans,
        cut_spans=cut_spans,
        coverage=coverage,
        matched_pub_words=matched_pub_words,
        total_pub_words=len(pub_words),
        n_internal_cuts=n_internal,
    )


# --- Public API ---------------------------------------------------------------

def spans_are_published(mask: dict, source_in: float, source_out: float,
                        tolerance: float = PUBLISH_TOLERANCE_S) -> bool:
    """True only when the ENTIRE [source_in, source_out] range survived to publication.

    A range is authorized only if it lies (within `tolerance` seconds of slop at
    each end) wholly inside a single published span. Any overlap with a cut span
    is disqualifying. Bias is toward CUT: on malformed input or an inverted range,
    return False rather than authorize.
    """
    if source_out < source_in:
        return False
    for s, e in mask.get("published_spans", []):
        if source_in >= s - tolerance and source_out <= e + tolerance:
            return True
    return False


def load_mask(path: str | Path) -> dict:
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"missing rights mask: {p} — run rights_mask.py build first")
    return yaml.safe_load(p.read_text())


# --- CLI ----------------------------------------------------------------------

@app.command()
def build(
    episode_dir: Path = typer.Argument(..., help="Episode workspace directory"),
    published_url: str = typer.Argument(..., help="Published YouTube URL"),
    published_duration_s: float = typer.Option(..., help="Published video duration (s)"),
    source_duration_s: float = typer.Option(0.0, help="Raw source duration (s); default = last raw word end"),
    transcript: Path = typer.Option(None, help="Raw transcript.json (default: <dir>/transcript/transcript.json)"),
) -> None:
    """Build rights-mask.yaml for an episode."""
    episode_dir = episode_dir.resolve()
    tpath = transcript or episode_dir / "transcript" / "transcript.json"
    raw = load_raw_words(tpath)
    src_dur = source_duration_s or raw[-1].end
    logger.info("raw words: {}  source_duration: {:.2f}s", len(raw), src_dur)

    vtt = download_captions(published_url, episode_dir / "published")
    pub_words, pub_times = parse_published_vtt(vtt)
    logger.info("published words: {}  (from {}, last t={:.1f}s)",
                len(pub_words), vtt.name, pub_times[-1])

    al = align(raw, pub_words, pub_times, src_dur)
    cut_total = sum(e - s for s, e in al.cut_spans)
    pub_total = sum(e - s for s, e in al.published_spans)
    expected_cut = src_dur - published_duration_s

    _report(al, cut_total, pub_total, expected_cut, src_dur, published_duration_s)

    # FAIL LOUD guards -- never ship an untrustworthy or permissive mask.
    if al.coverage < MIN_COVERAGE:
        raise typer.Exit(
            _fatal(f"alignment coverage {al.coverage:.2%} < {MIN_COVERAGE:.0%} — "
                   "alignment untrustworthy, refusing to write mask"))
    if not (CUT_MIN_S <= cut_total <= CUT_MAX_S):
        raise typer.Exit(
            _fatal(f"cut total {cut_total:.0f}s outside sanity window "
                   f"[{CUT_MIN_S:.0f}, {CUT_MAX_S:.0f}]s (expected ~{expected_cut:.0f}s) — "
                   "alignment is wrong, refusing to write mask"))

    mask = {
        "source_duration_s": round(src_dur, 2),
        "published_duration_s": published_duration_s,
        "published_url": published_url,
        "method": "word-level sequence alignment of raw transcript against published auto-captions",
        "alignment_coverage": round(al.coverage, 4),
        "min_matched_run_words": MIN_MATCHED_RUN,
        "min_published_span_s": MIN_PUBLISHED_SPAN_S,
        "cut_threshold_s": CUT_THRESHOLD_S,
        "publish_tolerance_s": PUBLISH_TOLERANCE_S,
        "cut_total_s": round(cut_total, 1),
        "published_total_s": round(pub_total, 1),
        "n_internal_cuts": al.n_internal_cuts,
        "published_spans": [[s, e] for s, e in al.published_spans],
        "cut_spans": [[s, e] for s, e in al.cut_spans],
    }
    out = episode_dir / "rights-mask.yaml"
    out.write_text(yaml.safe_dump(mask, sort_keys=False, default_flow_style=None))
    logger.success("wrote {}", out)


@app.command()
def check(
    episode_dir: Path = typer.Argument(..., help="Episode workspace directory"),
    candidates_glob: str = typer.Option("chunks/candidates2-*.yaml", help="Glob for candidate files"),
) -> None:
    """Check candidate clips against an existing rights-mask.yaml."""
    episode_dir = episode_dir.resolve()
    mask = load_mask(episode_dir / "rights-mask.yaml")
    rows = check_candidates(mask, episode_dir, candidates_glob)
    _candidate_table(rows)


def check_candidates(mask: dict, episode_dir: Path, glob: str) -> list[dict]:
    rows: list[dict] = []
    for f in sorted(episode_dir.glob(glob)):
        doc = yaml.safe_load(f.read_text())
        for c in doc.get("candidates", []):
            si, so = float(c["source_in"]), float(c["source_out"])
            published = spans_are_published(mask, si, so)
            # Partial: overlaps some published span but not wholly inside one.
            overlaps = any(so > s and si < e for s, e in mask["published_spans"])
            verdict = "PUBLISHED" if published else ("PARTIAL" if overlaps else "CUT")
            rows.append({
                "id": c["id"], "slug": c.get("slug", ""),
                "source_in": si, "source_out": so, "verdict": verdict,
            })
    return rows


# --- Reporting ----------------------------------------------------------------

def _fatal(msg: str) -> int:
    console.print(f"[bold red]FATAL:[/] {msg}")
    return 1


def _report(al: Alignment, cut_total: float, pub_total: float,
            expected_cut: float, src_dur: float, pub_dur: float) -> None:
    t = RichTable(title="Rights-mask alignment", show_header=False)
    t.add_row("raw source duration", f"{src_dur:.2f}s")
    t.add_row("published duration", f"{pub_dur:.2f}s")
    t.add_row("expected cut (raw - pub)", f"{expected_cut:.1f}s")
    t.add_row("measured cut total", f"{cut_total:.1f}s")
    t.add_row("measured published total", f"{pub_total:.1f}s")
    t.add_row("alignment coverage", f"{al.coverage:.2%} ({al.matched_pub_words}/{al.total_pub_words})")
    t.add_row("published spans", str(len(al.published_spans)))
    t.add_row("cut spans", str(len(al.cut_spans)))
    t.add_row("internal cuts", str(al.n_internal_cuts))
    console.print(t)


def _candidate_table(rows: list[dict]) -> None:
    t = RichTable(title="Candidate rights check")
    t.add_column("id"); t.add_column("slug")
    t.add_column("in", justify="right"); t.add_column("out", justify="right")
    t.add_column("verdict")
    style = {"PUBLISHED": "green", "PARTIAL": "yellow", "CUT": "bold red"}
    for r in rows:
        t.add_row(r["id"], r["slug"], f"{r['source_in']:.1f}", f"{r['source_out']:.1f}",
                  f"[{style[r['verdict']]}]{r['verdict']}[/]")
    console.print(t)


if __name__ == "__main__":
    app()
