"""Shared library for the stage-1 Google-Doc tooling (pick doc, comment loop, freeze).

Not executable. Imported by build_pick_doc.py, doc_ops.py, freeze_picks.py (the script
directory is on sys.path). Spec: ../references/pick-doc.md and ../references/schemas.md.

Sections
  1. errors, config, episode context, published-overlap file
  2. clock formatting, words, paragraph plan
  3. pick model (owner/cut per word), kept segments, validation
  4. text of labels / status lines / markers, desired document structure
  5. Docs-API document parsing, word alignment, model read-back
  6. edit planning (in-place diffs) and application
  7. Google auth + Drive/Docs client

The one primitive everything rests on is the *alignment*: the live document's transcript
paragraphs are aligned token-by-token to transcript.json words, giving word index <-> Docs
character-index ranges. Picks are the words' background colour; cuts are strikethrough.
"""

from __future__ import annotations

import io
import json
import re
import subprocess
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, NoReturn

import yaml
from loguru import logger

SKILL_DIR = Path(__file__).resolve().parent.parent
DEFAULTS_YAML = SKILL_DIR / "config" / "defaults.yaml"

PICK_FG = "#202020"  # text colour on a pick's background
BLACK = "#000000"
SHORT_LIMIT_S = 180.0
FORMATS = {"short": "S", "clip": "C"}
FORMAT_LABEL = {"short": "SHORT (vertical)", "clip": "CLIP (horizontal)"}
FORMAT_NAME = {"short": "SHORT", "clip": "CLIP"}
PARA_MIN_S, PARA_MAX_S, PARA_MAX_SENTENCES = 20.0, 30.0, 5  # body paragraph length targets
# (space above pt, space below pt) per paragraph kind; line spacing 115 %
SPACING = {"header": (14.0, 2.0), "transcript": (0.0, 10.0), "label": (10.0, 4.0), "status": (0.0, 2.0),
           "marker": (4.0, 2.0)}
LINE_SPACING = 115.0
STATUSES = ("proposed", "approved", "dropped")
ENDS_ON_WORDS = 8
BATCH_CHUNK = 400


# ---------------------------------------------------------------------------
# 1. errors, config, episode context
# ---------------------------------------------------------------------------


def die(msg: str) -> NoReturn:
    """Fail loud: message to stderr, exit 1."""
    raise SystemExit(f"error: {msg}")


def load_yaml(path: Path) -> Any:
    if not path.exists():
        die(f"{path} does not exist")
    return yaml.safe_load(path.read_text())


def save_yaml(path: Path, data: Any) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    tmp.replace(path)


def review_defaults() -> dict[str, Any]:
    return load_yaml(DEFAULTS_YAML)["review"]


@dataclass
class PickMeta:
    id: str
    format: str
    color: str
    status: str
    title: str
    why: str = ""

    def to_yaml(self) -> dict[str, Any]:
        return {"format": self.format, "color": self.color, "status": self.status,
                "title": self.title, "why": self.why}


@dataclass
class Ctx:
    """Everything a stage-1 script needs about one episode."""

    dir: Path
    data: dict[str, Any]
    cfg: dict[str, Any]
    words: list[dict[str, Any]]
    names: dict[str, str]  # speaker id -> display name
    unpublished: list[bool] = field(default_factory=list)  # per word; all False without rights-mask.yaml
    interj: list[bool] = field(default_factory=list)  # short other-speaker words folded inline (see find_interjections)
    elided: list[bool] = field(default_factory=list)  # words not shown in the doc (middle of long unpublished stretches)
    _keys: list[str] | None = field(default=None, repr=False)

    @property
    def yaml_path(self) -> Path:
        return self.dir / "episode.yaml"

    @property
    def review(self) -> dict[str, Any]:
        if self.data.get("review") is None:  # ingest writes `review: null` on a fresh episode
            self.data["review"] = {}
        return self.data["review"]

    @property
    def account(self) -> str:
        return self.review.get("account") or self.cfg["account"]

    def save(self) -> None:
        save_yaml(self.yaml_path, self.data)

    def search_keys(self) -> list[str]:
        if self._keys is None:
            self._keys = [search_key(w["w"]) for w in self.words]
        return self._keys

    def pick_meta(self) -> dict[str, PickMeta]:
        raw = self.review.get("picks") or {}
        return {pid: PickMeta(pid, v["format"], v["color"].upper(), v["status"], v["title"],
                              v.get("why", "")) for pid, v in raw.items()}

    def store_picks(self, model: "Model", published: list[dict[str, Any]]) -> None:
        """Persist every pick's metadata plus the internal details that are NOT shown in the doc."""
        self.review["picks"] = {pid: {**p.to_yaml(), **pick_details(self, model, pid, published)}
                                for pid, p in model.picks.items()}

    def doc_id(self) -> str:
        pd = self.review.get("pick_doc")
        if not pd:
            die(f"{self.yaml_path} has no review.pick_doc — run build_pick_doc.py first")
        return pd["id"]


def load_ctx(episode_dir: str | Path) -> Ctx:
    d = Path(episode_dir).expanduser().resolve()
    data = load_yaml(d / "episode.yaml")
    defaults = review_defaults()
    cfg = {**defaults, **{k: v for k, v in (data.get("review") or {}).items() if k in defaults}}
    tpath = d / ((data.get("transcript") or {}).get("json") or "transcript/transcript.json")
    words = json.loads(tpath.read_text())["words"]
    names = {s["id"]: s["name"] for s in data["speakers"]}
    unknown = sorted({w["speaker"] for w in words} - set(names))
    if unknown:
        die(f"transcript speakers {unknown} are not in episode.yaml speakers[]")
    unpub = unpublished_words(d, words)
    return Ctx(d, data, cfg, words, names, unpub, find_interjections(words), compute_elided(words, unpub))


def unpublished_words(episode_dir: Path, words: list[dict[str, Any]]) -> list[bool]:
    """True for words whose midpoint lies outside every rights-mask.yaml published span.

    No rights-mask.yaml -> everything is publishable (all False)."""
    path = episode_dir / "rights-mask.yaml"
    if not path.exists():
        return [False] * len(words)
    spans = sorted((float(a), float(b)) for a, b in load_yaml(path)["published_spans"])
    out: list[bool] = []
    k = 0
    for w in words:
        mid = (w["start"] + w["end"]) / 2
        while k < len(spans) and spans[k][1] < mid:
            k += 1
        out.append(not (k < len(spans) and spans[k][0] <= mid <= spans[k][1]))
    return out


def _flag_runs(flags: list[bool]) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    start = None
    for i, u in enumerate(flags + [False]):
        if u and start is None:
            start = i
        elif not u and start is not None:
            out.append((start, i - 1))
            start = None
    return out


def unpublished_stretches(ctx: Ctx) -> list[tuple[int, int]]:
    """Maximal inclusive word runs outside every published span."""
    return _flag_runs(ctx.unpublished)


ELIDE_MIN_S = 20.0
INTERJ_MAX_WORDS = 4
INTERJ_MAX_S = 1.5


def compute_elided(words: list[dict[str, Any]], unpublished: list[bool]) -> list[bool]:
    """Unpublished stretches longer than ELIDE_MIN_S keep only their first and last sentence."""
    elided = [False] * len(words)
    for a, b in _flag_runs(unpublished):
        if words[b]["end"] - words[a]["start"] <= ELIDE_MIN_S:
            continue
        first_end = next(k for k in range(a, b + 1) if k == b or ends_sentence(words[k]["w"]))
        terminators = [k for k in range(a, b) if ends_sentence(words[k]["w"])]
        last_start = terminators[-1] + 1 if terminators else a
        for k in range(first_end + 1, last_start):
            elided[k] = True
    return elided


def find_interjections(words: list[dict[str, Any]]) -> list[bool]:
    """Words of short (<= 4 words or < 1.5 s) runs by another speaker sandwiched inside a turn.

    They stay in time order and stay real transcript words; the doc renders them inline as
    `(Name: Yeah.)` instead of as paragraphs of their own."""
    runs: list[tuple[int, int, str]] = []
    for i, w in enumerate(words):
        if runs and runs[-1][2] == w["speaker"]:
            runs[-1] = (runs[-1][0], i, w["speaker"])
        else:
            runs.append((i, i, w["speaker"]))

    def short(r: tuple[int, int, str]) -> bool:
        return r[1] - r[0] + 1 <= INTERJ_MAX_WORDS or words[r[1]]["end"] - words[r[0]]["start"] < INTERJ_MAX_S

    flags = [False] * len(words)
    main: str | None = None
    k = 0
    while k < len(runs):
        if main is None or runs[k][2] == main:
            main = runs[k][2]
            k += 1
            continue
        j = k
        while j < len(runs) and runs[j][2] != main and short(runs[j]):
            j += 1
        if j > k and j < len(runs) and runs[j][2] == main:
            for a, b, _s in runs[k:j]:
                flags[a:b + 1] = [True] * (b - a + 1)
            k = j
        else:
            main = runs[k][2]
            k += 1
    return flags


def load_published(ctx: Ctx) -> list[dict[str, Any]]:
    """published-overlap.json shorts. start_word/end_word are INCLUSIVE word indices."""
    path = ctx.dir / "published-overlap.json"
    if not path.exists():
        helper = SKILL_DIR / "scripts" / "published_shorts.py"
        die(f"{path} is missing — run: uv run {helper} match {ctx.dir}")
    payload = json.loads(path.read_text())
    n = len(ctx.words)
    shorts = payload["shorts"]
    for s in shorts:
        if not (0 <= s["start_word"] <= s["end_word"] < n):
            die(f"{path}: short {s.get('video_id')!r} word range {s['start_word']}..{s['end_word']} "
                f"is outside the transcript (0..{n - 1}); end_word is inclusive")
    return shorts


# ---------------------------------------------------------------------------
# 2. clock formatting, words, paragraph plan
# ---------------------------------------------------------------------------


def fmt_clock(seconds: float, *, ceil: bool = False) -> str:
    total = int(seconds) if not ceil else int(-(-seconds // 1))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def fmt_dur(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def parse_clock(s: str) -> float:
    parts = [float(p) for p in s.strip().split(":")]
    if not 1 <= len(parts) <= 3:
        die(f"cannot parse time {s!r}; use seconds, mm:ss or h:mm:ss")
    out = 0.0
    for p in parts:
        out = out * 60 + p
    return out


_INVISIBLE = dict.fromkeys(map(ord, "​‌‍⁠﻿­"), None)
_TERMINATOR = re.compile(r"[.?!][\"')\]”’]*$")


def align_key(token: str) -> str:
    """Doc <-> transcript comparison key: NFKC, invisible characters dropped."""
    return unicodedata.normalize("NFKC", token).translate(_INVISIBLE)


def search_key(token: str) -> str:
    """Quote-matching key: lowercase letters/digits/apostrophes only."""
    t = unicodedata.normalize("NFKC", token).translate(_INVISIBLE).lower().replace("’", "'")
    return re.sub(r"[^\w']+", "", t)


def ends_sentence(token: str) -> bool:
    return bool(_TERMINATOR.search(token))


@dataclass
class Para:
    first: int
    last: int  # inclusive word indices (first/last are shown words)
    speaker: str
    start: float
    header: bool  # first shown paragraph of a turn: preceded by a speaker-header paragraph


def plan_paragraphs(words: list[dict[str, Any]], interj: list[bool], elided: list[bool]) -> list[Para]:
    """Turns (the main speaker's runs with short interjections folded in), each split into short
    paragraphs at sentence boundaries: ~20-30 s or 5 sentences. Elided words are not shown."""
    paras: list[Para] = []
    n = len(words)

    i = 0
    while i < n:
        main = words[i]["speaker"]
        j = i
        while j + 1 < n and (interj[j + 1] or words[j + 1]["speaker"] == main):
            j += 1
        sentences: list[tuple[int, int]] = []
        s_ = i
        for k in range(i, j + 1):
            if k == j or (ends_sentence(words[k]["w"]) and not interj[k] and not interj[k + 1]):
                sentences.append((s_, k))
                s_ = k + 1
        turn: list[tuple[int, int]] = []  # paragraph word ranges
        cur_first, count = sentences[0][0], 0
        for sf, sl in sentences:
            count += 1
            dur = words[sl]["end"] - words[cur_first]["start"]
            if dur >= PARA_MAX_S or count >= PARA_MAX_SENTENCES or (dur >= PARA_MIN_S and count >= 3):
                turn.append((cur_first, sl))
                cur_first, count = sl + 1, 0
        if count:
            turn.append((cur_first, sentences[-1][1]))
        first_in_turn = True
        for a, b in turn:
            present = [k for k in range(a, b + 1) if not elided[k]]
            if present:
                paras.append(Para(present[0], present[-1], words[present[0]]["speaker"],
                                  words[present[0]]["start"], first_in_turn))
                first_in_turn = False
        i = j + 1
    return paras


def header_text(ctx: Ctx, p: Para) -> str:
    return f"[{fmt_clock(p.start)}] {ctx.names[p.speaker]}"


def cont_prefix(p: Para) -> str:
    return f"{fmt_clock(p.start)} "


# ---------------------------------------------------------------------------
# 3. pick model
# ---------------------------------------------------------------------------


@dataclass
class Model:
    """Desired / live state: which pick owns each word, and which words are cut."""

    owner: list[str | None]
    cut: list[bool]
    picks: dict[str, PickMeta]

    def copy(self) -> "Model":
        return Model(list(self.owner), list(self.cut), {k: PickMeta(**vars(v)) for k, v in self.picks.items()})

    def color_of(self, pid: str | None) -> str | None:
        return self.picks[pid].color if pid else None

    def owned(self, pid: str) -> list[int]:
        return [i for i, o in enumerate(self.owner) if o == pid]

    def regions(self, pid: str) -> list[tuple[int, int]]:
        out: list[tuple[int, int]] = []
        start = None
        for i, o in enumerate(self.owner + [None]):
            if o == pid and start is None:
                start = i
            elif o != pid and start is not None:
                out.append((start, i - 1))
                start = None
        return out

    def same_as(self, other: "Model") -> bool:
        return self.owner == other.owner and self.cut == other.cut


def pick_sort_key(pid: str) -> tuple[int, int]:
    return (pid[0] != "S", int(pid[1:]))


def next_free_id(picks: dict[str, PickMeta], fmt: str) -> str:
    prefix = FORMATS[fmt]
    nums = [int(p[1:]) for p in picks if p[0] == prefix]
    return f"{prefix}{max(nums, default=0) + 1}"


@dataclass
class Seg:
    first: int
    last: int
    speaker: str


def kept_segments(words: list[dict[str, Any]], model: Model, pid: str) -> list[Seg]:
    """Kept (owned, not cut) word runs, split at index gaps and speaker changes."""
    segs: list[Seg] = []
    for i, o in enumerate(model.owner):
        if o != pid or model.cut[i]:
            continue
        sp = words[i]["speaker"]
        if segs and segs[-1].last == i - 1 and segs[-1].speaker == sp:
            segs[-1].last = i
        else:
            segs.append(Seg(i, i, sp))
    return segs


def kept_duration(words: list[dict[str, Any]], segs: list[Seg]) -> float:
    return sum(words[s.last]["end"] - words[s.first]["start"] for s in segs)


def ends_on(words: list[dict[str, Any]], model: Model, pid: str) -> str:
    kept = [i for i in model.owned(pid) if not model.cut[i]]
    return " ".join(words[i]["w"] for i in kept[-ENDS_ON_WORDS:])


def validate_model(ctx: Ctx, model: Model) -> None:
    """The §3 rules, applied to a whole model. Fails loud naming the pick."""
    for pid, meta in model.picks.items():
        if meta.format not in FORMATS:
            die(f"pick {pid}: unknown format {meta.format!r} (short|clip)")
        if pid[0] != FORMATS[meta.format]:
            die(f"pick {pid}: id prefix does not match format {meta.format!r}")
        if meta.status not in STATUSES:
            die(f"pick {pid}: unknown status {meta.status!r} ({'|'.join(STATUSES)})")
        regions = model.regions(pid)
        if not regions:
            die(f"pick {pid} owns no words")
        for a, b in regions:
            for edge in (a, b):
                if model.cut[edge]:
                    die(f"pick {pid}: region {a}..{b} has its edge word #{edge} "
                        f"({ctx.words[edge]['w']!r}) cut — move the boundary with `range` instead")
        outside = [i for i in model.owned(pid) if ctx.unpublished[i]]
        if outside:
            die(f"pick {pid} leaves the published spans of rights-mask.yaml: {len(outside)} word(s) from "
                f"{fmt_clock(ctx.words[outside[0]]['start'])} ({ctx.words[outside[0]]['w']!r}) were never "
                f"published — material cut before publication is never used")
        segs = kept_segments(ctx.words, model, pid)
        if not segs:
            die(f"pick {pid}: every word is cut")
        if meta.format == "short" and meta.status != "dropped":
            dur = kept_duration(ctx.words, segs)
            if dur >= SHORT_LIMIT_S:
                die(f"short {pid}: kept duration {fmt_dur(dur)} ({dur:.1f}s) is not under "
                    f"{SHORT_LIMIT_S:.0f}s — cut more, trim a boundary, or make it a clip")
    colors = Counter(m.color for m in model.picks.values())
    reused = [c for c, n in colors.items() if n > 1]
    if reused:
        die(f"pick colours reused within one doc: {reused}")


# ---------------------------------------------------------------------------
# 4. label / status / marker text and the desired structure
# ---------------------------------------------------------------------------


def overlapping_published(model: Model, pid: str, published: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s for s in published
            if any(model.owner[i] == pid for i in range(s["start_word"], s["end_word"] + 1))]


def pick_ranges_text(ctx: Ctx, regions: list[tuple[int, int]]) -> str:
    w = ctx.words
    return ", ".join(f"{fmt_clock(w[a]['start'])}–{fmt_clock(w[b]['end'], ceil=True)}" for a, b in regions)


def status_text(ctx: Ctx, model: Model, pid: str) -> str:
    m = model.picks[pid]
    dur = fmt_dur(kept_duration(ctx.words, kept_segments(ctx.words, model, pid)))
    return f"{pid} · {FORMAT_NAME[m.format]} · {dur} · {m.status.upper()} — {m.title}"


def label_text(ctx: Ctx, model: Model, pid: str, region: int, published: list[dict[str, Any]]) -> str:
    """Short ▶ label; the pick's internal details live only in episode.yaml review.picks (`doc_ops.py show`)."""
    if region > 1:
        return f"▶ {pid} · region {region}"
    m = model.picks[pid]
    dur = fmt_dur(kept_duration(ctx.words, kept_segments(ctx.words, model, pid)))
    warn = " · ⚠ published" if overlapping_published(model, pid, published) else ""
    return f"▶ {pid} · {FORMAT_LABEL[m.format]} · {dur}{warn}"


def pick_details(ctx: Ctx, model: Model, pid: str, published: list[dict[str, Any]]) -> dict[str, Any]:
    """What `doc_ops.py show` prints: everything about a pick that the doc itself no longer carries."""
    dur = kept_duration(ctx.words, kept_segments(ctx.words, model, pid))
    over = [{"title": x["title"], "url": x["url"]} for x in overlapping_published(model, pid, published)]
    return {"duration": fmt_dur(dur), "duration_s": round(dur, 1),
            "regions": pick_ranges_text(ctx, model.regions(pid)),
            "ends_on": ends_on(ctx.words, model, pid), "overlap": over}


def marker_text(short: dict[str, Any]) -> str:
    return f'· published as "{short["title"]}"'


def unpublished_marker_text(ctx: Ctx, a: int, b: int) -> str:
    dur = round(ctx.words[b]["end"] - ctx.words[a]["start"])
    return f"· not published ({pick_ranges_text(ctx, [(a, b)])}, {dur}s)"


@dataclass(frozen=True)
class Style:
    bg: str | None = None
    fg: str | None = None
    strike: bool = False
    bold: bool = False
    italic: bool = False
    size: float | None = field(default=None, compare=False)
    link: str | None = field(default=None, compare=False)

    def sig(self) -> tuple[Any, ...]:
        return (self.bg, (self.fg or BLACK).upper() if self.fg else BLACK, self.strike, self.bold, self.italic)


@dataclass(frozen=True)
class Item:
    key: tuple[Any, ...]
    kind: str  # status | label | marker
    text: str
    style: Style


def word_style(ctx: Ctx, model: Model, i: int) -> Style:
    o = model.owner[i]
    size = 9 if ctx.interj[i] else None
    if o:
        return Style(bg=model.color_of(o), fg=PICK_FG, strike=model.cut[i], size=size)
    grey = ctx.cfg["grey"].upper()
    if ctx.unpublished[i]:
        return Style(fg=grey, strike=True, italic=True, size=size)
    return Style(fg=grey, size=size)


def desired_structure(ctx: Ctx, model: Model, word_anchor: list[int],
                      published: list[dict[str, Any]]) -> tuple[list[Item], dict[int, list[Item]]]:
    """(status items in display order, {anchor paragraph index: label/marker items placed above it})."""
    status: list[Item] = []
    gaps: dict[int, list[tuple[tuple[int, int, int], Item]]] = {}
    for pid in sorted(model.picks, key=pick_sort_key):
        color = model.picks[pid].color
        status.append(Item(("status", pid), "status", status_text(ctx, model, pid),
                           Style(bg=color, fg=PICK_FG, size=11)))
        for r, (a, _b) in enumerate(model.regions(pid), start=1):
            item = Item(("label", pid, r), "label", label_text(ctx, model, pid, r, published),
                        Style(bg=color, fg=PICK_FG, bold=True, size=11))
            gaps.setdefault(word_anchor[a], []).append(((1, a, 0), item))
    grey = ctx.cfg["grey"].upper()
    for n, s in enumerate(published):
        if any(model.owner[i] for i in range(s["start_word"], s["end_word"] + 1)):
            continue
        item = Item(("marker", marker_text(s), 0), "marker", marker_text(s), Style(fg=grey, size=9))
        gaps.setdefault(word_anchor[s["start_word"]], []).append(((0, s["start_word"], n), item))
    for a, b in unpublished_stretches(ctx):
        text = unpublished_marker_text(ctx, a, b)
        item = Item(("marker", text, 0), "marker", text, Style(fg=grey, size=9))
        gaps.setdefault(word_anchor[a], []).append(((0, a, 0), item))
    ordered: dict[int, list[Item]] = {}
    for p, items in gaps.items():
        occ: Counter[str] = Counter()
        row: list[Item] = []
        for _k, it in sorted(items, key=lambda x: x[0]):
            if it.kind == "marker":
                it = Item(("marker", it.text, occ[it.text]), it.kind, it.text, it.style)
                occ[it.text] += 1
            row.append(it)
        ordered[p] = row
    return status, ordered


# ---------------------------------------------------------------------------
# 5. Docs-API parsing, alignment, read-back
# ---------------------------------------------------------------------------


def _hex(color: dict[str, Any] | None) -> str | None:
    if not color or "color" not in color:
        return None
    rgb = color["color"].get("rgbColor", {})
    return "#{:02X}{:02X}{:02X}".format(*(round(rgb.get(c, 0) * 255) for c in ("red", "green", "blue")))


def style_from_api(ts: dict[str, Any]) -> Style:
    return Style(bg=_hex(ts.get("backgroundColor")), fg=_hex(ts.get("foregroundColor")) or BLACK,
                 strike=bool(ts.get("strikethrough")), bold=bool(ts.get("bold")),
                 italic=bool(ts.get("italic")), link=(ts.get("link") or {}).get("url"))


def _width(ch: str) -> int:
    return 2 if ord(ch) > 0xFFFF else 1


@dataclass
class DocPara:
    start: int
    end: int  # exclusive, includes the trailing newline
    text: str  # without the trailing newline
    idx: list[int]  # Docs index of every char in text
    styles: list[Style]
    kind: str = "other"
    named: str = "NORMAL_TEXT"
    above: float = 0.0
    below: float = 0.0
    line: float = 100.0

    def rng(self, c0: int, c1: int) -> tuple[int, int]:
        return self.idx[c0], self.idx[c1 - 1] + _width(self.text[c1 - 1])

    @property
    def text_end(self) -> int:
        return self.idx[-1] + _width(self.text[-1]) if self.text else self.start


MARKER_PREFIXES = ("· published as", "· not published")
STATUS_RE = re.compile(r"^([SC]\d+) · (?:SHORT|CLIP) ")
LABEL_RE = re.compile(r"^▶ ([SC]\d+) · (?:region (\d+)|(?:SHORT|CLIP) )")
CONT_RE = re.compile(r"^(?:\d+:)?\d{1,2}:\d{2} ")


def header_re(ctx: Ctx) -> re.Pattern[str]:
    names = "|".join(re.escape(n) for n in sorted(set(ctx.names.values()), key=len, reverse=True))
    return re.compile(rf"^\[(?:\d+:)?\d{{1,2}}:\d{{2}}\] (?:{names})$")


def classify(text: str, hre: re.Pattern[str], seen_header: bool) -> str:
    if text.startswith("▶ "):
        return "label"
    if text.startswith(MARKER_PREFIXES):
        return "marker"
    if STATUS_RE.match(text):
        return "status"
    if hre.match(text):
        return "header"
    if seen_header and text.strip():
        return "transcript"
    return "other"


def parse_doc(doc: dict[str, Any], ctx: Ctx) -> list[DocPara]:
    hre = header_re(ctx)
    paras: list[DocPara] = []
    seen_header = False
    for el in doc["body"]["content"]:
        p = el.get("paragraph")
        if not p:
            continue
        chars: list[str] = []
        idx: list[int] = []
        styles: list[Style] = []
        for e in p["elements"]:
            pos = e.get("startIndex", 0)
            tr = e.get("textRun")
            if not tr:
                chars.append("\x00")
                idx.append(pos)
                styles.append(Style())
                continue
            st = style_from_api(tr.get("textStyle", {}))
            for ch in tr["content"]:
                chars.append(ch)
                idx.append(pos)
                styles.append(st)
                pos += _width(ch)
        if chars and chars[-1] == "\n":
            chars.pop(), idx.pop(), styles.pop()
        text = "".join(chars)
        kind = classify(text, hre, seen_header)
        seen_header = seen_header or kind == "header"
        ps = p.get("paragraphStyle", {})
        paras.append(DocPara(el.get("startIndex", 0), el["endIndex"], text, idx, styles, kind,
                             ps.get("namedStyleType", "NORMAL_TEXT"),
                             ps.get("spaceAbove", {}).get("magnitude", 0.0),
                             ps.get("spaceBelow", {}).get("magnitude", 0.0), ps.get("lineSpacing", 100.0)))
    return paras


@dataclass
class Alignment:
    paras: list[DocPara]
    word_para: list[int]  # word -> index into paras (elided words: the next shown word's paragraph)
    word_a: list[int]  # word -> char offset where the word starts in its paragraph text (-1: elided)
    word_b: list[int]  # ... where it ends (exclusive)
    word_s: list[int]  # ... where its style span starts (an interjection's `(Name: ` opener belongs to it)
    para_words: dict[int, list[int]]  # transcript para index -> its shown word indices, in order
    anchor_of: dict[int, int]  # transcript para index -> paragraph that ▶ labels/markers go above
    # (the speaker header for the first paragraph of a turn, else the paragraph itself)


def align_doc(paras: list[DocPara], ctx: Ctx) -> Alignment:
    opener = re.compile(r"\((?:" + "|".join(re.escape(n) for n in sorted(set(ctx.names.values()), key=len, reverse=True)) + r"):")
    shown = [i for i, e in enumerate(ctx.elided) if not e]
    keys = [align_key(ctx.words[i]["w"]) for i in shown]
    n = len(ctx.words)
    word_para, word_a, word_b, word_s = [-1] * n, [-1] * n, [-1] * n, [-1] * n
    para_words: dict[int, list[int]] = {}
    anchor_of: dict[int, int] = {}
    ptr = 0
    after_header, last_header = False, -1
    for pi, p in enumerate(paras):
        if p.kind == "header":
            if after_header:
                die(f"speaker header {paras[last_header].text!r} has no text under it")
            after_header, last_header = True, pi
            continue
        if p.kind != "transcript":
            continue
        if after_header:
            plen, anchor_of[pi], after_header = 0, last_header, False
        else:
            m0 = CONT_RE.match(p.text)
            if not m0:
                die(f"doc paragraph {p.text[:40]!r} has no leading timestamp and no speaker header above it")
            plen, anchor_of[pi] = m0.end(), pi
        mine: list[int] = []
        in_int: str | None = None
        opener_at = -1
        for m in re.finditer(r"\S+", p.text[plen:]):
            raw = m.group()
            tok = align_key(raw)
            if ptr >= len(keys):
                die(f"doc has more transcript words than transcript.json ({len(shown)} shown) — "
                    f"extra text in paragraph {p.text[:40]!r}")
            if tok == keys[ptr] or (in_int and tok == keys[ptr] + ")"):
                closing = bool(in_int) and tok != keys[ptr]
            elif raw == "\u2026":
                continue  # elision mark
            elif not in_int and opener.fullmatch(tok):
                in_int, opener_at = tok[1:-1], plen + m.start()
                if ctx.names[ctx.words[shown[ptr]]["speaker"]] != in_int:
                    die(f"interjection {raw!r} in paragraph {p.text[:30]!r} does not match the speaker of "
                        f"transcript word #{shown[ptr]}")
                continue
            else:
                die(f"doc text no longer aligns to the transcript at paragraph {p.text[:30]!r}: "
                    f"doc has {raw!r} where transcript word #{shown[ptr]} is {ctx.words[shown[ptr]]['w']!r} "
                    f"(somebody edited the words)")
            w = shown[ptr]
            word_para[w] = pi
            word_a[w] = plen + m.start()
            word_b[w] = plen + m.end() - (1 if closing else 0)
            word_s[w] = opener_at if opener_at >= 0 else word_a[w]
            opener_at = -1
            if closing:
                in_int = None
            mine.append(w)
            ptr += 1
        if in_int:
            die(f"interjection ({in_int}: ...) in paragraph {p.text[:30]!r} is not closed")
        if not mine:
            die(f"doc transcript paragraph {p.text[:30]!r} contains no words")
        para_words[pi] = mine
    if ptr != len(keys):
        die(f"doc transcript ends at shown word #{ptr} but transcript.json has {len(keys)} shown words "
            f"(text deleted from the doc)")
    last = -1
    for w in range(n - 1, -1, -1):  # elided words point at the next shown word's paragraph
        if word_para[w] >= 0:
            last = word_para[w]
        else:
            word_para[w] = last
    prev = 0
    for w in range(n):
        if word_para[w] < 0:
            word_para[w] = prev
        prev = word_para[w]
    return Alignment(paras, word_para, word_a, word_b, word_s, para_words, anchor_of)


def word_span_end(al: Alignment, i: int, nxt: int | None) -> int:
    """Char offset where word i's style span ends: the next shown word's span start, or paragraph end."""
    return al.word_s[nxt] if nxt is not None else len(al.paras[al.word_para[i]].text)


def read_model(ctx: Ctx, al: Alignment) -> Model:
    meta = ctx.pick_meta()
    by_color = {m.color: pid for pid, m in meta.items()}
    owner: list[str | None] = []
    cut: list[bool] = []
    unknown: Counter[str] = Counter()
    for i in range(len(ctx.words)):
        if ctx.elided[i]:
            owner.append(None)
            cut.append(False)
            continue
        p = al.paras[al.word_para[i]]
        a, b = al.word_a[i], al.word_b[i]
        st = p.styles[a]
        if any((s.bg, s.strike) != (st.bg, st.strike) for s in p.styles[a:b]):
            die(f"word #{i} ({ctx.words[i]['w']!r}) near {fmt_clock(ctx.words[i]['start'])} is partly "
                f"highlighted/struck through — re-select the whole word")
        if st.bg is None:
            owner.append(None)
        elif st.bg in by_color:
            owner.append(by_color[st.bg])
        else:
            unknown[st.bg] += 1
            owner.append(None)
        cut.append(st.strike and st.bg is not None)
    if unknown:
        die(f"doc has highlight colour(s) {dict(unknown)} that are not in review.picks "
            f"({sorted(by_color)}) — remove those highlights in the doc")
    missing = [pid for pid, m in meta.items() if not m.why]
    if missing:
        die(f"episode.yaml review.picks has no 'why' for {missing}")
    return Model(owner, cut, meta)


# ---------------------------------------------------------------------------
# 6. edit planning and application
# ---------------------------------------------------------------------------

ORDER_UPDATE, ORDER_INSERT_GAP, ORDER_INSERT_STATUS = 0, 1, 2


@dataclass
class Edit:
    anchor: int  # Docs index the edit touches first; edits apply in descending anchor order
    order: int
    requests: list[dict[str, Any]]


def _rgb(hexstr: str) -> dict[str, Any]:
    r, g, b = (int(hexstr[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return {"color": {"rgbColor": {"red": r, "green": g, "blue": b}}}


def style_request(a: int, b: int, st: Style) -> dict[str, Any]:
    ts: dict[str, Any] = {"foregroundColor": _rgb(st.fg or BLACK), "strikethrough": st.strike, "bold": st.bold,
                                "italic": st.italic}
    fields = ["backgroundColor", "foregroundColor", "strikethrough", "bold", "italic"]
    if st.bg:
        ts["backgroundColor"] = _rgb(st.bg)
    if st.size:
        ts["fontSize"] = {"magnitude": st.size, "unit": "PT"}
        fields.append("fontSize")
    return {"updateTextStyle": {"range": {"startIndex": a, "endIndex": b}, "textStyle": ts,
                                "fields": ",".join(fields)}}


def plan_word_styles(ctx: Ctx, al: Alignment, model: Model) -> list[Edit]:
    edits: list[Edit] = []
    for pi, ws in al.para_words.items():
        p = al.paras[pi]
        want: dict[int, Style] = {}
        for k, i in enumerate(ws):
            st = word_style(ctx, model, i)
            nxt = ws[k + 1] if k + 1 < len(ws) else None
            for c in range(al.word_s[i], word_span_end(al, i, nxt)):
                want[c] = st
        run: tuple[int, int, Style] | None = None
        for c in sorted(want):
            wanted = want[c]
            if p.styles[c].sig() == wanted.sig():
                if run:
                    edits.append(_style_edit(p, run))
                    run = None
            elif run and run[1] == c and run[2].sig() == wanted.sig():
                run = (run[0], c + 1, run[2])
            else:
                if run:
                    edits.append(_style_edit(p, run))
                run = (c, c + 1, wanted)
        if run:
            edits.append(_style_edit(p, run))
    return edits


def _style_edit(p: DocPara, run: tuple[int, int, Style]) -> Edit:
    a, b = p.rng(run[0], run[1])
    return Edit(a, ORDER_UPDATE, [style_request(a, b, run[2])])


@dataclass
class LiveItem:
    key: tuple[Any, ...]
    para: DocPara


def _live_key(p: DocPara, occurrence: Counter[str]) -> tuple[Any, ...]:
    if p.kind == "status":
        return ("status", STATUS_RE.match(p.text).group(1))  # type: ignore[union-attr]
    if p.kind == "label":
        m = LABEL_RE.match(p.text)
        if m:
            return ("label", m.group(1), int(m.group(2) or 1))
        return ("label", "?", p.text)
    n = occurrence[p.text]
    occurrence[p.text] += 1
    return ("marker", p.text, n)


def _no_links(p: DocPara) -> bool:
    return all(st.link is None for st in p.styles)


def pstyle_request(a: int, b: int, named: str | None, spacing: tuple[float, float] | None) -> dict[str, Any]:
    ps: dict[str, Any] = {}
    fields: list[str] = []
    if named:
        ps["namedStyleType"] = named
        fields.append("namedStyleType")
    if spacing:
        ps.update({"spaceAbove": {"magnitude": spacing[0], "unit": "PT"},
                   "spaceBelow": {"magnitude": spacing[1], "unit": "PT"}, "lineSpacing": LINE_SPACING})
        fields += ["spaceAbove", "spaceBelow", "lineSpacing"]
    return {"updateParagraphStyle": {"range": {"startIndex": a, "endIndex": b}, "paragraphStyle": ps,
                                     "fields": ",".join(fields)}}


def _clear_link_request(a: int, b: int) -> dict[str, Any]:
    return {"updateTextStyle": {"range": {"startIndex": a, "endIndex": b}, "textStyle": {}, "fields": "link"}}


def _text_requests(start: int, text: str, d: Item) -> list[dict[str, Any]]:
    """Requests that style `text` freshly inserted at `start` (link first so explicit colours win)."""
    n = _utf16_len(text)
    reqs: list[dict[str, Any]] = []
    if d.kind in ("status", "label"):
        reqs.append(_clear_link_request(start, start + n))  # inserted text may inherit a neighbouring link
    reqs.append(style_request(start, start + n, d.style))
    return reqs


def _diff_items(live: list[LiveItem], desired: list[Item], end_anchor: int, insert_order: int,
                deleted: set[int]) -> list[Edit]:
    edits: list[Edit] = []
    live_by_key = {li.key: li for li in live}
    desired_keys = {d.key for d in desired}
    for li in live:
        if li.key not in desired_keys:
            deleted.add(li.para.start)
            edits.append(Edit(li.para.start, ORDER_UPDATE, [
                {"deleteContentRange": {"range": {"startIndex": li.para.start, "endIndex": li.para.end}}}]))
    for d in desired:
        li = live_by_key.get(d.key)
        if li is None:
            continue
        p = li.para
        if p.text != d.text:
            reqs: list[dict[str, Any]] = []
            if p.text:
                reqs.append({"deleteContentRange": {"range": {"startIndex": p.start, "endIndex": p.text_end}}})
            reqs.append({"insertText": {"location": {"index": p.start}, "text": d.text}})
            reqs += _text_requests(p.start, d.text, d)
            edits.append(Edit(p.start, ORDER_UPDATE, reqs))
        else:
            reqs = []
            if any(s.sig() != d.style.sig() for s in p.styles):
                reqs.append(style_request(p.start, p.text_end, d.style))
            if d.kind in ("status", "label") and not _no_links(p):
                reqs.append(_clear_link_request(p.start, p.text_end))
                reqs.append(style_request(p.start, p.text_end, d.style))
            if reqs:
                edits.append(Edit(p.start, ORDER_UPDATE, reqs))
    # insertions: unmatched desired items go before the next matched live item (or at end_anchor)
    pending: list[Item] = []
    for d in desired:
        li = live_by_key.get(d.key)
        if li is None:
            pending.append(d)
            continue
        if pending:
            edits.append(_insert_edit(pending, li.para.start, insert_order))
            pending = []
    if pending:
        edits.append(_insert_edit(pending, end_anchor, insert_order))
    return edits


def _utf16_len(s: str) -> int:
    return len(s.encode("utf-16-le")) // 2


def _insert_edit(items: list[Item], anchor: int, order: int) -> Edit:
    text = "".join(it.text + "\n" for it in items)
    reqs: list[dict[str, Any]] = [{"insertText": {"location": {"index": anchor}, "text": text}}]
    pos = anchor
    for it in items:
        n = _utf16_len(it.text)
        spacing = SPACING.get(it.kind)
        if spacing:
            reqs.append(pstyle_request(pos, pos + n + 1, "NORMAL_TEXT", spacing))
        reqs += _text_requests(pos, it.text, it)
        pos += n + 1
    return Edit(anchor, order, reqs)


def plan_structure(ctx: Ctx, al: Alignment, status: list[Item], gaps: dict[int, list[Item]],
                   deleted: set[int]) -> list[Edit]:
    live_status: list[LiveItem] = []
    live_gaps: dict[int, list[LiveItem]] = {}
    pending: list[LiveItem] = []
    occ: Counter[str] = Counter()
    for pi, p in enumerate(al.paras):
        if p.kind == "status":
            live_status.append(LiveItem(_live_key(p, occ), p))
        elif p.kind in ("label", "marker"):
            pending.append(LiveItem(_live_key(p, occ), p))
        elif p.kind in ("transcript", "header"):
            if pending:
                live_gaps[pi] = pending
            pending = []
            occ = Counter()
    if pending:
        die(f"unexpected ▶ label / published marker after the end of the transcript: {pending[0].para.text[:50]!r}")
    if not live_status:
        die("the doc has no status lines (paragraphs like 'S1 · SHORT · 1:45 · PROPOSED — …') — was it edited?")
    edits = _diff_items(live_status, status, live_status[-1].para.end, ORDER_INSERT_STATUS, deleted)
    for pi in sorted(set(live_gaps) | set(gaps)):
        edits += _diff_items(live_gaps.get(pi, []), gaps.get(pi, []), al.paras[pi].start, ORDER_INSERT_GAP, deleted)
    return edits


def plan_para_styles(al: Alignment, deleted: set[int]) -> list[Edit]:
    edits: list[Edit] = []
    for p in al.paras:
        want = SPACING.get(p.kind)
        if not want or p.start in deleted:
            continue
        if abs(p.above - want[0]) > 0.01 or abs(p.below - want[1]) > 0.01 or abs(p.line - LINE_SPACING) > 0.01:
            edits.append(Edit(p.start, ORDER_UPDATE, [pstyle_request(p.start, p.start + 1, None, want)]))
    return edits


def plan_all(ctx: Ctx, paras: list[DocPara], model: Model, published: list[dict[str, Any]]) -> tuple[Alignment, list[Edit]]:
    al = align_doc(paras, ctx)
    word_anchor = [al.anchor_of[pi] for pi in al.word_para]
    status, gaps = desired_structure(ctx, model, word_anchor, published)
    deleted: set[int] = set()
    edits = plan_word_styles(ctx, al, model) + plan_structure(ctx, al, status, gaps, deleted)
    return al, edits + plan_para_styles(al, deleted)


def flatten(edits: list[Edit]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for e in sorted(edits, key=lambda e: (-e.anchor, e.order)):
        out += e.requests
    return out


def apply_edits(g: "DocsBackend", doc_id: str, edits: list[Edit]) -> int:
    reqs = flatten(edits)
    for k in range(0, len(reqs), BATCH_CHUNK):
        g.batch_update(doc_id, reqs[k:k + BATCH_CHUNK])
    return len(reqs)


class DocsBackend:
    """Interface sync() needs: implemented by `Google` (real) and by the offline emulator."""

    def get_doc(self, doc_id: str) -> dict[str, Any]: ...
    def batch_update(self, doc_id: str, requests: list[dict[str, Any]]) -> None: ...


def sync(ctx: Ctx, g: DocsBackend, doc_id: str, published: list[dict[str, Any]],
         desired: Model | Callable[[Model], Model], commit: Callable[[Model], None] | None = None) -> int:
    """Bring the pick doc to the desired model IN PLACE, then read back and verify.

    `desired` is a Model (build) or a function from the live-read Model to the new one (edit).
    `commit(model)` runs after validation and before the first Docs request.
    Returns the number of Docs requests applied.
    """
    paras = parse_doc(g.get_doc(doc_id), ctx)
    if callable(desired):
        live = read_model(ctx, align_doc(paras, ctx))
        model = desired(live)
    else:
        model = desired
    validate_model(ctx, model)
    if commit:
        commit(model)  # persist episode.yaml picks now: the verify pass below reads them
    _al, edits = plan_all(ctx, paras, model, published)
    n = apply_edits(g, doc_id, edits)
    logger.info("pick doc: {} docs request(s) in {} edit(s)", n, len(edits))
    paras2 = parse_doc(g.get_doc(doc_id), ctx)
    al2, leftover = plan_all(ctx, paras2, model, published)
    if leftover:
        sample = leftover[0].requests[0]
        die(f"readback mismatch: {len(leftover)} edit(s) still pending after apply "
            f"(first: {json.dumps(sample)[:300]}) — the doc did not take the change as planned")
    if not read_model(ctx, al2).same_as(model):
        die("readback mismatch: colours/strikethrough in the doc differ from the intended state")
    return n


# ---------------------------------------------------------------------------
# 7. Google auth + Drive/Docs client
# ---------------------------------------------------------------------------

SCOPES = ["https://www.googleapis.com/auth/documents", "https://www.googleapis.com/auth/drive"]
TOKEN_DIR = Path.home() / ".config" / "produce-shorts"
GOG_DIRS = [Path.home() / "Library" / "Application Support" / "gogcli", Path.home() / ".config" / "gogcli"]
COMMENT_FIELDS = ("nextPageToken,comments(id,content,quotedFileContent,resolved,createdTime,"
                  "author(displayName,emailAddress),replies(*))")


def token_path(account: str) -> Path:
    return TOKEN_DIR / f"token-{account}.json"


def reauth_hint(account: str) -> str:
    return (f"gog auth add {account} --services docs,drive --force-consent   "
            f"(interactive browser consent as {account}); then re-run — the token cache refreshes itself")


def export_token(account: str) -> Path:
    path = token_path(account)
    TOKEN_DIR.mkdir(parents=True, exist_ok=True)
    TOKEN_DIR.chmod(0o700)
    cmd = ["gog", "auth", "tokens", "export", account, "--out", str(path), "--overwrite", "--no-input"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        die(f"could not export the Google token for {account} from gog ({proc.stderr.strip()[:200]}). "
            f"Run this yourself, then retry:  {' '.join(cmd)}  — or authorize first: {reauth_hint(account)}")
    path.chmod(0o600)
    return path


def _client_secrets(client: str) -> dict[str, str]:
    name = "credentials.json" if client in ("", "default") else f"credentials-{client}.json"
    for d in GOG_DIRS:
        if (d / name).exists():
            raw = json.loads((d / name).read_text())
            return {"client_id": raw["client_id"], "client_secret": raw["client_secret"]}
    die(f"gog OAuth client file {name} not found in {[str(d) for d in GOG_DIRS]}")


def credentials(account: str):
    from google.auth.exceptions import RefreshError
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    def build(path: Path) -> Credentials:
        tok = json.loads(path.read_text())
        sec = _client_secrets(tok.get("client", "default"))
        return Credentials(None, refresh_token=tok["refresh_token"], token_uri="https://oauth2.googleapis.com/token",
                           scopes=SCOPES, **sec)

    fresh = not token_path(account).exists()
    path = export_token(account) if fresh else token_path(account)
    creds = build(path)
    try:
        creds.refresh(Request())
    except RefreshError as exc:
        if fresh:
            die(f"Google refused the refresh token gog holds for {account} ({exc.args[0]}). The grant was revoked "
                f"or expired (OAuth apps in 'Testing' mode expire refresh tokens after 7 days). "
                f"Run: {reauth_hint(account)}")
        logger.warning("cached token for {} was refused; re-exporting from gog once", account)
        creds = build(export_token(account))
        try:
            creds.refresh(Request())
        except RefreshError as exc2:
            die(f"Google refused the refresh token gog holds for {account} ({exc2.args[0]}). The grant was "
                f"revoked or expired (OAuth apps in 'Testing' mode expire refresh tokens after 7 days). "
                f"Run: {reauth_hint(account)}")
    return creds


class Google(DocsBackend):
    def __init__(self, account: str):
        from googleapiclient.discovery import build

        creds = credentials(account)
        self.account = account
        self.docs = build("docs", "v1", credentials=creds, cache_discovery=False)
        self.drive = build("drive", "v3", credentials=creds, cache_discovery=False)

    # -- docs
    def get_doc(self, doc_id: str) -> dict[str, Any]:
        return self.docs.documents().get(documentId=doc_id).execute()

    def batch_update(self, doc_id: str, requests: list[dict[str, Any]]) -> None:
        if requests:
            self.docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    # -- drive files
    def find_or_create_folder(self, name: str, parent: str | None = None) -> str:
        esc = name.replace("\\", "\\\\").replace("'", "\\'")
        q = (f"name = '{esc}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false "
             f"and '{parent or 'root'}' in parents")
        found = self.drive.files().list(q=q, fields="files(id,name)", spaces="drive").execute()["files"]
        if len(found) > 1:
            die(f"Drive has {len(found)} folders named {name!r} under {'root' if not parent else parent}; "
                f"delete the duplicates so the target is unambiguous")
        if found:
            return found[0]["id"]
        body: dict[str, Any] = {"name": name, "mimeType": "application/vnd.google-apps.folder"}
        if parent:
            body["parents"] = [parent]
        return self.drive.files().create(body=body, fields="id").execute()["id"]

    def upload_html_as_doc(self, html: str, title: str, folder_id: str) -> dict[str, str]:
        from googleapiclient.http import MediaIoBaseUpload

        media = MediaIoBaseUpload(io.BytesIO(html.encode()), mimetype="text/html", resumable=False)
        body = {"name": title, "mimeType": "application/vnd.google-apps.document", "parents": [folder_id]}
        f = self.drive.files().create(body=body, media_body=media, fields="id,webViewLink").execute()
        return {"id": f["id"], "url": f["webViewLink"]}

    # -- comments
    def list_comments(self, doc_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        token = None
        while True:
            r = self.drive.comments().list(fileId=doc_id, fields=COMMENT_FIELDS, includeDeleted=False,
                                           pageSize=100, pageToken=token).execute()
            out += r.get("comments", [])
            token = r.get("nextPageToken")
            if not token:
                return out

    def create_comment(self, doc_id: str, text: str) -> str:
        return self.drive.comments().create(fileId=doc_id, body={"content": text}, fields="id").execute()["id"]

    def reply(self, doc_id: str, comment_id: str, text: str, action: str | None = None) -> str:
        body: dict[str, Any] = {}
        if text:
            body["content"] = text
        if action:
            body["action"] = action
        return self.drive.replies().create(fileId=doc_id, commentId=comment_id, body=body,
                                           fields="id,action").execute()["id"]


def doc_url(doc_id: str) -> str:
    return f"https://docs.google.com/document/d/{doc_id}/edit"


# ---------------------------------------------------------------------------
# quote location (shared by doc_ops locate/comments)
# ---------------------------------------------------------------------------


def clean_quote(ctx: Ctx, quote: str) -> str:
    hre = header_re(ctx)
    lines = []
    for k, line in enumerate(quote.splitlines()):
        line = line.strip()
        if not line or line.startswith("▶") or line.startswith(MARKER_PREFIXES) or STATUS_RE.match(line) \
                or hre.match(line):
            continue
        lines.append(CONT_RE.sub("", line, count=1) if k else line)
    return " ".join(lines)


def locate_quote(ctx: Ctx, quote: str) -> tuple[tuple[int, int] | None, str | None]:
    """Unique inclusive word range of a quoted passage, or (None, reason)."""
    toks = [k for k in (search_key(t) for t in clean_quote(ctx, quote).split()) if k]
    if not toks:
        return None, "quote has no transcript words (a label/status line, or empty)"
    keys = ctx.search_keys()
    n = len(toks)
    hits = [i for i in range(len(keys) - n + 1) if keys[i] == toks[0] and keys[i:i + n] == toks]
    if not hits and n >= 3:
        # Docs highlights arbitrary characters: tolerate a partial first (suffix) / last (prefix) word
        hits = [i for i in range(len(keys) - n + 1)
                if keys[i + 1:i + n - 1] == toks[1:-1] and keys[i].endswith(toks[0])
                and keys[i + n - 1].startswith(toks[-1])]
    if not hits:
        return None, f"quote not found in the transcript: {' '.join(toks)[:80]!r}"
    if len(hits) > 1:
        times = ", ".join(fmt_clock(ctx.words[i]["start"]) for i in hits[:6])
        return None, f"quote is ambiguous ({len(hits)} matches at {times}); highlight more words"
    return (hits[0], hits[0] + n - 1), None


def describe_range(ctx: Ctx, a: int, b: int) -> dict[str, Any]:
    w = ctx.words
    return {"start_word": a, "end_word": b, "start_time": w[a]["start"], "end_time": w[b]["end"],
            "start_clock": fmt_clock(w[a]["start"]), "end_clock": fmt_clock(w[b]["end"], ceil=True),
            "speaker": ctx.names[w[a]["speaker"]], "text": " ".join(x["w"] for x in w[a:b + 1])[:300]}
