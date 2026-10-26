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

Enforces the timeline invariants 1-10, the dialogue-vs-audio check (11), inserts (12) and
overlays (13) from
references/schemas.md. Any failure prints a findings table and exits 1.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable

from broll import MediaInfo, build_index, load_insert_words
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
from psmedia import parse_crop

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
        if seg.is_insert:
            continue  # an insert's range is checked against its own file (invariant 12)
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


def check_4_output_duration_value(clip: Clip) -> list[Finding]:
    if not clip.timeline:
        return []
    last = clip.timeline[-1].output_out
    if not close(clip.output.duration_s, last):
        return [Finding("4", "output.duration_s", f"{last:.3f}s (timeline[-1].output_out)",
                        f"{clip.output.duration_s:.3f}s")]
    return []


def check_4_output_duration(clip: Clip, episode: Episode) -> list[Finding]:
    if not clip.timeline:
        return []
    out: list[Finding] = check_4_output_duration_value(clip)
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
        if seg.is_insert:
            continue  # not in the episode transcript; checked against its own words file (invariant 12)
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
        if seg.speaker not in ids and not seg.is_insert  # an insert's speaker is not an episode speaker
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
        if v.kind == "insert" and fmt == "clip":
            continue  # invariant 12
        if v.kind != "aroll":
            out.append(Finding("9", seg.id, "visual.kind aroll (B-roll goes in overlays:, inserts only in format clip)", v.kind))
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


def _asset_findings(inv: str, where: str, name: str, index: dict[str, MediaInfo]) -> list[Finding]:
    info = index.get(name)
    if info is None or not info.exists:
        return [Finding(inv, f"{where}/{name}", f"asset exists at broll/{name}", "missing on disk")]
    if info.provenance is None:
        return [Finding(inv, f"{where}/{name}", f"a provenance entry for {name} (source, licence, permission)",
                        "no entry in the provenance ledger")]
    return []


def _tail_start(clip: Clip) -> float | None:
    return None if clip.broll is None else clip.output.duration_s - clip.broll.protected_tail_s


def check_12_inserts(clip: Clip, index: dict[str, MediaInfo], insert_words: dict[str, list[dict]]) -> list[Finding]:
    """Insert segments: a credited non-episode source spliced into a horizontal clip's timeline."""
    out: list[Finding] = []
    tail = _tail_start(clip)
    broll_prefix = f"clips/{clip.clip.id}/broll"
    for seg in clip.timeline:
        if seg.is_insert != (seg.insert is not None):
            out.append(Finding("12", seg.id, "visual.kind insert <=> an insert block on the segment",
                               f"kind={seg.visual.kind}, insert block {'present' if seg.insert else 'absent'}"))
            continue
        if not seg.is_insert:
            continue
        if clip.clip.format != "clip":
            out.append(Finding("12", seg.id, "insert segments only in format clip", clip.clip.format))
        if clip.broll is None:
            out.append(Finding("12", seg.id, "a broll: block (provenance, protected_tail_s)", "absent"))
        if str(PurePosixPath(seg.source_file).parent) != broll_prefix:
            out.append(Finding("12", seg.id, f"source_file under {broll_prefix}/ (relative to the episode root)",
                               seg.source_file))
        if seg.visual.treatment != "letterbox":
            out.append(Finding("12", seg.id, "insert treatment letterbox", seg.visual.treatment))
        if not seg.insert.speaker_name.strip():
            out.append(Finding("12", seg.id, "insert.speaker_name names who is speaking", "empty"))
        name = PurePosixPath(seg.source_file).name
        found = _asset_findings("12", seg.id, name, index)
        out += found
        info = index.get(name)
        if info is not None and info.exists:
            if not info.has_audio:
                out.append(Finding("12", seg.id, f"{name} has an audio stream (an insert plays its own sound)", "no audio"))
            if info.duration is None:
                out.append(Finding("12", seg.id, f"{name} is a video", "a still image"))
            elif seg.source_in < -EPSILON or seg.source_out > info.duration + EPSILON:
                out.append(Finding("12", seg.id, f"source range inside {name} (0-{info.duration:.3f}s)",
                                   f"{seg.source_in:.3f}-{seg.source_out:.3f}"))
        if tail is not None and seg.output_out > tail + EPSILON:
            out.append(Finding("12", seg.id, f"insert ends before the protected tail ({fmt_mmss(tail)})",
                               f"ends {fmt_mmss(seg.output_out)}"))
        words = insert_words.get(seg.id)
        if words is None:
            out.append(Finding("12", seg.id, f"word timings at {seg.insert.words}", "not loaded"))
            continue
        audible = [w["w"] for w in words if w["end"] > w["start"]
                   and (min(w["end"], seg.source_out) - max(w["start"], seg.source_in))
                   >= AUDIBLE_WORD_OVERLAP * (w["end"] - w["start"])]
        expected, actual = tokenize(" ".join(audible)), tokenize(seg.dialogue)
        if expected != actual:
            out.append(Finding("12", seg.id, f"dialogue == the {len(expected)} words audible in its words file",
                               f"{len(actual)} dialogue token(s); first difference near "
                               f"{next((a for a, b in zip(actual, expected) if a != b), '<length>')!r}"))
    return out


def _shot_findings(ov, index: dict[str, MediaInfo], fps: float) -> list[Finding]:
    out: list[Finding] = []
    shots = ov.shots
    if shots and abs(shots[0].at) > EPSILON:
        out.append(Finding("13", ov.id, "first shot at 0.0", f"{shots[0].at:.3f}"))
    for k, shot in enumerate(shots):
        where = f"{ov.id}/shot{k + 1}"
        slot_end = shots[k + 1].at if k + 1 < len(shots) else ov.duration
        slot = slot_end - shot.at
        if slot <= EPSILON:
            out.append(Finding("13", where, "shots ordered by `at`, each with a non-empty slot inside the window",
                               f"at={shot.at:.3f}, slot {slot:.3f}s"))
            continue
        if (shot.asset is None) == (shot.grid is None):
            out.append(Finding("13", where, "exactly one of asset / grid", f"asset={shot.asset}, grid={'set' if shot.grid else None}"))
            continue
        if k == 0 and shot.dissolve_frames:
            out.append(Finding("13", where, "no dissolve into the first shot (use fade_in_frames)", f"{shot.dissolve_frames}"))
        if shot.dissolve_frames / fps > slot + EPSILON:
            out.append(Finding("13", where, f"dissolve shorter than the shot's {slot:.3f}s slot", f"{shot.dissolve_frames}f"))
        if shot.zoom is not None and (len(shot.zoom) != 2 or not all(1.0 <= z <= 2.0 for z in shot.zoom)):
            out.append(Finding("13", where, "zoom [from, to], each within 1.0-2.0", f"{shot.zoom}"))
        if shot.crop is not None:
            out += _crop_findings(where, shot.crop, index.get(shot.asset or ""))
        if shot.grid is not None:
            g = shot.grid
            if g.cols < 1 or g.rows < 1 or len(g.tiles) > g.cols * g.rows or not g.tiles:
                out.append(Finding("13", where, f"1..{g.cols * g.rows} tiles for a {g.cols}x{g.rows} grid", f"{len(g.tiles)}"))
            for t, tile in enumerate(g.tiles, start=1):
                out += _asset_findings("13", f"{where}/tile{t}", tile.asset, index)
                if not (-EPSILON <= tile.at < slot):
                    out.append(Finding("13", f"{where}/tile{t}", f"tile at within the shot's slot [0, {slot:.3f})", f"{tile.at:.3f}"))
                if index.get(tile.asset) and index[tile.asset].duration is not None:
                    out.append(Finding("13", f"{where}/tile{t}", "grid tiles are stills", f"{tile.asset} is a video"))
                if tile.crop is not None:
                    out += _crop_findings(f"{where}/tile{t}", tile.crop, index.get(tile.asset))
            continue
        found = _asset_findings("13", where, shot.asset, index)
        out += found
        info = index.get(shot.asset)
        if found or info is None:
            continue
        if info.duration is None:
            if shot.src_in is not None or shot.src_out is not None or shot.speed != 1.0 or shot.hold_last:
                out.append(Finding("13", where, "a still takes no src_in/src_out/speed/hold_last", shot.asset))
            continue
        if shot.src_in is None or shot.src_out is None:
            out.append(Finding("13", where, f"src_in/src_out for the video {shot.asset}", "missing"))
            continue
        if shot.speed <= 0:
            out.append(Finding("13", where, "speed > 0", f"{shot.speed}"))
            continue
        if shot.src_in < -EPSILON or shot.src_out > info.duration + EPSILON or shot.src_out <= shot.src_in:
            out.append(Finding("13", where, f"source range inside {shot.asset} (0-{info.duration:.3f}s)",
                               f"{shot.src_in:.3f}-{shot.src_out:.3f}"))
            continue
        plays = (shot.src_out - shot.src_in) / shot.speed
        if plays < slot - 1.0 / fps and not shot.hold_last:
            out.append(Finding("13", where, f"range fills its {slot:.3f}s slot, or hold_last: true to freeze the last frame",
                               f"plays {plays:.3f}s"))
    return out


def _crop_findings(where: str, spec: str, info: MediaInfo | None) -> list[Finding]:
    try:
        w, h, x, y = parse_crop(spec)
    except ValueError as err:
        return [Finding("13", where, "crop x=..:y=..:w=..:h=..", str(err))]
    if info is not None and info.width and (x < 0 or y < 0 or x + w > info.width or y + h > (info.height or 0)):
        return [Finding("13", where, f"crop inside the {info.width}x{info.height} asset", spec)]
    return []


def check_13_overlays(clip: Clip, index: dict[str, MediaInfo]) -> list[Finding]:
    """Overlays: real, credited B-roll composited over a horizontal clip (schemas.md § Overlays)."""
    if not clip.overlays:
        return []
    out: list[Finding] = []
    fps = clip.output.fps
    dur = clip.output.duration_s
    if clip.clip.format != "clip":
        out.append(Finding("13", "overlays", "overlays only on format clip (shorts have no B-roll)", clip.clip.format))
    if clip.broll is None:
        out.append(Finding("13", "broll", "a broll: block (provenance, protected_tail_s)", "absent"))
    tail = _tail_start(clip)
    seen: set[str] = set()
    for ov in clip.overlays:
        if ov.id in seen:
            out.append(Finding("13", ov.id, "unique overlay ids", "duplicate"))
        seen.add(ov.id)
        if ov.end <= ov.start or ov.start < -EPSILON or ov.end > dur + EPSILON:
            out.append(Finding("13", ov.id, f"window within [0, {dur:.3f}] with end > start", f"{ov.start:.3f}-{ov.end:.3f}"))
            continue
        if (ov.fade_in_frames + ov.fade_out_frames) / fps > ov.duration + EPSILON:
            out.append(Finding("13", ov.id, "fades fit inside the window", f"{ov.fade_in_frames}+{ov.fade_out_frames} frames"))
        if ov.layer == "picture":
            if not ov.shots or ov.lines:
                out.append(Finding("13", ov.id, f"{ov.mode}: at least one shot and no text lines",
                                   f"{len(ov.shots)} shot(s), {len(ov.lines)} line(s)"))
            if ov.mode == "pip" and ov.box is None:
                out.append(Finding("13", ov.id, "pip names its box {x, y, w, h}", "no box"))
            if ov.mode == "fullscreen" and ov.box is not None:
                out.append(Finding("13", ov.id, "fullscreen takes no box (it is the whole frame)", f"{ov.box}"))
            if (ov.from_box is None) != (ov.move_frames == 0):
                out.append(Finding("13", ov.id, "from_box and move_frames > 0 together", f"from_box={ov.from_box}, move_frames={ov.move_frames}"))
            for b in (ov.box, ov.from_box):
                if b is not None and (b.w <= 0 or b.h <= 0 or b.x < 0 or b.y < 0 or b.x + b.w > _w(clip) or b.y + b.h > _h(clip)):
                    out.append(Finding("13", ov.id, f"box inside the {clip.output.resolution} frame", f"{b}"))
                if b is not None and (b.w % 2 or b.h % 2):
                    out.append(Finding("13", ov.id, "even box width and height (4:2:0 video has no odd sizes)", f"{b}"))
            out += _shot_findings(ov, index, fps)
            for seg in clip.inserts:
                if ov.start < seg.output_out - EPSILON and ov.end > seg.output_in + EPSILON:
                    out.append(Finding("13", ov.id, f"no picture overlay over the insert {seg.id}",
                                       f"overlaps {fmt_mmss(seg.output_in)}-{fmt_mmss(seg.output_out)}"))
            if ov.mode == "fullscreen" and tail is not None and ov.end > tail + EPSILON:
                out.append(Finding("13", ov.id, f"fullscreen cutaways end before the protected tail ({fmt_mmss(tail)})",
                                   f"ends {fmt_mmss(ov.end)}"))
        else:
            if not ov.lines or ov.shots or ov.box is not None:
                out.append(Finding("13", ov.id, f"{ov.mode}: text lines only (no shots, no box)",
                                   f"{len(ov.lines)} line(s), {len(ov.shots)} shot(s)"))
            for line in ov.lines:
                for run in line.runs:
                    for name in ("at", "underline_at", "strike_at"):
                        t = getattr(run, name)
                        if t is not None and not (-EPSILON <= t < ov.duration):
                            out.append(Finding("13", ov.id, f"run {name} inside the window [0, {ov.duration:.3f})",
                                               f"{run.text!r}: {t:.3f}"))
            if ov.reveal == "words" and not (0 < ov.reveal_s < ov.duration):
                out.append(Finding("13", ov.id, "reveal_s inside the window for reveal: words", f"{ov.reveal_s}"))
    for layer in ("picture", "text"):
        windows = sorted((o for o in clip.overlays if o.layer == layer), key=lambda o: o.start)
        out += [
            Finding("13", f"{a.id}/{b.id}", f"no overlap within the {layer} layer",
                    f"{a.id} ends {a.end:.3f}s, {b.id} starts {b.start:.3f}s")
            for a, b in zip(windows, windows[1:])
            if b.start < a.end - EPSILON
        ]
    return out


def _w(clip: Clip) -> int:
    return int(clip.output.resolution.lower().split("x")[0])


def _h(clip: Clip) -> int:
    return int(clip.output.resolution.lower().split("x")[1])


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
    """Validate CLIP_DIR against schemas.md invariants 1-13."""
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

    index = build_index(clip, clip_dir)
    insert_words = load_insert_words(clip, clip_dir)

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
        *check_12_inserts(clip, index, insert_words),
        *check_13_overlays(clip, index),
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
        f"{len(clip.inserts)} insert(s), {len(clip.overlays)} overlay(s), "
        f"duration {fmt_mmss(clip.output.duration_s)} — invariants 1-13 satisfied"
        + (f" ({len(skips)} skipped)" if skips else "")
    )


if __name__ == "__main__":
    app()
