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
"""The stage-1 comment loop — read comments, locate quoted text, edit picks IN PLACE, reply.

Every edit is a Docs `batchUpdate` against the live pick doc (colours, strikethrough, label and
status text), never a re-upload, so the user's comments stay anchored. Each edit re-validates
(no overlapping picks, short < 180 s, nothing outside the published spans) before touching the
doc, then reads the doc back and verifies it. Word indices are INCLUSIVE; find them with
`locate`. Storyboard docs use `comments|reply|resolve --doc DOC_ID`. See references/pick-doc.md §5.
"""

from __future__ import annotations

import bisect
import html
import json
import re
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger

import gdoc
from gdoc import (Ctx, Model, PickMeta, die, ends_on, fmt_clock, fmt_dur, kept_duration, kept_segments,
                  load_ctx, load_published, locate_quote, pick_ranges_text)

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)

EPISODE = typer.Argument(..., help="Episode directory")
PICK = typer.Argument(..., help="Pick id, e.g. S1 or C2")


class Snap(str, Enum):
    none = "none"
    start = "start"
    end = "end"
    both = "both"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def need_pick(m: Model, pid: str) -> None:
    if pid not in m.picks:
        die(f"unknown pick {pid!r}; the doc has {sorted(m.picks, key=gdoc.pick_sort_key)}")


def check_range(ctx: Ctx, a: int, b: int) -> None:
    n = len(ctx.words)
    if not (0 <= a <= b < n):
        die(f"word range {a}..{b} is invalid (need 0 <= start <= end < {n}; both inclusive)")


def where(ctx: Ctx, i: int) -> str:
    return f"word #{i} {ctx.words[i]['w']!r} at {fmt_clock(ctx.words[i]['start'])}"


def claim(ctx: Ctx, m: Model, pid: str, a: int, b: int) -> None:
    for i in range(a, b + 1):
        if m.owner[i] is not None:
            die(f"{pid}: {where(ctx, i)} already belongs to {m.owner[i]} — a word belongs to at most one pick "
                f"(a dropped pick keeps its words reserved)")
        m.owner[i], m.cut[i] = pid, False


def release(m: Model, a: int, b: int) -> None:
    for i in range(a, b + 1):
        m.owner[i], m.cut[i] = None, False


def pick_summary(ctx: Ctx, m: Model, pid: str) -> dict[str, Any]:
    meta = m.picks[pid]
    segs = kept_segments(ctx.words, m, pid)
    dur = kept_duration(ctx.words, segs)
    ranges = pick_ranges_text(ctx, m.regions(pid))
    return {"pick": pid, "format": meta.format, "status": meta.status, "title": meta.title,
            "duration": fmt_dur(dur), "duration_s": round(dur, 1), "ranges": ranges,
            "ends_on": ends_on(ctx.words, m, pid),
            "summary": f'{pid} now {ranges} ({fmt_dur(dur)}), ends on "{ends_on(ctx.words, m, pid)}"'}


def run_edit(episode_dir: Path, mutate: Callable[[Ctx, Model], tuple[Model, str]]) -> None:
    """Load, apply `mutate` to the live doc's model in place, verify, persist, print the result."""
    ctx = load_ctx(episode_dir)
    published = load_published(ctx)
    g = gdoc.Google(ctx.account)
    result: dict[str, Any] = {}

    def desired(live: Model) -> Model:
        new, focus = mutate(ctx, live)
        result["model"], result["focus"] = new, focus
        return new

    def commit(model: Model) -> None:
        ctx.store_picks(model, published)
        ctx.save()

    n = gdoc.sync(ctx, g, ctx.doc_id(), published, desired, commit)
    out = pick_summary(ctx, result["model"], result["focus"])
    out["docs_requests"] = n
    print(json.dumps(out, indent=2, ensure_ascii=False))


@app.command()
def show(episode_dir: Path = EPISODE, pick: str = typer.Argument(None, help="Pick id (default: every pick)")) -> None:
    """Print the internal details of a pick (why, regions, ends_on, overlap) from episode.yaml review.picks.

    These details are no longer in the Google Doc; `range`/`cut`/`add`/... keep them current.
    """
    picks = load_ctx(episode_dir).review.get("picks") or {}
    if pick and pick not in picks:
        die(f"no pick {pick} in episode.yaml (have: {', '.join(picks) or 'none'})")
    print(json.dumps({pick: picks[pick]} if pick else picks, indent=2, ensure_ascii=False))


def split_args(args: list[str], doc: str | None, usage: str, n_with_episode: int) -> tuple[Path | None, list[str]]:
    if doc:
        if len(args) != n_with_episode - 1:
            die(f"usage with --doc: doc_ops.py {usage.replace('EPISODE_DIR ', '')} --doc DOC_ID")
        return None, args
    if len(args) != n_with_episode:
        die(f"usage: doc_ops.py {usage}  (or without EPISODE_DIR when --doc DOC_ID is given)")
    return Path(args[0]), args[1:]


def google_for(episode_dir: Path | None, account: str | None) -> tuple[gdoc.Google, Ctx | None]:
    if episode_dir:
        ctx = load_ctx(episode_dir)
        return gdoc.Google(ctx.account), ctx
    return gdoc.Google(account or gdoc.review_defaults()["account"]), None


# ---------------------------------------------------------------------------
# comments / locate
# ---------------------------------------------------------------------------


def snap_start(ctx: Ctx, i: int) -> int:
    w = ctx.words
    while i > 0 and w[i - 1]["speaker"] == w[i]["speaker"] and not gdoc.ends_sentence(w[i - 1]["w"]):
        i -= 1
    return i


def snap_end(ctx: Ctx, j: int) -> int:
    w = ctx.words
    while j + 1 < len(w) and w[j + 1]["speaker"] == w[j]["speaker"] and not gdoc.ends_sentence(w[j]["w"]):
        j += 1
    return j


def apply_snap(ctx: Ctx, a: int, b: int, snap: Snap) -> tuple[int, int]:
    if snap in (Snap.start, Snap.both):
        a = snap_start(ctx, a)
    if snap in (Snap.end, Snap.both):
        b = snap_end(ctx, b)
    return a, b


@app.command()
def locate(
    episode_dir: Path = EPISODE,
    quote: str = typer.Argument("", help="Quoted (highlighted) text; must match the transcript exactly once"),
    time: str = typer.Option("", "--time", help="Seconds, mm:ss or h:mm:ss -> the word spoken at that time"),
    snap: Snap = typer.Option(Snap.none, help="Move the start back to a sentence start and/or the end to a sentence end"),
) -> None:
    """Word range of a quote (or the word at --time). Fails loud when absent or ambiguous."""
    ctx = load_ctx(episode_dir)
    if bool(quote) == bool(time):
        die("give exactly one of QUOTE or --time")
    if time:
        t = gdoc.parse_clock(time) if ":" in time else float(time)
        starts = [w["start"] for w in ctx.words]
        i = max(bisect.bisect_right(starts, t) - 1, 0)
        if t > ctx.words[i]["end"] and i + 1 < len(ctx.words):
            i += 1  # in a gap: the next word to be spoken
        a, b = apply_snap(ctx, i, i, snap)
    else:
        rng, err = locate_quote(ctx, quote)
        if err:
            die(err)
        a, b = apply_snap(ctx, *rng, snap)  # type: ignore[misc]
    print(json.dumps(gdoc.describe_range(ctx, a, b), indent=2, ensure_ascii=False))


def thread_json(c: dict[str, Any], ctx: Ctx | None, model: Model | None) -> dict[str, Any]:
    quote = html.unescape((c.get("quotedFileContent") or {}).get("value", ""))
    out: dict[str, Any] = {
        "id": c["id"], "author": (c.get("author") or {}).get("displayName"), "created": c.get("createdTime"),
        "content": c["content"], "quoted": quote, "resolved": c.get("resolved", False),
        "replies": [{"id": r["id"], "author": (r.get("author") or {}).get("displayName"),
                     "created": r.get("createdTime"), "content": r.get("content", ""), "action": r.get("action")}
                    for r in c.get("replies", [])],
    }
    if not ctx or model is None:
        return out
    first = quote.strip().splitlines()[0] if quote.strip() else ""
    if first.startswith("▶") and (m := gdoc.LABEL_RE.match(first)):
        out["target"] = {"kind": "label", "pick": m.group(1)}
    elif m := gdoc.STATUS_RE.match(first):
        out["target"] = {"kind": "status", "pick": m.group(1)}
    elif not quote.strip():
        out["target"] = {"kind": "doc"}
    else:
        rng, err = locate_quote(ctx, quote)
        if err:
            out["target"] = {"kind": "text", "locate_error": err}
        else:
            a, b = rng  # type: ignore[misc]
            owners = sorted({model.owner[i] for i in range(a, b + 1) if model.owner[i]}, key=gdoc.pick_sort_key)
            cuts = sum(model.cut[a:b + 1])
            out["target"] = {"kind": "text", "in_picks": owners, "cut_words_in_range": cuts,
                             **gdoc.describe_range(ctx, a, b)}
    return out


@app.command()
def comments(
    args: list[str] = typer.Argument(None, help="EPISODE_DIR (omit with --doc)"),
    doc: str = typer.Option(None, "--doc", help="Comment on any doc by id (storyboard docs)"),
    account: str = typer.Option(None, help="Google account for --doc (default: review.account)"),
    all_: bool = typer.Option(False, "--all", help="Include resolved threads"),
) -> None:
    """Open comment threads (JSON): quoted text, full reply chain, resolved word range."""
    ep, _ = split_args(args or [], doc, "comments EPISODE_DIR", 1)
    g, ctx = google_for(ep, account)
    doc_id = doc or ctx.doc_id()  # type: ignore[union-attr]
    threads = g.list_comments(doc_id)
    log_id = ctx.review.get("log_comment_id") if ctx else None
    threads = [c for c in threads if c["id"] != log_id and (all_ or not c.get("resolved"))]
    model = None
    if ctx and threads:
        model = gdoc.read_model(ctx, gdoc.align_doc(gdoc.parse_doc(g.get_doc(doc_id), ctx), ctx))
    out = sorted((thread_json(c, ctx, model) for c in threads), key=lambda t: t["created"] or "")
    if not out:
        logger.info("no {} comment threads on {}", "" if all_ else "open", doc_id)
    print(json.dumps(out, indent=2, ensure_ascii=False))


@app.command()
def reply(
    args: list[str] = typer.Argument(None, help="EPISODE_DIR COMMENT_ID TEXT  (with --doc: COMMENT_ID TEXT)"),
    doc: str = typer.Option(None, "--doc"),
    account: str = typer.Option(None),
) -> None:
    """Reply to a comment thread (leave it open — a question back to the user)."""
    ep, rest = split_args(args or [], doc, "reply EPISODE_DIR COMMENT_ID TEXT", 3)
    g, ctx = google_for(ep, account)
    rid = g.reply(doc or ctx.doc_id(), rest[0], rest[1])  # type: ignore[union-attr]
    print(json.dumps({"comment": rest[0], "reply": rid}))


@app.command()
def resolve(
    args: list[str] = typer.Argument(None, help="EPISODE_DIR COMMENT_ID  (with --doc: COMMENT_ID)"),
    doc: str = typer.Option(None, "--doc"),
    account: str = typer.Option(None),
    message: str = typer.Option("", help="Optional text posted with the resolve"),
) -> None:
    """Resolve a comment thread."""
    ep, rest = split_args(args or [], doc, "resolve EPISODE_DIR COMMENT_ID", 2)
    g, ctx = google_for(ep, account)
    rid = g.reply(doc or ctx.doc_id(), rest[0], message, action="resolve")  # type: ignore[union-attr]
    print(json.dumps({"comment": rest[0], "resolved_by_reply": rid}))


@app.command()
def log(episode_dir: Path = EPISODE, line: str = typer.Argument(..., help="e.g. 'Rev 2 — addressed 5, open 1'")) -> None:
    """Append one line to the doc's revision-log thread."""
    ctx = load_ctx(episode_dir)
    cid = ctx.review.get("log_comment_id")
    if not cid:
        die("episode.yaml has no review.log_comment_id — was the doc built by build_pick_doc.py?")
    g = gdoc.Google(ctx.account)
    rid = g.reply(ctx.doc_id(), cid, line)
    if m := re.match(r"\s*Rev (\d+)", line):
        ctx.review["round"] = int(m.group(1))
        ctx.save()
    print(json.dumps({"log_comment": cid, "reply": rid, "round": ctx.review.get("round")}))


# ---------------------------------------------------------------------------
# pick edits
# ---------------------------------------------------------------------------


@app.command("range")
def range_(
    episode_dir: Path = EPISODE, pick: str = PICK,
    start_word: int = typer.Option(None, help="New first word of the pick's first region (inclusive)"),
    end_word: int = typer.Option(None, help="New last word of the pick's last region (inclusive)"),
) -> None:
    """Move a pick's start and/or end."""
    if start_word is None and end_word is None:
        die("give --start-word and/or --end-word")

    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        need_pick(m, pick)
        for w in (start_word, end_word):
            if w is not None:
                check_range(ctx, w, w)
        if start_word is not None:
            a0, b0 = m.regions(pick)[0]
            if start_word < a0:
                claim(ctx, m, pick, start_word, a0 - 1)
            elif start_word > a0:
                if start_word > b0:
                    die(f"{pick}: --start-word {start_word} is beyond the end of its first region ({a0}..{b0}); "
                        f"use cut/add-region instead")
                release(m, a0, start_word - 1)
        if end_word is not None:
            a1, b1 = m.regions(pick)[-1]
            if end_word > b1:
                claim(ctx, m, pick, b1 + 1, end_word)
            elif end_word < b1:
                if end_word < a1:
                    die(f"{pick}: --end-word {end_word} is before the start of its last region ({a1}..{b1})")
                release(m, end_word + 1, b1)
        return m, pick

    run_edit(episode_dir, mutate)


def _cut(episode_dir: Path, pick: str, a: int, b: int, value: bool) -> None:
    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        need_pick(m, pick)
        check_range(ctx, a, b)
        for i in range(a, b + 1):
            if m.owner[i] != pick:
                die(f"{pick}: {where(ctx, i)} is not inside {pick} (owner: {m.owner[i]}) — "
                    f"{'cuts' if value else 'un-cuts'} must lie inside the pick's regions")
            m.cut[i] = value
        return m, pick

    run_edit(episode_dir, mutate)


@app.command()
def cut(episode_dir: Path = EPISODE, pick: str = PICK,
        from_word: int = typer.Option(..., help="First word to cut (inclusive)"),
        to_word: int = typer.Option(..., help="Last word to cut (inclusive)")) -> None:
    """Cut words from inside a pick (struck through, never rendered)."""
    _cut(episode_dir, pick, from_word, to_word, True)


@app.command()
def uncut(episode_dir: Path = EPISODE, pick: str = PICK,
          from_word: int = typer.Option(..., help="First word to restore (inclusive)"),
          to_word: int = typer.Option(..., help="Last word to restore (inclusive)")) -> None:
    """Restore cut words."""
    _cut(episode_dir, pick, from_word, to_word, False)


@app.command("add-region")
def add_region(episode_dir: Path = EPISODE, pick: str = PICK,
               start_word: int = typer.Option(...), end_word: int = typer.Option(...)) -> None:
    """Splice another region (from anywhere in the episode) into a pick."""

    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        need_pick(m, pick)
        check_range(ctx, start_word, end_word)
        claim(ctx, m, pick, start_word, end_word)
        return m, pick

    run_edit(episode_dir, mutate)


@app.command()
def add(episode_dir: Path = EPISODE, pick: str = PICK,
        format: str = typer.Option(..., help="short | clip"),
        start_word: int = typer.Option(...), end_word: int = typer.Option(...),
        title: str = typer.Option(...), why: str = typer.Option("Added during review.")) -> None:
    """Add a new pick (new colour, new label and status line)."""

    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        if format not in gdoc.FORMATS:
            die(f"unknown format {format!r} (short|clip)")
        if not re.fullmatch(rf"{gdoc.FORMATS[format]}\d+", pick):
            die(f"id {pick!r} does not match format {format!r} (S<n> for short, C<n> for clip)")
        if pick in m.picks:
            die(f"pick {pick} already exists")
        check_range(ctx, start_word, end_word)
        used = {p.color for p in m.picks.values()}
        free = [c.upper() for c in ctx.cfg["palette"] if c.upper() not in used]
        if not free:
            die("every palette colour is already used by a pick (review.palette)")
        m.picks[pick] = PickMeta(pick, format, free[0], "proposed", title, why)
        claim(ctx, m, pick, start_word, end_word)
        return m, pick

    run_edit(episode_dir, mutate)


@app.command("format")
def format_(episode_dir: Path = EPISODE, pick: str = PICK,
            new_format: str = typer.Argument(..., help="short | clip")) -> None:
    """Change a pick's format; renumbers it to the next free id of the new kind (S2 -> C<n>)."""

    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        need_pick(m, pick)
        if new_format not in gdoc.FORMATS:
            die(f"unknown format {new_format!r} (short|clip)")
        if m.picks[pick].format == new_format:
            die(f"{pick} is already a {new_format}")
        new_id = gdoc.next_free_id(m.picks, new_format)
        meta = m.picks[pick]
        meta.id, meta.format = new_id, new_format
        m.picks = {(new_id if k == pick else k): meta if k == pick else v for k, v in m.picks.items()}
        m.owner = [new_id if o == pick else o for o in m.owner]
        return m, new_id

    run_edit(episode_dir, mutate)


@app.command()
def status(episode_dir: Path = EPISODE, pick: str = PICK,
           new_status: str = typer.Argument(..., help="proposed | approved | dropped")) -> None:
    """Mark a pick proposed / approved / dropped (also reopens)."""

    def mutate(ctx: Ctx, live: Model) -> tuple[Model, str]:
        m = live.copy()
        need_pick(m, pick)
        if new_status not in gdoc.STATUSES:
            die(f"unknown status {new_status!r} ({'|'.join(gdoc.STATUSES)})")
        m.picks[pick].status = new_status
        return m, pick

    run_edit(episode_dir, mutate)


# ---------------------------------------------------------------------------
# final render link in a storyboard doc
# ---------------------------------------------------------------------------


@app.command()
def final(clip_dir: Path = typer.Argument(..., help="clips/<slug> directory"),
          url: str = typer.Option(..., "--url", help="Drive link of the final render")) -> None:
    """Insert `FINAL RENDER v<N>: <url>` at the top of the clip's latest storyboard doc."""
    clip_dir = clip_dir.expanduser().resolve()
    clip = gdoc.load_yaml(clip_dir / "clip.yaml")
    docs = (clip.get("review") or {}).get("storyboard_docs") or []
    if not docs:
        die(f"{clip_dir / 'clip.yaml'} has no review.storyboard_docs — build the storyboard doc first")
    latest = max(docs, key=lambda d: d["rev"])
    versions = (clip.get("render") or {}).get("versions") or []
    if not versions:
        die(f"{clip_dir / 'clip.yaml'} has no render.versions — render before adding the final link")
    n = versions[-1]["version"]
    episode = clip_dir.parent.parent
    account = (gdoc.load_yaml(episode / "episode.yaml").get("review") or {}).get("account") \
        or gdoc.review_defaults()["account"]
    g = gdoc.Google(account)
    text = f"FINAL RENDER v{n}: {url}"
    first = _first_paragraph(g.get_doc(latest["id"]))
    reqs: list[dict[str, Any]] = []
    if first["text"].startswith("FINAL RENDER v"):
        if first["text"] == text:
            print(json.dumps({"doc": latest["url"], "unchanged": True}))
            return
        if first["text"].startswith(f"FINAL RENDER v{n}:"):
            reqs.append({"deleteContentRange": {"range": {"startIndex": first["start"], "endIndex": first["text_end"]}}})
            insert_at, newline = first["start"], ""
        else:
            insert_at, newline = first["start"], "\n"
    else:
        insert_at, newline = first["start"], "\n"
    size = gdoc._utf16_len(text)
    reqs += [
        {"insertText": {"location": {"index": insert_at}, "text": text + newline}},
        {"updateTextStyle": {"range": {"startIndex": insert_at, "endIndex": insert_at + size},
                             "textStyle": {"bold": True}, "fields": "bold"}},
        {"updateTextStyle": {"range": {"startIndex": insert_at + size - gdoc._utf16_len(url), "endIndex": insert_at + size},
                             "textStyle": {"link": {"url": url}}, "fields": "link"}},
    ]
    if newline:
        reqs.append({"updateParagraphStyle": {
            "range": {"startIndex": insert_at, "endIndex": insert_at + size + 1},
            "paragraphStyle": {"namedStyleType": "NORMAL_TEXT"}, "fields": "namedStyleType"}})
    g.batch_update(latest["id"], reqs)
    after = _first_paragraph(g.get_doc(latest["id"]))
    if after["text"] != text:
        die(f"readback mismatch: first paragraph of {latest['url']} is {after['text'][:80]!r}, expected {text!r}")
    print(json.dumps({"doc": latest["url"], "line": text}))


def _first_paragraph(doc: dict[str, Any]) -> dict[str, Any]:
    for el in doc["body"]["content"]:
        p = el.get("paragraph")
        if p:
            text = "".join(e.get("textRun", {}).get("content", "") for e in p["elements"]).rstrip("\n")
            return {"start": el.get("startIndex", 1), "text": text,
                    "text_end": el["endIndex"] - 1}
    die("document has no paragraphs")


if __name__ == "__main__":
    app()
