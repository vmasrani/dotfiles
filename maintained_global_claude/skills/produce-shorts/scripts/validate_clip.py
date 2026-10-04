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
"""Validate a clip manifest against its episode.

Enforces the timeline invariants 1-10 (plus the dialogue-vs-audio check, numbered 11) from
references/schemas.md. Any failure prints a findings table and exits 1.
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
    close,
    fmt_mmss,
    is_subsequence,
    load_clip,
    load_episode,
    load_transcript,
    sha256_file,
    tokenize,
)

console = Console()
app = typer.Typer(add_completion=False)


@dataclass
class Finding:
    invariant: str
    where: str
    expected: str
    actual: str


@dataclass
class Skip:
    invariant: str
    where: str
    reason: str


# ---------------------------------------------------------------------------
# Invariants 1-8, 10
# ---------------------------------------------------------------------------


def check_1_contiguous(clip: Clip) -> list[Finding]:
    tl = clip.timeline
    if not tl:
        return [Finding("1", "timeline", "at least one segment", "empty timeline")]
    out: list[Finding] = []
    if not close(tl[0].output_in, 0.0):
        out.append(Finding("1", tl[0].id, "output_in 0.0", f"{tl[0].output_in:.3f}"))
    out += [
        Finding("1", seg.id, f"output_in {prev.output_out:.3f} (== previous output_out)",
                f"{seg.output_in:.3f} ({'gap' if seg.output_in > prev.output_out else 'overlap'} "
                f"of {abs(seg.output_in - prev.output_out):.3f}s)")
        for prev, seg in zip(tl, tl[1:])
        if not close(seg.output_in, prev.output_out)
    ]
    out += [
        Finding("1", seg.id, f"output_in >= previous ({prev.output_in:.3f}) — timeline ordered by output_in",
                f"{seg.output_in:.3f}")
        for prev, seg in zip(tl, tl[1:])
        if seg.output_in < prev.output_in - EPSILON
    ]
    out += [
        Finding("1", seg.id, "output_out > output_in", f"{seg.output_in:.3f} -> {seg.output_out:.3f}")
        for seg in tl
        if seg.output_out <= seg.output_in
    ]
    return out


def check_2_durations(clip: Clip) -> list[Finding]:
    return [
        Finding("2", seg.id, f"output duration {seg.source_duration:.3f}s (== source duration)",
                f"{seg.output_duration:.3f}s (delta {seg.output_duration - seg.source_duration:+.3f}s)")
        for seg in clip.timeline
        if not close(seg.output_duration, seg.source_duration)
    ]


def check_3_source_within_probe(clip: Clip, episode: Episode) -> list[Finding]:
    probes = episode.media.probes
    out: list[Finding] = []
    for seg in clip.timeline:
        probe = probes.get(seg.source_file)
        if probe is None:
            out.append(Finding("3", seg.id, f"probe for {seg.source_file} in episode.yaml media.probes",
                               f"no probe entry (known: {sorted(probes) or 'none'})"))
            continue
        if seg.source_in < -EPSILON:
            out.append(Finding("3", seg.id, "source_in >= 0", f"{seg.source_in:.3f}"))
        if seg.source_out > probe.duration_s + EPSILON:
            out.append(Finding("3", seg.id, f"source_out <= probed duration {probe.duration_s:.3f}s",
                               f"{seg.source_out:.3f}s"))
        if seg.source_out <= seg.source_in:
            out.append(Finding("3", seg.id, "source_out > source_in",
                               f"{seg.source_in:.3f} -> {seg.source_out:.3f}"))
    return out


def check_4_output_duration(clip: Clip, episode: Episode) -> list[Finding]:
    if not clip.timeline:
        return []
    last = clip.timeline[-1].output_out
    out: list[Finding] = []
    if not close(clip.output.duration_s, last):
        out.append(Finding("4", "output.duration_s", f"{last:.3f}s (timeline[-1].output_out)",
                           f"{clip.output.duration_s:.3f}s"))
    profiles = [p for p in episode.platform_profiles if p.format == clip.clip.format]
    if not profiles:
        out.append(Finding("4", "episode.yaml platform_profiles",
                           f"at least one profile with format: {clip.clip.format}", "none"))
    out += [
        Finding("4", f"profile {p.name}", f"duration <= max_duration_s {p.max_duration_s:.3f}s",
                f"{clip.output.duration_s:.3f}s")
        for p in profiles
        if p.max_duration_s is not None and clip.output.duration_s > p.max_duration_s + EPSILON
    ]
    return out


def check_5_broll_assets(clip: Clip) -> list[Finding]:
    by_id = {a.id: a for a in clip.assets}
    out: list[Finding] = []
    for seg in clip.timeline:
        if seg.visual.kind != "broll":
            if seg.visual.asset_id is not None:
                out.append(Finding("5", seg.id, "asset_id null on an aroll segment",
                                   f"asset_id={seg.visual.asset_id}"))
            continue
        if seg.visual.asset_id is None:
            out.append(Finding("5", seg.id, "broll segment names an asset_id", "asset_id is null"))
            continue
        asset = by_id.get(seg.visual.asset_id)
        if asset is None:
            out.append(Finding("5", seg.id, f"asset {seg.visual.asset_id} present in assets[]",
                               f"not found (known: {sorted(by_id) or 'none'})"))
            continue
        if asset.duration_s < seg.output_duration - EPSILON:
            out.append(Finding("5", f"{seg.id}/{asset.id}",
                               f"asset duration >= segment duration {seg.output_duration:.3f}s",
                               f"{asset.duration_s:.3f}s"))
    return out


def check_6_asset_usage(clip: Clip) -> list[Finding]:
    used: dict[str, list[str]] = {}
    for seg in clip.timeline:
        if seg.visual.kind == "broll" and seg.visual.asset_id:
            used.setdefault(seg.visual.asset_id, []).append(seg.id)
    out: list[Finding] = []
    for asset in clip.assets:
        actual = sorted(used.get(asset.id, []))
        declared = sorted(asset.used_in_segments)
        if declared != actual:
            out.append(Finding("6", asset.id, f"used_in_segments {actual or '[] (unused asset)'}",
                               f"{declared}"))
    known = {a.id for a in clip.assets}
    out += [
        Finding("6", asset_id, "asset declared in assets[]",
                f"used by {sorted(segs)} but absent from assets[]")
        for asset_id, segs in used.items()
        if asset_id not in known
    ]
    return out


def check_7_asset_files(clip: Clip, clip_dir: Path) -> list[Finding]:
    findings: list[Finding] = []
    for asset in clip.assets:
        path = clip_dir / asset.file
        if not path.is_file():
            findings.append(Finding("7", asset.id, f"file exists at {path}", "missing on disk"))
            continue
        if asset.sha256 is None:
            findings.append(Finding("7", asset.id, "sha256 recorded for a downloaded asset",
                                    f"null (actual sha256 is {sha256_file(path)})"))
            continue
        actual = sha256_file(path)
        if actual != asset.sha256:
            findings.append(Finding("7", asset.id, f"sha256 {asset.sha256}", actual))
    return findings


def check_8_subtitles(clip: Clip) -> list[Finding]:
    out: list[Finding] = []
    lines = clip.subtitles.lines
    for idx, line in enumerate(lines, start=1):
        if len(line.output_range) != 2:
            out.append(Finding("8", f"subtitle {idx}", "output_range [start, end]", f"{line.output_range}"))
            continue
        start, end = line.output_range
        if end <= start:
            out.append(Finding("8", f"subtitle {idx}", "end > start", f"{start:.3f} -> {end:.3f}"))
        if start < -EPSILON or end > clip.output.duration_s + EPSILON:
            out.append(Finding("8", f"subtitle {idx}", f"range within [0, {clip.output.duration_s:.3f}]",
                               f"[{start:.3f}, {end:.3f}]"))
        spanned = [
            seg for seg in clip.timeline
            if seg.output_in < end - EPSILON and seg.output_out > start + EPSILON
        ]
        if not spanned:
            out.append(Finding("8", f"subtitle {idx}", "range overlaps at least one timeline segment",
                               f"[{start:.3f}, {end:.3f}] spans nothing"))
            continue
        dialogue = tokenize(" ".join(seg.dialogue for seg in spanned))
        words = tokenize(line.text)
        if not is_subsequence(words, dialogue):
            out.append(Finding("8", f"subtitle {idx}",
                               f"text words appear in order in dialogue of {[s.id for s in spanned]}",
                               f"{line.text!r} is not a subsequence of that dialogue"))
        for emph in line.emphasis:
            if not is_subsequence(tokenize(emph.word), words):
                out.append(Finding("8", f"subtitle {idx}", f"emphasis word {emph.word!r} present in text",
                                   f"absent from {line.text!r}"))
    for i, (a, b) in enumerate(zip(lines, lines[1:]), start=1):
        if len(a.output_range) == 2 and len(b.output_range) == 2 and b.output_range[0] < a.output_range[1] - EPSILON:
            out.append(Finding("8", f"subtitles {i}/{i + 1}",
                               f"non-overlapping ranges (next start >= {a.output_range[1]:.3f})",
                               f"next starts at {b.output_range[0]:.3f} — overlap of "
                               f"{a.output_range[1] - b.output_range[0]:.3f}s"))
    return out


# A word counts as audible in a segment when at least this much of it survives the cut.
# A word clipped by a few milliseconds is still heard in full and must still be captioned;
# a word the cut lands in the middle of is a bad edit point, not a transcription question.
AUDIBLE_WORD_OVERLAP = 0.5


def check_11_dialogue_covers_audio(clip: Clip, transcript) -> list[Finding]:
    """`dialogue` must account for every transcript word actually audible in the segment.

    Invariant 8 checks that subtitles are a subsequence of `dialogue` — which says nothing
    about whether `dialogue` matches the AUDIO, because both were derived from the same
    (possibly truncated) word set. That circularity let a real defect ship: a source_in of
    5694.26 against a word starting at 5694.258 dropped "to" from `dialogue` while leaving
    76ms of it audible at full speech level. Forced alignment matched the shorter text,
    every downstream check agreed, and the first syllable of the delivered short was
    uncaptioned. This closes the loop against the transcript itself.
    """
    out: list[Finding] = []
    for seg in clip.timeline:
        audible = [
            w for w in transcript.words
            if w.speaker == seg.speaker
            and w.end > w.start
            and (min(w.end, seg.source_out) - max(w.start, seg.source_in))
            >= AUDIBLE_WORD_OVERLAP * (w.end - w.start)
        ]
        expected, actual = tokenize(" ".join(w.w for w in audible)), tokenize(seg.dialogue)
        if expected == actual:
            continue
        missing = [w for w in audible if tokenize(w.w) and tokenize(w.w)[0] not in actual]
        detail = (
            f"first missing word {missing[0].w!r} at {missing[0].start:.3f}s"
            if missing else f"{len(actual)} word(s) in dialogue vs {len(expected)} audible"
        )
        out.append(Finding("11", seg.id,
                           f"dialogue covers all {len(expected)} word(s) audible in "
                           f"[{seg.source_in:.3f}, {seg.source_out:.3f}]", detail))
    return out


FORMAT_ASPECT = {"short": "9:16", "clip": "16:9"}


def check_10_speakers(clip: Clip, episode: Episode) -> list[Finding]:
    ids = episode.speaker_ids()
    out = [
        Finding("10", seg.id, f"speaker in {sorted(ids)}", seg.speaker)
        for seg in clip.timeline
        if seg.speaker not in ids
    ]
    for seg in clip.timeline:
        treatment = seg.visual.treatment
        if treatment.startswith("closeup-") and treatment[len("closeup-"):] not in ids:
            out.append(Finding("10", seg.id, f"treatment speaker in {sorted(ids)}",
                               f"{treatment} -> {treatment[len('closeup-'):]!r}"))
        out += [
            Finding("10", seg.id, f"visual.speakers entries in {sorted(ids)}", f"{spk!r}")
            for spk in (seg.visual.speakers or [])
            if spk not in ids
        ]
    return out


def check_9_format_treatments(clip: Clip) -> list[Finding]:
    fmt = clip.clip.format
    out: list[Finding] = []
    want_aspect = FORMAT_ASPECT[fmt]
    if clip.output.aspect != want_aspect:
        out.append(Finding("9", "output.aspect", f"{want_aspect} (format: {fmt})", clip.output.aspect))
    for seg in clip.timeline:
        v = seg.visual
        if v.kind != "aroll":
            out.append(Finding("9", seg.id, "visual.kind aroll (no B-roll in this pipeline)", v.kind))
            continue
        if fmt == "clip":
            if v.treatment != "source-frame":
                out.append(Finding("9", seg.id, "format clip uses only treatment source-frame", v.treatment))
            if v.speakers:
                out.append(Finding("9", seg.id, "visual.speakers null on a source-frame segment", f"{v.speakers}"))
            continue
        if v.treatment == "splitscreen":
            spk = v.speakers or []
            if len(spk) != 2 or len(set(spk)) != 2:
                out.append(Finding("9", seg.id,
                                   "splitscreen names exactly two distinct speakers [top, bottom]",
                                   f"visual.speakers={v.speakers}"))
        elif v.treatment.startswith("closeup-") and len(v.treatment) > len("closeup-"):
            if v.speakers:
                out.append(Finding("9", seg.id, "visual.speakers null on a closeup segment", f"{v.speakers}"))
        else:
            out.append(Finding("9", seg.id, "format short uses only closeup-<speaker> or splitscreen",
                               v.treatment))
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def render_findings(findings: list[Finding]) -> None:
    table = RichTable(title="Validation failures", header_style="bold red", show_lines=False)
    table.add_column("Inv", style="bold red", no_wrap=True)
    table.add_column("Where", style="cyan", no_wrap=True)
    table.add_column("Expected", style="green")
    table.add_column("Actual", style="yellow")
    for f in findings:
        table.add_row(f.invariant, f.where, f.expected, f.actual)
    console.print(table)


def render_skips(skips: list[Skip]) -> None:
    for s in skips:
        console.print(f"[bold yellow]SKIPPED[/] invariant {s.invariant} for [cyan]{s.where}[/]: {s.reason}")


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    episode_root: Path = typer.Option(
        None, "--episode-root", help="Episode root holding episode.yaml (default: CLIP_DIR/../..)"
    ),
) -> None:
    """Validate CLIP_DIR against schemas.md invariants 1-11."""
    clip_dir = clip_dir.resolve()
    if not clip_dir.is_dir():
        raise typer.BadParameter(f"clip directory does not exist: {clip_dir}")
    root = (episode_root or clip_dir.parent.parent).resolve()

    clip_path, episode_path = clip_dir / "clip.yaml", root / "episode.yaml"
    for p in (clip_path, episode_path):
        if not p.is_file():
            raise typer.BadParameter(f"missing required file: {p}")

    logger.info(f"clip={clip_path} episode={episode_path}")
    clip, episode = load_clip(clip_path), load_episode(episode_path)

    sha_findings = check_7_asset_files(clip, clip_dir)
    skips: list[Skip] = []

    # Invariant 11 needs the transcript. If it is absent the check cannot run — say so
    # visibly rather than letting "skipped" and "passed" look identical.
    transcript_path = root / episode.transcript.json_file
    if transcript_path.is_file():
        dialogue_findings = check_11_dialogue_covers_audio(clip, load_transcript(transcript_path))
    else:
        dialogue_findings = []
        skips.append(Skip("11", clip.clip.id, f"transcript not found at {transcript_path}"))

    findings = [
        *check_1_contiguous(clip),
        *check_2_durations(clip),
        *check_3_source_within_probe(clip, episode),
        *check_4_output_duration(clip, episode),
        *check_5_broll_assets(clip),
        *check_6_asset_usage(clip),
        *sha_findings,
        *check_8_subtitles(clip),
        *check_9_format_treatments(clip),
        *check_10_speakers(clip, episode),
        *dialogue_findings,
    ]

    render_skips(skips)
    if findings:
        render_findings(findings)
        console.print(
            f"[bold red]FAIL[/] {clip.clip.id}: {len(findings)} finding(s) across invariants "
            f"{sorted({f.invariant for f in findings}, key=int)}"
        )
        raise typer.Exit(1)

    console.print(
        f"[bold green]PASS[/] {clip.clip.id}: {len(clip.timeline)} segments, "
        f"{len(clip.subtitles.lines)} subtitle lines, {len(clip.assets)} assets, "
        f"duration {fmt_mmss(clip.output.duration_s)} — invariants 1-11 satisfied"
        + (f" ({len(skips)} skipped)" if skips else "")
    )


if __name__ == "__main__":
    app()
