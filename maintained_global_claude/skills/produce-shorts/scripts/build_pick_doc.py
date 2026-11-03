#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "google-api-python-client>=2.120",
#   "google-auth>=2.30",
#   "google-auth-httplib2>=0.2",
# ]
# ///
"""Stage 1 — build the pick doc: draft-picks.json + transcript -> a Google Doc in Drive.

Validates the editor's picks (references/pick-doc.md §3), renders the HTML (§4), uploads it
converted to a Google Doc in `<review.drive_folder>/<episode id>/`, then repairs/verifies the
colours, strikethrough and labels with in-place Docs edits (so a lossy HTML import can never
leave the doc different from what was intended), and records the `review:` block in
episode.yaml. Requires `published-overlap.json` (run `published_shorts.py match` first).
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rich.console import Console
from rich.table import Table

import gdoc
from gdoc import (BLACK, FORMATS, Ctx, Model, PickMeta, die, fmt_clock, fmt_dur, kept_duration,
                  kept_segments, load_ctx, load_published, plan_paragraphs, search_key,
                  validate_model, word_style)

console = Console(stderr=True)
app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)

SNAP_TOL_S = 5.0
KEY_TEXT = (
    "How to comment: highlight at least ~5 words of the transcript and comment in plain language "
    "(\"start here\", \"end after this\", \"include up to 14:10\", \"cut this\", \"keep this\", \"drop\", "
    "\"approve\", \"new short: this exchange\", \"make this a clip\"); comment on a ▶ label or on a "
    "status line to talk about a whole pick. Colours mark the proposed picks and every pick has its own "
    "colour; grey text lies outside every pick; coloured text on a pick's colour is what it keeps; "
    "coloured text with a line through it is cut from inside that pick."
)


# ---------------------------------------------------------------------------
# draft-picks.json -> Model
# ---------------------------------------------------------------------------


def find_sequence(ctx: Ctx, text: str, near: float, *, end: bool) -> tuple[list[int], int]:
    """Word indices where the verbatim run `text` sits within +-SNAP_TOL_S of `near`.

    Returns (candidate indices, token count); an index is the run's first word (end=False)
    or its last word (end=True)."""
    toks = [k for k in (search_key(t) for t in text.split()) if k]
    if not toks:
        return [], 0
    keys, words, n = ctx.search_keys(), ctx.words, len(toks)
    hits = []
    for i in range(len(keys) - n + 1):
        if keys[i] != toks[0] or keys[i:i + n] != toks:
            continue
        t = words[i + n - 1]["end"] if end else words[i]["start"]
        if abs(t - near) <= SNAP_TOL_S:
            hits.append(i + n - 1 if end else i)
    return hits, n


def snap(ctx: Ctx, pid: str, what: str, text: str, near: float, *, end: bool) -> int:
    hits, n = find_sequence(ctx, text, near, end=end)
    if not hits:
        die(f"pick {pid}: {what} {text!r} not found within ±{SNAP_TOL_S:.0f}s of {near:.1f}s "
            f"({fmt_clock(near)}) in transcript.json — quote the words verbatim")
    if len(hits) > 1:
        at = ", ".join(fmt_clock(ctx.words[h]["start"]) for h in hits)
        die(f"pick {pid}: {what} {text!r} matches {len(hits)} places within ±{SNAP_TOL_S:.0f}s of "
            f"{near:.1f}s ({at}) — quote more words")
    return hits[0]


def model_from_draft(ctx: Ctx, draft: dict[str, Any]) -> Model:
    picks_raw = draft["picks"]
    if not picks_raw:
        die("draft-picks.json has no picks")
    palette = ctx.cfg["palette"]
    if len(picks_raw) > len(palette):
        die(f"{len(picks_raw)} picks but only {len(palette)} palette colours (review.palette)")
    n = len(ctx.words)
    owner: list[str | None] = [None] * n
    cut = [False] * n
    metas: dict[str, PickMeta] = {}
    for rank, p in enumerate(picks_raw):
        pid, fmt = p["id"], p["format"]
        if fmt not in FORMATS:
            die(f"pick {pid}: unknown format {fmt!r} (short|clip)")
        if pid[0] != FORMATS[fmt]:
            die(f"pick {pid}: id prefix does not match format {fmt!r} (S<n> for short, C<n> for clip)")
        if pid in metas:
            die(f"duplicate pick id {pid}")
        metas[pid] = PickMeta(pid, fmt, palette[rank].upper(), "proposed", p["title"], p["why"])
        last_end = -1
        for r, reg in enumerate(p["regions"], start=1):
            a = snap(ctx, pid, f"region {r} start_words", reg["start_words"], reg["start"], end=False)
            b = snap(ctx, pid, f"region {r} end_words", reg["end_words"], reg["end"], end=True)
            if b < a:
                die(f"pick {pid}: region {r} ends (word #{b}) before it starts (word #{a})")
            if a <= last_end:
                die(f"pick {pid}: region {r} overlaps or precedes the previous region — regions play in source order")
            last_end = b
            for i in range(a, b + 1):
                if owner[i] is not None:
                    die(f"pick {pid} overlaps pick {owner[i]} at {fmt_clock(ctx.words[i]['start'])} "
                        f"({ctx.words[i]['w']!r}) — a word belongs to at most one pick")
                owner[i] = pid
        for c in p.get("cuts") or []:
            a = snap(ctx, pid, "cut", c["words"], c["start"], end=False)
            toks = [k for k in (search_key(t) for t in c["words"].split()) if k]
            for i in range(a, a + len(toks)):
                if owner[i] != pid:
                    die(f"pick {pid}: cut {c['words']!r} at {fmt_clock(ctx.words[a]['start'])} lies outside "
                        f"the pick's regions")
                cut[i] = True
    model = Model(owner, cut, metas)
    validate_model(ctx, model)
    return model


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def css(st: gdoc.Style) -> str:
    parts = []
    if st.bg:
        parts.append(f"background-color:{st.bg}")
    parts.append(f"color:{st.fg or BLACK}")
    if st.bold:
        parts.append("font-weight:bold")
    if st.italic:
        parts.append("font-style:italic")
    if st.strike:
        parts.append("text-decoration:line-through")
    if st.size:
        parts.append(f"font-size:{st.size:g}pt")
    return ";".join(parts)


def span(text: str, st: gdoc.Style) -> str:
    return f'<span style="{css(st)}">{html.escape(text)}</span>'


def render_html(ctx: Ctx, model: Model, published: list[dict[str, Any]], title: str) -> str:
    paras = plan_paragraphs(ctx.words, ctx.interj, ctx.elided)
    n = len(ctx.words)
    word_anchor = [0] * n
    for k, p in enumerate(paras):
        for i in range(p.first, p.last + 1):
            word_anchor[i] = k
    for i in range(n):  # elided words point at the next shown word's paragraph
        if ctx.elided[i]:
            word_anchor[i] = next((word_anchor[j] for j in range(i + 1, n) if not ctx.elided[j]), len(paras) - 1)
    status, gaps = gdoc.desired_structure(ctx, model, word_anchor, published)
    body = [f"<h1>{html.escape(title)}</h1>", f"<p>{html.escape(KEY_TEXT)}</p>"]
    body += [f"<p>{span(it.text, it.style)}</p>" for it in status]
    w = ctx.words
    for k, p in enumerate(paras):
        body += [f"<p>{span(it.text, it.style)}</p>" for it in gaps.get(k, [])]
        if p.header:
            body.append(f"<p>{span(gdoc.header_text(ctx, p), gdoc.Style(fg='#333333', bold=True, size=12))}</p>")
        shown = [i for i in range(p.first, p.last + 1) if not ctx.elided[i]]
        runs: list[tuple[gdoc.Style, list[str]]] = []
        inside = False
        for pos, i in enumerate(shown):
            nxt = shown[pos + 1] if pos + 1 < len(shown) else None
            txt = ""
            if ctx.interj[i] and not inside and pos:
                txt += f"({ctx.names[w[i]['speaker']]}: "
                inside = True
            txt += w[i]["w"]
            if inside and not (nxt is not None and ctx.interj[nxt] and w[nxt]["speaker"] == w[i]["speaker"]):
                txt += ")"
                inside = False
            if i + 1 < n and ctx.elided[i + 1]:
                txt += " \u2026"
            if nxt is not None:
                txt += " "
            st = word_style(ctx, model, i)
            if runs and runs[-1][0].sig() == st.sig() and runs[-1][0].size == st.size:
                runs[-1][1].append(txt)
            else:
                runs.append((st, [txt]))
        prefix = "" if p.header else span(gdoc.cont_prefix(p), gdoc.Style(fg="#B0B0B0", size=8))
        body.append("<p>" + prefix + "".join(span("".join(t), st) for st, t in runs) + "</p>")
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title></head>'
            f"<body>{''.join(body)}</body></html>")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def summary_table(ctx: Ctx, model: Model) -> Table:
    t = Table(title="picks")
    for col in ("id", "format", "dur", "colour", "title"):
        t.add_column(col)
    for pid, m in sorted(model.picks.items(), key=lambda kv: gdoc.pick_sort_key(kv[0])):
        dur = fmt_dur(kept_duration(ctx.words, kept_segments(ctx.words, model, pid)))
        t.add_row(pid, m.format, dur, m.color, m.title)
    return t


@app.command()
def build(
    episode_dir: Path = typer.Argument(..., help="Episode directory (episode.yaml, transcript/, review/draft-picks.json)"),
    title_prefix: str = typer.Option("", help="Prepended to the Drive file name and the doc title, e.g. '[TEST] '"),
    new_doc: bool = typer.Option(False, "--new-doc", help="Create a second doc even though the episode already has one"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate and write review/pick-doc.html only; no Drive access"),
) -> None:
    """Validate draft-picks.json, render the doc, upload it, record review: in episode.yaml."""
    ctx = load_ctx(episode_dir)
    draft_path = ctx.dir / "review" / "draft-picks.json"
    if not draft_path.exists():
        die(f"{draft_path} is missing — the editor writes it (references/pick-doc.md §2)")
    published = load_published(ctx)
    model = model_from_draft(ctx, json.loads(draft_path.read_text()))
    title = f"{title_prefix}{ctx.data['episode']['title']} — picks"
    page = render_html(ctx, model, published, title)
    html_path = ctx.dir / "review" / "pick-doc.html"
    html_path.write_text(page)
    console.print(summary_table(ctx, model))
    logger.info("wrote {} ({} KB)", html_path, len(page) // 1024)
    if dry_run:
        return
    if ctx.review.get("pick_doc") and not new_doc:
        die(f"episode.yaml already has a pick doc ({ctx.review['pick_doc']['url']}); rebuilding would orphan "
            f"the user's comments — edit it with doc_ops.py, or pass --new-doc to make a second doc")

    g = gdoc.Google(ctx.account)
    top = g.find_or_create_folder(ctx.cfg["drive_folder"])
    folder = g.find_or_create_folder(ctx.data["episode"]["id"], parent=top)
    doc = g.upload_html_as_doc(page, title, folder)
    logger.info("uploaded {}", doc["url"])

    ctx.review.update({"account": ctx.account, "folder_id": folder, "pick_doc": doc, "round": 0})
    ctx.store_picks(model, published)
    n = gdoc.sync(ctx, g, doc["id"], published, model)
    logger.info("post-upload verification passed ({} repair request(s) needed)", n)
    shorts = sum(m.format == "short" for m in model.picks.values())
    ctx.review["log_comment_id"] = g.create_comment(
        doc["id"], f"Revision log. Rev 0 — initial proposal: {shorts} short(s), {len(model.picks) - shorts} clip(s).")
    ctx.data.setdefault("status", {})["stage"] = "picking"
    ctx.save()
    print(doc["url"])


if __name__ == "__main__":
    app()
