"""B-roll for horizontal clips: the media index, provenance ledger, and insert remapping.

Not executable — imported by validate_clip.py, render_horizontal.py, assemble_audio.py,
qc_render.py and insert_segment.py. Canonical spec: ../references/schemas.md § Overlays and
§ Insert segments.

Two kinds of B-roll exist, and only these two:

* **overlays** (`clip.yaml overlays:`) composite real footage, stills or typography OVER the cut;
  the hosts' audio keeps playing. They never change the timeline.
* **insert segments** are timeline segments cut from a non-episode source (picture AND sound),
  spliced in by `insert_segment()`, which splits the segment it lands in and shifts everything
  after it — timeline, overlays and subtitle lines — by the insert's duration.

Every file either kind uses lives in `CLIP_DIR/broll/` and must have an entry in the provenance
ledger (`broll.provenance`, default `broll/provenance.json`). Nothing AI-generated, ever.
"""

from __future__ import annotations

import sys as _sys
from pathlib import Path as _P
_sys.path.insert(0, str(_P(__file__).resolve().parent))
from mediatools import ffmpeg_tool

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from pslib import (
    EPSILON,
    Clip,
    TimelineSegment,
    Word,
    ffprobe_media,
    tokenize,
)

STILL_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
#: keys every provenance-ledger entry must carry (non-empty)
PROVENANCE_REQUIRED = ("file", "source_url", "licence", "permission")
#: A word counts as audible in a segment when at least this much of it survives the cut
#: (the same rule validate_clip invariant 11 and the subtitle remap use).
AUDIBLE_WORD_OVERLAP = 0.5


@dataclass(frozen=True)
class MediaInfo:
    """What the validator needs to know about one broll/ file."""

    exists: bool
    #: seconds for video; None for a still image
    duration: float | None
    has_audio: bool
    #: the file's provenance-ledger entry, None when it has none
    provenance: dict[str, Any] | None
    width: int | None = None
    height: int | None = None


# ---------------------------------------------------------------------------
# Provenance + media index
# ---------------------------------------------------------------------------


def load_provenance(path: Path) -> dict[str, dict[str, Any]]:
    """`[{"file": "talk_hero.png", "source_url": …, "licence": …, "attribution": …, "permission": …}, …]`
    → entries by file name.

    A missing ledger is an error naming the path; a malformed one names the bad entry.
    """
    if not path.is_file():
        raise FileNotFoundError(
            f"missing B-roll provenance ledger: {path} — every overlay/insert asset needs an entry "
            f"(source URL, licence, permission status) before it can be validated or rendered"
        )
    entries = json.loads(path.read_text())
    if not isinstance(entries, list):
        raise ValueError(f"{path}: expected a JSON list of asset entries, got {type(entries).__name__}")
    out: dict[str, dict[str, Any]] = {}
    for i, entry in enumerate(entries):
        name = entry.get("file") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError(f"{path}: assets[{i}] has no `file` name")
        missing = [k for k in PROVENANCE_REQUIRED if not entry.get(k)]
        if missing:
            raise ValueError(f"{path}: entry for {name} lacks {missing} — every asset records where it came from and on what terms")
        out[PurePosixPath(name).name] = entry
    return out


def broll_dir(clip_dir: Path) -> Path:
    return clip_dir / "broll"


def insert_asset_name(seg: TimelineSegment) -> str:
    return PurePosixPath(seg.source_file).name


def referenced_assets(clip: Clip) -> list[str]:
    names = [name for ov in clip.overlays for name in ov.assets()]
    names += [insert_asset_name(seg) for seg in clip.inserts]
    return sorted(set(names))


def still_dims(path: Path) -> tuple[int, int]:
    proc = subprocess.run(
        [ffmpeg_tool("ffprobe"), "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
         "-of", "csv=p=0", str(path)], capture_output=True, text=True,
    )
    if proc.returncode != 0 or "," not in proc.stdout:
        raise RuntimeError(f"ffprobe could not read the still {path}: {proc.stderr.strip() or proc.stdout!r}")
    w, h = proc.stdout.strip().split(",")[:2]
    return int(w), int(h)


def probe_media(path: Path, provenance: dict[str, Any] | None) -> MediaInfo:
    if not path.is_file():
        return MediaInfo(exists=False, duration=None, has_audio=False, provenance=provenance)
    if path.suffix.lower() in STILL_EXTS:
        w, h = still_dims(path)
        return MediaInfo(exists=True, duration=None, has_audio=False, provenance=provenance, width=w, height=h)
    probe = ffprobe_media(path)
    return MediaInfo(
        exists=True, duration=probe.duration_s, has_audio=probe.audio_codec is not None,
        provenance=provenance, width=probe.width, height=probe.height,
    )


def build_index(clip: Clip, clip_dir: Path) -> dict[str, MediaInfo]:
    """Probe every broll/ file the clip references. Empty when the clip has no B-roll."""
    names = referenced_assets(clip)
    if not names:
        return {}
    if clip.broll is None:
        raise ValueError("clip.yaml uses overlays/inserts but has no `broll:` block (provenance, protected_tail_s)")
    ledger = load_provenance(clip_dir / clip.broll.provenance)
    return {name: probe_media(broll_dir(clip_dir) / name, ledger.get(PurePosixPath(name).name)) for name in names}


def load_insert_words(clip: Clip, clip_dir: Path) -> dict[str, list[dict]]:
    """Each insert's own word timings (insert-file time), keyed by segment id."""
    out: dict[str, list[dict]] = {}
    for seg in clip.inserts:
        if seg.insert is None:
            raise ValueError(f"{seg.id}: visual.kind insert without an `insert:` block")
        path = clip_dir / seg.insert.words
        if not path.is_file():
            raise FileNotFoundError(f"{seg.id}: insert word timings missing at {path} — transcribe the insert first")
        payload = json.loads(path.read_text())
        words = payload["words"] if isinstance(payload, dict) else payload
        out[seg.id] = [{"w": w["w"], "start": float(w["start"]), "end": float(w["end"])} for w in words]
    return out


# ---------------------------------------------------------------------------
# Timeline remapping
# ---------------------------------------------------------------------------


def shift_for_insert(t: float, at: float, dur: float) -> float:
    """An output time before an insert placed at `at` is unchanged; at/after it moves by `dur`."""
    return round(t + dur, 6) if t >= at - EPSILON else t


def _audible(words: list[Word], speaker: str, lo: float, hi: float) -> list[Word]:
    return [
        w for w in words
        if w.speaker == speaker and w.end > w.start
        and (min(w.end, hi) - max(w.start, lo)) >= AUDIBLE_WORD_OVERLAP * (w.end - w.start)
    ]


def split_text_after(text: str, n_tokens: int, where: str) -> tuple[str, str]:
    """Split `text` at a whitespace boundary after exactly `n_tokens` tokens."""
    chunks = text.split()
    count = 0
    for i, chunk in enumerate(chunks):
        if count == n_tokens:
            return " ".join(chunks[:i]), " ".join(chunks[i:])
        count += len(tokenize(chunk))
        if count > n_tokens:
            raise ValueError(f"{where}: token {n_tokens} falls inside the chunk {chunk!r} of the dialogue")
    if count == n_tokens:
        return " ".join(chunks), ""
    raise ValueError(f"{where}: dialogue has {count} tokens, cannot split after {n_tokens}")


def _next_segment_id(clip: Clip) -> str:
    nums = [int(s.id[1:]) for s in clip.timeline if s.id[:1] == "S" and s.id[1:].isdigit()]
    return f"S{max(nums, default=0) + 1:02d}"


def insert_segment(
    clip: Clip, at: float, insert: TimelineSegment, words: list[Word], transition_in: str
) -> Clip:
    """Splice `insert` into the output timeline at output time `at`.

    The segment containing `at` is split (its first part keeps its id, the tail gets the next
    free `S<NN>`, per the never-renumber rule) on a word gap — a split inside a spoken word is
    refused. Every later segment, overlay and subtitle line moves by the insert's duration; an
    overlay or subtitle line that straddles `at` is refused (move it first, then insert).
    `transition_in` is the transition INTO the insert; `insert.transition` is the one out of it.
    """
    if not insert.is_insert or insert.insert is None:
        raise ValueError(f"{insert.id}: insert_segment needs visual.kind insert with an `insert:` block")
    return splice_segments(clip, at, [insert], words, transition_in)


def splice_segments(
    clip: Clip, at: float, segments: list[TimelineSegment], words: list[Word], transition_in: str
) -> Clip:
    """Splice contiguous `segments` (episode segments and/or inserts, in play order) into the output
    timeline at output time `at` — `at = 0` prepends a lead-in. Same rules as `insert_segment`:
    the containing segment is split on a word gap, everything after `at` (segments, overlays,
    subtitle lines, the insert) moves by the spliced duration, and straddlers are refused."""
    if not segments:
        raise ValueError("splice_segments needs at least one segment")
    taken = {s.id for s in clip.timeline}
    for new in segments:
        if new.id in taken:
            raise ValueError(f"segment id {new.id} already exists in the timeline")
        taken.add(new.id)
        if new.source_duration <= 0:
            raise ValueError(f"{new.id}: source range {new.source_in}-{new.source_out} is empty")
    dur = round(sum(s.source_duration for s in segments), 6)
    end = clip.timeline[-1].output_out
    if not (-EPSILON <= at <= end + EPSILON):
        raise ValueError(f"insert point {at:.3f}s is outside the clip [0, {end:.3f}]")

    for ov in clip.overlays:
        if ov.start < at - EPSILON and ov.end > at + EPSILON:
            raise ValueError(f"overlay {ov.id} ({ov.start:.3f}-{ov.end:.3f}s) straddles the insert point {at:.3f}s")
    for i, line in enumerate(clip.subtitles.lines, start=1):
        a, b = line.output_range
        if a < at - EPSILON and b > at + EPSILON:
            raise ValueError(f"subtitle line {i} ({a:.3f}-{b:.3f}s) straddles the insert point {at:.3f}s")

    placed, t = [], at
    for new in segments:
        placed.append(new.model_copy(update={"output_in": round(t, 6), "output_out": round(t + new.source_duration, 6)}))
        t += new.source_duration
    timeline: list[TimelineSegment] = []
    for seg in clip.timeline:
        if seg.output_out <= at + EPSILON:
            timeline.append(seg)
            if abs(seg.output_out - at) <= EPSILON:
                timeline[-1] = seg.model_copy(update={"transition": transition_in})
                timeline += placed
            continue
        if seg.output_in >= at - EPSILON:
            if not any(s.id == placed[0].id for s in timeline):
                timeline += placed
            timeline.append(seg.model_copy(update={"output_in": round(seg.output_in + dur, 6), "output_out": round(seg.output_out + dur, 6)}))
            continue
        # `at` falls strictly inside this segment: split on a word gap.
        split_src = round(seg.source_in + (at - seg.output_in), 6)
        inside = [w for w in words if w.start < split_src - EPSILON and w.end > split_src + EPSILON
                  and w.end > seg.source_in and w.start < seg.source_out]
        if inside:
            w = inside[0]
            raise ValueError(
                f"insert point {at:.3f}s (source {split_src:.3f}s in {seg.id}) is inside the word "
                f"{w.w.strip('.,!?;:')!r} ({w.start:.3f}-{w.end:.3f}s) — pick a word gap"
            )
        n_head = len(tokenize(" ".join(w.w for w in _audible(words, seg.speaker, seg.source_in, split_src))))
        head_text, tail_text = split_text_after(seg.dialogue, n_head, seg.id)
        head = seg.model_copy(update={"source_out": split_src, "output_out": at, "dialogue": head_text,
                                      "transition": transition_in})
        tail = seg.model_copy(update={
            "id": _next_segment_id(clip), "source_in": split_src, "output_in": round(at + dur, 6),
            "output_out": round(seg.output_out + dur, 6), "dialogue": tail_text,
        })
        timeline += [head, *placed, tail]

    overlays = [
        ov.model_copy(update={"start": shift_for_insert(ov.start, at, dur), "end": shift_for_insert(ov.end, at, dur)})
        if ov.start >= at - EPSILON else ov
        for ov in clip.overlays
    ]
    lines = [
        line.model_copy(update={"output_range": [shift_for_insert(t, at, dur) for t in line.output_range]})
        if line.output_range[0] >= at - EPSILON else line
        for line in clip.subtitles.lines
    ]
    return clip.model_copy(update={
        "timeline": timeline,
        "overlays": overlays,
        "subtitles": clip.subtitles.model_copy(update={"lines": lines}),
        "output": clip.output.model_copy(update={"duration_s": round(clip.output.duration_s + dur, 6)}),
    })


def remove_segments(clip: Clip, ids: list[str]) -> Clip:
    """Drop contiguous timeline segments `ids` (e.g. a lead-in the user cut) and close the gap:
    every later segment, overlay and subtitle line moves back by the removed duration. An overlay
    or subtitle line that touches the removed span is refused — move or delete it first."""
    order = [s.id for s in clip.timeline]
    missing = [i for i in ids if i not in order]
    if missing or not ids:
        raise ValueError(f"remove_segments: segment id(s) {missing or ids} not in the timeline {order}")
    idx = sorted(order.index(i) for i in ids)
    if idx != list(range(idx[0], idx[0] + len(idx))):
        raise ValueError(f"remove_segments: {ids} are not contiguous in the timeline {order}")
    lo, hi = clip.timeline[idx[0]].output_in, clip.timeline[idx[-1]].output_out
    dur = round(hi - lo, 6)
    for ov in clip.overlays:
        if ov.start < hi - EPSILON and ov.end > lo + EPSILON:
            raise ValueError(f"overlay {ov.id} ({ov.start:.3f}-{ov.end:.3f}s) lies over the removed span {lo:.3f}-{hi:.3f}s")
    for i, line in enumerate(clip.subtitles.lines, start=1):
        a, b = line.output_range
        if a < hi - EPSILON and b > lo + EPSILON:
            raise ValueError(f"subtitle line {i} ({a:.3f}-{b:.3f}s) lies over the removed span {lo:.3f}-{hi:.3f}s")
    back = lambda t: round(t - dur, 6) if t >= hi - EPSILON else t  # noqa: E731
    timeline = [
        s.model_copy(update={"output_in": back(s.output_in), "output_out": back(s.output_out)})
        for k, s in enumerate(clip.timeline) if k not in idx
    ]
    if idx[0] > 0 and idx[-1] + 1 < len(clip.timeline):
        # the segment before the gap now hands over to the one after it: keep the outgoing transition of the removed run
        prev = idx[0] - 1
        timeline[prev] = timeline[prev].model_copy(update={"transition": clip.timeline[idx[-1]].transition})
    return clip.model_copy(update={
        "timeline": timeline,
        "overlays": [o.model_copy(update={"start": back(o.start), "end": back(o.end)}) for o in clip.overlays],
        "subtitles": clip.subtitles.model_copy(update={"lines": [
            l.model_copy(update={"output_range": [back(t) for t in l.output_range]}) for l in clip.subtitles.lines]}),
        "output": clip.output.model_copy(update={"duration_s": round(clip.output.duration_s - dur, 6)}),
    })


def remapped_words(clip: Clip, transcript_words: list[Word], insert_words: dict[str, list[dict]]) -> list[dict]:
    """Every audible word on the OUTPUT timeline: episode words per episode segment, an insert's
    own words (from its words file) per insert segment. Never episode words under an insert."""
    out: list[dict] = []
    for seg in clip.timeline:
        shift = seg.output_in - seg.source_in
        if seg.is_insert:
            if seg.id not in insert_words:
                raise ValueError(f"{seg.id}: no word timings loaded for this insert")
            pool = insert_words[seg.id]
            out += [
                {"w": w["w"], "start": max(w["start"], seg.source_in) + shift, "end": min(w["end"], seg.source_out) + shift}
                for w in pool
                if w["end"] > w["start"]
                and (min(w["end"], seg.source_out) - max(w["start"], seg.source_in)) >= AUDIBLE_WORD_OVERLAP * (w["end"] - w["start"])
            ]
            continue
        for wd in transcript_words:
            overlap = min(wd.end, seg.source_out) - max(wd.start, seg.source_in)
            if wd.end > wd.start and overlap >= AUDIBLE_WORD_OVERLAP * (wd.end - wd.start):
                out.append({"w": wd.w, "start": max(wd.start, seg.source_in) + shift,
                            "end": min(wd.end, seg.source_out) + shift})
    return out


def hosts_hidden_intervals(clip: Clip) -> list[tuple[float, float]]:
    """Output intervals where the hosts are NOT on screen: fullscreen overlays and inserts, merged."""
    spans = sorted(
        [(ov.start, ov.end) for ov in clip.overlays if ov.mode == "fullscreen"]
        + [(s.output_in, s.output_out) for s in clip.inserts]
    )
    merged: list[tuple[float, float]] = []
    for a, b in spans:
        if merged and a <= merged[-1][1] + EPSILON:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    return merged


def hosts_visible_fraction(clip: Clip) -> float:
    hidden = sum(b - a for a, b in hosts_hidden_intervals(clip))
    return 1.0 - hidden / clip.output.duration_s
