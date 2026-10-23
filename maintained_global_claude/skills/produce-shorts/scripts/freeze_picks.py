#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "google-api-python-client>=2.120",
#   "google-auth>=2.30",
#   "google-auth-httplib2>=0.2",
# ]
# ///
"""The freeze — read the approved pick doc back and write clips/<slug>/clip.yaml per approved pick.

Reads the live doc (Docs `documents.get`), aligns it to transcript.json words, takes each pick's
kept (coloured, not struck-through) words as the timeline (one segment per contiguous run, split
at speaker changes in time order; crosstalk rule in run_timeline), pads the edges by review.boundary_pad_s without crossing a neighbouring
word, then runs validate_clip.py on every clip. Refuses (nonzero) while any pick is `proposed`,
when the doc text no longer aligns to the transcript, when a highlight colour is not in
review.picks, or when a short's kept duration is >= 180 s. See references/pick-doc.md §6.
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

import gdoc
from gdoc import Ctx, Model, die, ends_on, fmt_dur, load_ctx
from validate_clip import AUDIBLE_WORD_OVERLAP

console = Console(stderr=True)
app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)
SCRIPTS = Path(__file__).resolve().parent
OUTPUT = {"short": ("9:16", "1080x1920"), "clip": ("16:9", "1920x1080")}
DOC_STATUS_RE = re.compile(r" · (PROPOSED|APPROVED|DROPPED) — ")


def slugify(title: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return slug[:60].strip("-") or "clip"


def doc_statuses(paras: list[gdoc.DocPara]) -> dict[str, str]:
    out: dict[str, str] = {}
    for p in paras:
        if p.kind == "status":
            m = DOC_STATUS_RE.search(p.text)
            if not m:
                die(f"status line {p.text[:60]!r} has no PROPOSED/APPROVED/DROPPED marker")
            out[gdoc.STATUS_RE.match(p.text).group(1)] = m.group(1).lower()  # type: ignore[union-attr]
    return out


@dataclass
class TimelineSeg:
    speaker: str
    words: list[int]  # transcript indices, transcript order — the segment's dialogue
    lo: float
    hi: float


def kept_runs(model: Model, pid: str) -> list[list[int]]:
    """Index-contiguous runs of the pick's kept words; a cut or unowned word ends a run."""
    runs: list[list[int]] = []
    for i, o in enumerate(model.owner):
        if o == pid and not model.cut[i]:
            if runs and runs[-1][-1] == i - 1:
                runs[-1].append(i)
            else:
                runs.append([i])
    return runs


def _mid(w: dict[str, Any]) -> float:
    return (w["start"] + w["end"]) / 2


def heard(w: dict[str, Any], lo: float, hi: float) -> bool:
    """validate_clip invariant 11's predicate: the word is audible in [lo, hi]."""
    return w["end"] > w["start"] and (min(w["end"], hi) - max(w["start"], lo)) >= AUDIBLE_WORD_OVERLAP * (w["end"] - w["start"])


def speaker_groups(words: list[dict[str, Any]], active: list[int]) -> list[list[int]]:
    """Split a run at speaker changes in TIME order (word midpoint), not transcript order.

    A multitrack transcript interleaves speakers by start time, so two speakers talking over
    each other alternate word by word; ordering by midpoint puts every word of a group before
    every word of the next, which is what guarantees a cut point exists between them."""
    groups: list[list[int]] = []
    for i in sorted(active, key=lambda i: (_mid(words[i]), i)):
        if groups and words[groups[-1][-1]]["speaker"] == words[i]["speaker"]:
            groups[-1].append(i)
        else:
            groups.append([i])
    return [sorted(g) for g in groups]


def group_bounds(ctx: Ctx, run: list[int], groups: list[list[int]], max_t: float | None) -> list[tuple[float, float]]:
    """(source_in, source_out) per group of one run: padded, never into a neighbouring word, and
    abutting where two groups meet. Groups that overlap in time (crosstalk) are cut halfway
    between the last midpoint of one and the first midpoint of the next, so each word keeps the
    majority of its duration in its own segment; the source stays continuous across the cut."""
    w, pad = ctx.words, float(ctx.cfg["boundary_pad_s"])
    first, last = run[0], run[-1]
    starts = [min(w[i]["start"] for i in g) for g in groups]
    ends = [max(w[i]["end"] for i in g) for g in groups]
    bounds = [[a - pad, b + pad] for a, b in zip(starts, ends)]
    a, b = starts[0], ends[-1]
    bounds[0][0] = max(a - pad, min(w[first - 1]["end"], a)) if first > 0 else max(a - pad, 0.0)
    bounds[-1][1] = min(b + pad, max(w[last + 1]["start"], b)) if last + 1 < len(w) else b + pad
    for k in range(len(groups) - 1):
        e, s = ends[k], starts[k + 1]
        if s < e:
            cut = (max(_mid(w[i]) for i in groups[k]) + min(_mid(w[i]) for i in groups[k + 1])) / 2
        elif s - e <= 2 * pad:
            cut = (e + s) / 2
        else:
            continue
        bounds[k][1] = bounds[k + 1][0] = cut
    if max_t is not None:
        bounds = [[lo, min(hi, max_t)] for lo, hi in bounds]
    return [(round(lo, 3), round(hi, 3)) for lo, hi in bounds]


def run_timeline(ctx: Ctx, run: list[int], max_t: float | None) -> tuple[list[TimelineSeg], list[int]]:
    """One kept run -> speaker segments, plus the run's words heard in no segment of their speaker.

    Crosstalk rule: while some word is not heard (invariant 11) in its own group's segment,
    drop the worst-placed one (lowest share inside, then longest) from the segmentation and
    re-split. Such a word is typically a backchannel force-aligned across seconds of the other
    speaker; it stays in the as-recorded audio but gets no segment and no caption. Dialogue is
    then exactly the run words of the segment's speaker heard in it, in transcript order."""
    w = ctx.words
    bad = [i for i in run if w[i]["end"] < w[i]["start"]]
    if bad:
        die(f"transcript word(s) end before they start: "
            f"{[(i, w[i]['w'], w[i]['start'], w[i]['end']) for i in bad]} — fix transcript.json")
    active = list(run)
    while True:
        groups = speaker_groups(w, active)
        bounds = group_bounds(ctx, run, groups, max_t)
        misplaced = [
            ((min(w[i]["end"], hi) - max(w[i]["start"], lo)) / (w[i]["end"] - w[i]["start"]),
             -(w[i]["end"] - w[i]["start"]), i)
            for g, (lo, hi) in zip(groups, bounds) for i in g
            if w[i]["end"] > w[i]["start"] and not heard(w[i], lo, hi)
        ]
        if not misplaced:
            break
        active.remove(min(misplaced)[2])
    segs = [
        TimelineSeg(w[g[0]]["speaker"],
                    [i for i in run if w[i]["speaker"] == w[g[0]]["speaker"]
                     and (heard(w[i], lo, hi) or (i in g and w[i]["end"] == w[i]["start"]))],
                    lo, hi)
        for g, (lo, hi) in zip(groups, bounds)
    ]
    placed = {i for s in segs for i in s.words}
    return segs, [i for i in run if i not in placed]


def build_clip(ctx: Ctx, model: Model, pid: str, slug: str, max_t: float | None) -> tuple[dict[str, Any], float]:
    meta = model.picks[pid]
    segs: list[TimelineSeg] = []
    unheard: list[int] = []
    for run in kept_runs(model, pid):
        run_segs, run_unheard = run_timeline(ctx, run, max_t)
        segs += run_segs
        unheard += run_unheard
    if unheard:
        logger.warning("{}: {} overlapped word(s) heard in no segment of their speaker — kept in the audio, "
                       "uncaptioned: {}", pid, len(unheard),
                       ", ".join(f"{ctx.words[i]['speaker']}:{ctx.words[i]['w']!r}@{ctx.words[i]['start']:.2f}"
                                 for i in unheard))
    source_file = ctx.data["media"]["episode_video"]
    timeline: list[dict[str, Any]] = []
    t = 0.0
    for k, s in enumerate(segs, start=1):
        lo, hi = s.lo, s.hi
        dur = round(hi - lo, 3)
        treatment = f"closeup-{s.speaker}" if meta.format == "short" else "source-frame"
        timeline.append({
            "id": f"S{k:02d}", "source_file": source_file, "source_in": lo, "source_out": hi,
            "output_in": round(t, 3), "output_out": round(t + dur, 3),
            "dialogue": " ".join(ctx.words[i]["w"] for i in s.words),
            "speaker": s.speaker, "audio": "as-recorded",
            "visual": {"kind": "aroll", "treatment": treatment, "speakers": None, "locked": False,
                       "reason": None, "asset_id": None, "motion": None},
            "transition": "cut",
        })
        t = round(t + dur, 3)
    aspect, resolution = OUTPUT[meta.format]
    sub = ctx.data.get("subtitles") or gdoc.load_yaml(gdoc.DEFAULTS_YAML)["subtitles"]
    clip = {
        "clip": {"id": slug, "pick": pid, "format": meta.format, "title": meta.title, "status": "frozen",
                 "why": meta.why, "ends_on": ends_on(ctx.words, model, pid)},
        "timeline": timeline,
        "subtitles": {"font": sub["font"], "base_color": sub["base_color"], "emphasis_palette": [sub["emphasis_color"]],
                      "position_default": "bottom-center", "lines": []},
        "assets": [],
        "review": {"storyboard_docs": [], "cover": None, "final_url": None},
        "output": {"aspect": aspect, "resolution": resolution, "fps": 30, "duration_s": t},
        "render": {"versions": []},
    }
    return clip, t


@app.command()
def freeze(episode_dir: Path = typer.Argument(..., help="Episode directory")) -> None:
    """Pick doc -> clips/<slug>/clip.yaml for every approved pick; validate; status.stage: frozen."""
    ctx = load_ctx(episode_dir)
    meta = ctx.pick_meta()
    if not meta:
        die("episode.yaml has no review.picks — nothing to freeze")
    proposed = sorted(p for p, m in meta.items() if m.status == "proposed")
    if proposed:
        die(f"picks still proposed: {proposed} — approve or drop every pick before the freeze")
    approved = sorted((p for p, m in meta.items() if m.status == "approved"), key=gdoc.pick_sort_key)
    if not approved:
        die("no approved picks — nothing to freeze")

    g = gdoc.Google(ctx.account)
    paras = gdoc.parse_doc(g.get_doc(ctx.doc_id()), ctx)
    al = gdoc.align_doc(paras, ctx)
    model = gdoc.read_model(ctx, al)
    mismatched = {p: (m.status, doc_statuses(paras).get(p)) for p, m in meta.items()
                  if doc_statuses(paras).get(p) != m.status}
    if mismatched:
        die(f"doc status lines disagree with episode.yaml (pick: (yaml, doc)): {mismatched}")
    gdoc.validate_model(ctx, model)

    probes = (ctx.data.get("media") or {}).get("probes") or {}
    max_t = (probes.get(ctx.data["media"]["episode_video"]) or {}).get("duration_s")
    slugs: dict[str, str] = {}
    for pid in approved:
        slug = slugify(meta[pid].title)
        slugs[pid] = slug if slug not in slugs.values() else f"{slug}-{pid.lower()}"

    clips_dir = ctx.dir / "clips"
    plan: list[tuple[str, Path, dict[str, Any], float]] = []
    for pid in approved:
        clip_dir = clips_dir / slugs[pid]
        existing = clip_dir / "clip.yaml"
        if existing.exists():
            old = gdoc.load_yaml(existing)["clip"]
            if old.get("pick") != pid or old.get("status") != "frozen":
                die(f"{existing} already exists (pick {old.get('pick')}, status {old.get('status')}); "
                    f"refusing to overwrite work from a later stage — rename the pick title or remove the clip")
        clip, dur = build_clip(ctx, model, pid, slugs[pid], max_t)
        if meta[pid].format == "short" and dur >= gdoc.SHORT_LIMIT_S:
            die(f"short {pid}: padded kept duration {dur:.2f}s is not under {gdoc.SHORT_LIMIT_S:.0f}s")
        plan.append((pid, clip_dir, clip, dur))

    for _pid, clip_dir, clip, _dur in plan:
        clip_dir.mkdir(parents=True, exist_ok=True)
        gdoc.save_yaml(clip_dir / "clip.yaml", clip)

    # sweep-then-assert: validate every clip, then fail once
    failures: list[str] = []
    table = Table(title="freeze")
    for col in ("pick", "clip", "dur", "segments", "validate_clip"):
        table.add_column(col)
    for pid, clip_dir, clip, dur in plan:
        proc = subprocess.run(["uv", "run", str(SCRIPTS / "validate_clip.py"), str(clip_dir)],
                              capture_output=True, text=True)
        ok = proc.returncode == 0
        table.add_row(pid, str(clip_dir.relative_to(ctx.dir)), fmt_dur(dur), str(len(clip["timeline"])),
                      "ok" if ok else f"FAILED rc={proc.returncode}")
        if not ok:
            failures.append(f"{pid} ({clip_dir}):\n{(proc.stdout + proc.stderr).strip()[-1500:]}")
    console.print(table)
    if failures:
        die("validate_clip.py failed — clip.yaml files were written but the episode is NOT marked frozen:\n"
            + "\n---\n".join(failures))
    ctx.data.setdefault("status", {})["stage"] = "frozen"
    ctx.save()
    logger.info("froze {} clip(s); status.stage = frozen", len(plan))
    for pid, clip_dir, _c, _d in plan:
        print(clip_dir / "clip.yaml")


if __name__ == "__main__":
    app()
