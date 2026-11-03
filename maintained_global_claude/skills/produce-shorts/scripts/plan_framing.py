#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Render prep — computed framing for a short (references/render-qc.md § Shorts).

Fills `visual.treatment` on every timeline segment of a `format: short` clip from the
words of `transcript.json` (who speaks when) and the thresholds in `config/defaults.yaml`
`framing:`. The rules, in precedence order:

1. Speaker change -> that speaker's solo (`closeup-<speaker>`).
2. Both parties live -> `splitscreen` of exactly those two speakers: a question and its
   answer within `exchange_gap_s`, an interruption / overlapping speech, or a back-and-forth
   of >= 3 turns each shorter than `exchange_turn_s`.
3. Never three: a split screen always names exactly two distinct speakers.
4. Dwell ceiling: no treatment held longer than `max_dwell_s`; a long solo is broken by a
   split screen with the listener, a long split by a solo of whoever speaks, always at a
   sentence boundary when one exists.
5. A split screen needs BOTH faces on screen: in a gallery-view recording the listener is
   often not in the frame (speaker view shows only whoever talks), so each computed split is
   checked with the same face detection the render uses (`framer.py`) and demoted to the
   talker's solo when a face is missing; the demotion and the missing range are in `reason`.
6. A segment with `visual.locked: true` (user override by comment) is never changed, never
   split, and never reasoned about.

Segments may be SPLIT (a dwell break, a split-screen window inside a long turn). Invariants
kept: the output timeline stays contiguous and the same length, source/output durations
match, the first part keeps its segment ID and later parts get NEW IDs appended after the
current maximum (never renumbered), and `dialogue` is sliced verbatim by transcript word.

`format: clip` keeps `source-frame` everywhere — the horizontal source is already framed.
"""

from __future__ import annotations

import copy
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

import facelib
from framer import Framer, resolve_source
from pslib import TimelineSegment, load_episode
from cliplib import (
    EPS,
    QUESTION_RE,
    TERMINAL_RE,
    Ctx,
    FramingConfig,
    OutWord,
    Word,
    dialogue_tokens,
    fmt_ts,
    load_ctx,
    load_words,
    place_words,
    treatment_label,
)

console = Console()
app = typer.Typer(add_completion=False)

PAUSE_S = 0.3             # a silence at least this long is a phrase boundary
INTERRUPT_GAP_S = 0.35    # next speaker starts this soon after an unfinished sentence = interruption
CUT_OFF_RE = re.compile(r"(—|-|…|\.\.\.)[\"')\]]*$")


@dataclass(frozen=True)
class Label:
    treatment: str
    speakers: tuple[str, str] | None = None


@dataclass
class Plan:
    """Per-word labelling of the whole timeline, plus everything needed to cut blocks."""

    ctx: Ctx
    cfg: FramingConfig
    words: list[OutWord]
    spk: list[str]                      # framing speaker per word (backchannels absorbed)
    locked: list[bool]
    label: list[Label | None]
    reason: list[str]
    duration: float
    fps: float
    transcript: list[Word]
    notes: list[str] = field(default_factory=list)

    # ---- geometry -------------------------------------------------------

    def cut_out(self, k: int) -> float:
        """Output time of the boundary BEFORE word k (0 and N are the clip ends)."""
        if k <= 0:
            return 0.0
        if k >= len(self.words):
            return self.duration
        a, b = self.words[k - 1], self.words[k]
        if a.seg != b.seg:
            return self.ctx.clip["timeline"][b.seg]["output_in"]
        seg = self.ctx.clip["timeline"][a.seg]
        mid = (a.end + b.start) / 2
        snapped = round(mid * self.fps) / self.fps
        return min(max(snapped, seg["output_in"] + 1 / self.fps), seg["output_out"] - 1 / self.fps)

    def span(self, i0: int, i1: int) -> float:
        return self.cut_out(i1 + 1) - self.cut_out(i0)

    def gap(self, i: int) -> float:
        """Silence between word i-1 and word i."""
        return self.words[i].start - self.words[i - 1].end

    def is_terminal(self, i: int) -> bool:
        return bool(TERMINAL_RE.search(self.words[i].text))

    def is_question(self, i: int) -> bool:
        return bool(QUESTION_RE.search(self.words[i].text))

    def cut_off(self, i: int) -> bool:
        t = self.words[i].text
        return bool(CUT_OFF_RE.search(t)) or not self.is_terminal(i)

    def sentence_start(self, i: int) -> bool:
        return i == 0 or self.is_terminal(i - 1)


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------


def turns_of(p: Plan) -> list[tuple[str, int, int]]:
    """Maximal runs of one framing speaker: (speaker, first word, last word)."""
    out: list[tuple[str, int, int]] = []
    for i, s in enumerate(p.spk):
        if out and out[-1][0] == s:
            out[-1] = (s, out[-1][1], i)
        else:
            out.append((s, i, i))
    return out


def absorb_backchannels(p: Plan) -> int:
    """'yeah' / 'right' inside someone's speech is not a speaker change worth a cut."""
    absorbed = 0
    ts = turns_of(p)
    for n in range(1, len(ts) - 1):
        (a, _, a1), (b, b0, b1), (c, _, _) = ts[n - 1], ts[n], ts[n + 1]
        short = (b1 - b0 + 1) <= p.cfg.backchannel_max_words and (p.words[b1].end - p.words[b0].start) <= p.cfg.backchannel_max_s
        if a == c and a != b and short and not p.is_question(a1) and not any(p.locked[b0 : b1 + 1]):
            for i in range(b0, b1 + 1):
                p.spk[i] = a
            absorbed += 1
    return absorbed


# ---------------------------------------------------------------------------
# Rule 2: both parties live
# ---------------------------------------------------------------------------


def pair_of(ctx: Ctx, a: str, b: str) -> tuple[str, str]:
    order = ctx.speaker_ids
    return (a, b) if order.index(a) <= order.index(b) else (b, a)


def tail_start(p: Plan, i0: int, i1: int) -> int:
    """First word of the closing sentence of the turn [i0, i1] (bounded by exchange_turn_s)."""
    k = max((k for k in range(i0, i1 + 1) if p.sentence_start(k)), default=i0)
    if p.words[i1].end - p.words[k].start <= p.cfg.exchange_turn_s:
        return k
    return next(k for k in range(i0, i1 + 1) if p.words[i1].end - p.words[k].start <= p.cfg.exchange_turn_s)


def head_end(p: Plan, i0: int, i1: int) -> int:
    """Last word of the opening sentence of the turn [i0, i1] (bounded by exchange_turn_s)."""
    j = next((j for j in range(i0, i1 + 1) if p.is_terminal(j)), i1)
    while p.words[j].end - p.words[i0].start > p.cfg.exchange_turn_s and j > i0:
        j -= 1
    return j


def handoff_windows(p: Plan, ts: list[tuple[str, int, int]]) -> list[tuple[int, int, tuple[str, str], str]]:
    cfg, out = p.cfg, []
    for (sx, x0, x1), (sy, y0, y1) in zip(ts, ts[1:]):
        if any(p.locked[x0 : y1 + 1]):
            continue
        gap = p.words[y0].start - p.words[x1].end
        if p.is_question(x1) and gap <= cfg.exchange_gap_s:
            why = f"question -> answer, {max(gap, 0):.1f}s gap"
        elif gap < -0.05:
            why = "overlapping speech"
        elif p.cut_off(x1) and gap <= INTERRUPT_GAP_S:
            why = "interruption"
        else:
            continue
        i0, i1 = tail_start(p, x0, x1), head_end(p, y0, y1)
        while p.span(i0, i1) < cfg.min_block_s and i1 < y1:
            i1 = head_end(p, i1 + 1, y1)
        while p.span(i0, i1) < cfg.min_block_s and i0 > x0:
            i0 = max((k for k in range(x0, i0) if p.sentence_start(k)), default=x0)
        out.append((i0, i1, pair_of(p.ctx, sx, sy), f"rule 2: {why}"))
    return out


def rapid_windows(p: Plan, ts: list[tuple[str, int, int]]) -> list[tuple[int, int, tuple[str, str], str]]:
    """>= 3 consecutive short turns between the same two people."""
    cfg, out, n = p.cfg, [], 0

    def short(t: tuple[str, int, int]) -> bool:
        return p.span(t[1], t[2]) < cfg.exchange_turn_s

    while n < len(ts):
        chain = [n]
        while short(ts[n]) and chain[-1] + 1 < len(ts):
            nxt = chain[-1] + 1
            live = p.words[ts[nxt][1]].start - p.words[ts[chain[-1]][2]].end <= cfg.exchange_gap_s
            if not (short(ts[nxt]) and live and len({ts[c][0] for c in chain + [nxt]}) <= 2):
                break
            chain.append(nxt)
        i0, i1 = ts[chain[0]][1], ts[chain[-1]][2]
        if len(chain) >= 3 and not any(p.locked[i0 : i1 + 1]):
            who = pair_of(p.ctx, *sorted({ts[c][0] for c in chain}, key=p.ctx.speaker_ids.index))
            out.append((i0, i1, who, f"rule 2: back-and-forth of {len(chain)} short turns"))
        n = chain[-1] + 1
    return out


# ---------------------------------------------------------------------------
# Labelling, blocks, dwell ceiling
# ---------------------------------------------------------------------------


def solo(speaker: str) -> Label:
    return Label(f"closeup-{speaker}")


def label_words(p: Plan) -> None:
    ts = turns_of(p)
    for i, sp in enumerate(p.spk):
        if not p.locked[i]:
            p.label[i], p.reason[i] = solo(sp), f"rule 1: {p.ctx.name(sp)} speaks"
    for i0, i1, pair, why in rapid_windows(p, ts) + handoff_windows(p, ts):
        for i in range(i0, i1 + 1):
            if not p.locked[i] and p.label[i] is not None and p.label[i].treatment != "splitscreen":
                p.label[i], p.reason[i] = Label("splitscreen", pair), why


def runs(p: Plan) -> list[tuple[int, int]]:
    """Maximal [i0, i1] ranges of equal label (locked and unlocked kept apart)."""
    out: list[tuple[int, int]] = []
    for i in range(len(p.words)):
        if out and p.label[out[-1][1]] == p.label[i] and p.locked[out[-1][1]] == p.locked[i]:
            out[-1] = (out[-1][0], i)
        else:
            out.append((i, i))
    return out


def merge_short_blocks(p: Plan) -> int:
    """No treatment flashes for less than min_block_s: fold it into a neighbour."""
    merged = 0
    changed = True
    while changed:
        changed = False
        rs = runs(p)
        for n, (i0, i1) in enumerate(rs):
            if p.locked[i0] or len(rs) == 1 or p.span(i0, i1) >= p.cfg.min_block_s:
                continue
            for m in (n - 1, n + 1):
                if 0 <= m < len(rs) and not p.locked[rs[m][0]]:
                    j = rs[m][0]
                    for i in range(i0, i1 + 1):
                        p.label[i], p.reason[i] = p.label[j], p.reason[j]
                    merged += 1
                    changed = True
                    break
            if changed:
                break
    return merged


def boundary_quality(p: Plan, i0: int, i1: int) -> tuple[int, int]:
    """(start, end) quality of the window [i0, i1]: 2 sentence boundary, 1 pause, 0 mid-phrase."""
    qs = 2 if p.sentence_start(i0) else 1 if i0 > 0 and p.gap(i0) >= PAUSE_S else 0
    qe = 2 if p.is_terminal(i1) else 1 if i1 + 1 < len(p.words) and p.gap(i1 + 1) >= PAUSE_S else 0
    return qs, qe


def listener_for(p: Plan, speaker: str, at: int) -> str:
    """The person who is NOT speaking and is nearest in the conversation to word `at`."""
    others = [(abs(k - at), p.spk[k]) for k in range(len(p.spk)) if p.spk[k] != speaker]
    if others:
        return min(others)[1]
    t = p.words[at].src_start
    near = [(abs(w.start - t), w.speaker) for w in p.transcript if w.speaker != speaker and w.speaker in p.ctx.speaker_ids]
    if not near:
        raise ValueError(f"no other speaker near {fmt_ts(t)} to pair with {speaker} for a dwell break")
    return min(near)[1]


def best_window(p: Plan, r0: int, r1: int, uniform_speaker: bool) -> tuple[int, int] | None:
    cap = min(p.cfg.exchange_turn_s, p.cfg.max_dwell_s / 2)
    floor = 2 * p.cfg.min_block_s   # an inserted break must register: at least twice the flash threshold
    t0, t1 = p.cut_out(r0), p.cut_out(r1 + 1)
    best, best_key = None, None
    for i0 in range(r0, r1 + 1):
        if p.locked[i0] or p.cut_out(i0) - t0 < p.cfg.min_block_s:
            continue
        for i1 in range(i0, r1 + 1):
            if p.locked[i1]:
                break
            if uniform_speaker and p.spk[i1] != p.spk[i0]:
                break
            dur = p.span(i0, i1)
            if dur > cap:
                break
            if dur < floor or t1 - p.cut_out(i1 + 1) < p.cfg.min_block_s:
                continue
            qs, qe = boundary_quality(p, i0, i1)
            mid = (p.cut_out(i0) + p.cut_out(i1 + 1)) / 2
            key = (min(qs, qe), qs + qe, -abs(mid - (t0 + t1) / 2))
            if best_key is None or key > best_key:
                best, best_key = (i0, i1), key
    return best


def enforce_dwell(p: Plan) -> None:
    stuck: set[tuple[int, int]] = set()
    while True:
        over = [(i0, i1) for i0, i1 in runs(p) if p.span(i0, i1) > p.cfg.max_dwell_s + EPS and (i0, i1) not in stuck]
        if not over:
            return
        r0, r1 = over[0]
        lab = p.label[r0]
        window = best_window(p, r0, r1, uniform_speaker=lab.treatment == "splitscreen")
        if window is None:
            stuck.add((r0, r1))
            p.notes.append(
                f"dwell ceiling: {treatment_label(p.ctx, lab.treatment, lab.speakers)} held "
                f"{p.span(r0, r1):.1f}s at {fmt_ts(p.cut_out(r0))} — no usable break window (locked or no room)"
            )
            continue
        i0, i1 = window
        if lab.treatment == "splitscreen":
            new, what = solo(p.spk[i0]), "solo"
        else:
            speaker = lab.treatment.removeprefix("closeup-")
            new = Label("splitscreen", pair_of(p.ctx, speaker, listener_for(p, speaker, i0)))
            what = "split with the listener"
        qs, qe = boundary_quality(p, i0, i1)
        where = "sentence boundary" if min(qs, qe) == 2 else "pause" if min(qs, qe) == 1 else "mid-phrase (no better break)"
        why = f"rule 4: {p.span(r0, r1):.0f}s dwell > {p.cfg.max_dwell_s:g}s, broken by {what} at a {where}"
        for i in range(i0, i1 + 1):
            p.label[i], p.reason[i] = new, why


# ---------------------------------------------------------------------------
# Rebuilding the timeline
# ---------------------------------------------------------------------------


def next_id_factory(timeline: list[dict]):
    pattern = re.compile(r"^(.*?)(\d+)$")
    parsed = [pattern.match(s["id"]) for s in timeline]
    if not all(parsed):
        raise ValueError(f"segment ids must look like S01, S02, … — got {[s['id'] for s in timeline]}")
    prefix, width = parsed[0].group(1), max(len(m.group(2)) for m in parsed)
    counter = max(int(m.group(2)) for m in parsed)

    def next_id() -> str:
        nonlocal counter
        counter += 1
        return f"{prefix}{counter:0{width}d}"

    return next_id


def rebuild_timeline(p: Plan) -> list[dict]:
    timeline = p.ctx.clip["timeline"]
    next_id = next_id_factory(timeline)
    by_seg: dict[int, list[int]] = {}
    for i, w in enumerate(p.words):
        by_seg.setdefault(w.seg, []).append(i)
    new: list[dict] = []
    for si, seg in enumerate(timeline):
        if p.locked[by_seg[si][0]]:
            new.append(seg)
            continue
        idx = by_seg[si]
        tokens = dialogue_tokens(seg["dialogue"])
        parts: list[list[int]] = [[idx[0]]]
        for i in idx[1:]:
            prev = parts[-1][-1]
            # one segment = one speaker's words (validate_clip invariant 11 judges `dialogue`
            # against the segment's speaker), so a speaker change always starts a new segment
            if p.label[i] == p.label[prev] and p.words[i].speaker == p.words[prev].speaker:
                parts[-1].append(i)
            else:
                parts.append([i])
        cuts = [seg["output_in"]] + [p.cut_out(part[0]) for part in parts[1:]] + [seg["output_out"]]
        for n, part in enumerate(parts):
            first, last = part[0] - idx[0], part[-1] - idx[0]
            lab = p.label[part[0]]
            piece = copy.deepcopy(seg)
            piece["id"] = seg["id"] if n == 0 else next_id()
            piece["output_in"], piece["output_out"] = round(cuts[n], 3), round(cuts[n + 1], 3)
            if n > 0:
                piece["source_in"] = round(seg["source_in"] + (cuts[n] - seg["output_in"]), 3)
            if n < len(parts) - 1:
                piece["source_out"] = round(seg["source_in"] + (cuts[n + 1] - seg["output_in"]), 3)
                piece["transition"] = "cut"
            piece["dialogue"] = " ".join(tokens[first : last + 1])
            piece["speaker"] = p.words[part[0]].speaker
            visual = piece.setdefault("visual", {"kind": "aroll"})
            visual["treatment"] = lab.treatment
            visual["speakers"] = list(lab.speakers) if lab.speakers else None
            visual["locked"] = False
            visual["reason"] = p.reason[part[0]]
            new.append(piece)
    return new


def check_invariants(old: list[dict], new: list[dict], fps: float) -> None:
    assert abs(new[0]["output_in"]) < EPS, "timeline must start at 0"
    for a, b in zip(new, new[1:]):
        assert abs(a["output_out"] - b["output_in"]) < EPS, f"gap/overlap between {a['id']} and {b['id']}"
    for s in new:
        assert abs((s["output_out"] - s["output_in"]) - (s["source_out"] - s["source_in"])) < EPS, f"{s['id']}: output/source duration mismatch"
        assert s["output_out"] - s["output_in"] >= 1 / fps - EPS, f"{s['id']}: shorter than one frame"
    assert abs(new[-1]["output_out"] - old[-1]["output_out"]) < EPS, "total duration changed"
    assert len({s["id"] for s in new}) == len(new), "duplicate segment ids"
    assert " ".join(" ".join(s["dialogue"] for s in new).split()) == " ".join(" ".join(s["dialogue"] for s in old).split()), "dialogue not preserved verbatim"
    kept = [s["id"] for s in old]
    assert [s["id"] for s in new if s["id"] in kept] == kept, "existing segment ids were reordered"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def report(ctx: Ctx, timeline: list[dict], notes: list[str], absorbed: int, dry_run: bool) -> None:
    def key(s: dict) -> tuple[str, tuple[str, ...]]:
        v = s["visual"]
        return v["treatment"], tuple(v.get("speakers") or ())

    hist: dict[str, list[float]] = {}
    for s in timeline:
        hist.setdefault(treatment_label(ctx, *(key(s)[0], list(key(s)[1]))), []).append(s["output_out"] - s["output_in"])
    total = timeline[-1]["output_out"]
    table = Table(title=f"framing — {ctx.clip['clip']['id']} ({len(timeline)} segments, {total:.1f}s)", header_style="bold cyan")
    for col, right in (("treatment", False), ("segments", True), ("seconds", True), ("share", True)):
        table.add_column(col, justify="right" if right else "left")
    for name, durs in sorted(hist.items(), key=lambda kv: -sum(kv[1])):
        table.add_row(name, str(len(durs)), f"{sum(durs):.1f}", f"{100 * sum(durs) / total:.0f}%")
    console.print(table)

    detail = Table(title="segments", header_style="bold cyan")
    for col in ("id", "output", "treatment", "reason"):
        detail.add_column(col)
    for s in timeline:
        v = s["visual"]
        detail.add_row(
            s["id"], f"{s['output_in']:.2f}-{s['output_out']:.2f}",
            treatment_label(ctx, v["treatment"], v.get("speakers")), (v.get("reason") or "") + (" [locked]" if v.get("locked") else ""),
        )
    console.print(detail)

    longest, cur = (0.0, 0.0, ""), None
    for s in timeline:
        if cur and key(s) == cur[0]:
            cur = (cur[0], cur[1], s["output_out"])
        else:
            cur = (key(s), s["output_in"], s["output_out"])
        if cur[2] - cur[1] > longest[0]:
            longest = (cur[2] - cur[1], cur[1], treatment_label(ctx, cur[0][0], list(cur[0][1])))
    console.print(f"longest dwell: [bold]{longest[0]:.1f}s[/] of {longest[2]} from {fmt_ts(longest[1])}")
    rules = Counter(re.match(r"(rule \d)", s["visual"]["reason"] or "").group(1) if re.match(r"(rule \d)", s["visual"]["reason"] or "") else "other" for s in timeline)
    console.print("segments by rule: " + ", ".join(f"{k}: {v}" for k, v in sorted(rules.items())) + f"; backchannels absorbed: {absorbed}")
    for n in notes:
        console.print(f"[yellow]note[/] {n}")
    console.print("[dim]dry run — clip.yaml not written[/]" if dry_run else "[green]clip.yaml updated[/]")


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def demote_unseen_splits(ctx: Ctx, timeline: list[dict], notes: list[str]) -> None:
    """Rule 5: a split screen whose two faces are not both on screen becomes the talker's solo."""
    episode = load_episode(ctx.root / "episode.yaml")
    framer = Framer(ctx.clip_dir, ctx.root, episode)
    out_w, out_h = (int(v) for v in ctx.clip["output"]["resolution"].split("x"))
    panel_h = out_h // 2
    for seg in timeline:
        v = seg["visual"]
        if v["treatment"] != "splitscreen" or v.get("locked"):
            continue
        model = TimelineSegment.model_validate(seg)
        missing = []
        for sid in v["speakers"]:
            source = resolve_source(model, episode, sid)
            if source[4]:
                raise ValueError("; ".join(source[4]))
            try:
                framer.shots(model, sid, source, "panel", out_w, panel_h, ctx.framing().max_upscale)
            except facelib.FaceError as err:
                missing.append(str(err))
        if not missing:
            continue
        v.update(treatment=f"closeup-{seg['speaker']}", speakers=None,
                 reason=f"split screen needs both faces on screen — solo instead ({missing[0].split(': ', 1)[1]})")
        notes.append(f"{seg['id']}: split screen demoted to closeup-{seg['speaker']} — {missing[0]}")


def plan_short(ctx: Ctx, dry_run: bool) -> None:
    cfg = ctx.framing()
    timeline = ctx.clip["timeline"]
    for seg in timeline:
        if seg["speaker"] not in ctx.speaker_ids:
            raise ValueError(f"segment {seg['id']}: speaker {seg['speaker']!r} not in episode.yaml speakers {ctx.speaker_ids}")
    transcript = load_words(ctx)
    words = place_words(ctx, transcript)
    if not words:
        raise ValueError("timeline contains no transcript words")
    locked_seg = [bool((s.get("visual") or {}).get("locked")) for s in timeline]
    plan = Plan(
        ctx=ctx, cfg=cfg, words=words,
        spk=[w.speaker for w in words], locked=[locked_seg[w.seg] for w in words],
        label=[None] * len(words), reason=[""] * len(words),
        duration=timeline[-1]["output_out"], fps=float(ctx.clip["output"]["fps"]), transcript=transcript,
    )
    for i, w in enumerate(words):
        if plan.locked[i]:
            v = timeline[w.seg]["visual"]
            plan.label[i] = Label(v["treatment"], tuple(v["speakers"]) if v.get("speakers") else None)
            plan.reason[i] = v.get("reason") or "locked"
        elif w.speaker not in ctx.speaker_ids:
            raise ValueError(f"transcript word {w.w!r} at {w.start:.2f}s has unknown speaker {w.speaker!r}")
    absorbed = absorb_backchannels(plan)
    label_words(plan)
    merge_short_blocks(plan)
    enforce_dwell(plan)
    new = rebuild_timeline(plan)
    check_invariants(timeline, new, plan.fps)
    demote_unseen_splits(ctx, new, plan.notes)
    for lab in {plan.label[i] for i in range(len(words))}:
        if lab.treatment == "splitscreen" and (lab.speakers is None or len(set(lab.speakers)) != 2):
            raise AssertionError(f"split screen without exactly two speakers: {lab}")
    report(ctx, new, plan.notes, absorbed, dry_run)
    if not dry_run:
        ctx.clip["timeline"] = new
        ctx.save_clip()


def plan_clip(ctx: Ctx, dry_run: bool) -> None:
    for seg in ctx.clip["timeline"]:
        visual = seg.setdefault("visual", {"kind": "aroll"})
        if visual.get("locked"):
            continue
        visual.update(treatment="source-frame", speakers=None, locked=False, reason="clip: the horizontal source is already framed")
    console.print(f"[green]{ctx.clip['clip']['id']}[/]: format clip — {len(ctx.clip['timeline'])} segments, all source-frame")
    if not dry_run:
        ctx.save_clip()


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root (default: CLIP_DIR/../..)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print the plan; do not write clip.yaml"),
) -> None:
    """Compute per-segment framing for CLIP_DIR and write it into clip.yaml."""
    ctx = load_ctx(clip_dir, episode_root)
    (plan_short if ctx.fmt == "short" else plan_clip)(ctx, dry_run)
    logger.info("done")


if __name__ == "__main__":
    app()
