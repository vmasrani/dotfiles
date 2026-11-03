"""Pick model: which transcript words each approved pick owns / cuts. Built from `picks.json`
(the chat-approved list), consumed by freeze_picks.py.

picks.json shape:
  {"picks": [{"id": "S1", "format": "short"|"clip", "title": "...", "why": "...",
              "ranges": [{"start": 1003.8, "end": 1049.5}, ...],      # kept source spans (seconds)
              "cuts":   [{"start": 1020.0, "end": 1024.5}]}]}         # optional spans removed inside
Spans select words by midpoint, so a span never needs to be frame-exact.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, NoReturn

SHORT_LIMIT_S = 177.6  # + the 2.33 s end tag must stay under YouTube Shorts' 180 s cap (= 2:57.6 of speech)
FORMATS = {"short": "S", "clip": "C"}
ENDS_ON_WORDS = 8


def die(msg: str) -> NoReturn:
    raise SystemExit(f"error: {msg}")


@dataclass
class PickMeta:
    id: str
    format: str
    title: str
    why: str = ""


@dataclass
class Model:
    owner: list[str | None]
    cut: list[bool]
    picks: dict[str, PickMeta]

    def owned(self, pid: str) -> list[int]:
        return [i for i, o in enumerate(self.owner) if o == pid]


def fmt_dur(seconds: float) -> str:
    total = int(round(seconds))
    return f"{total // 60}:{total % 60:02d}"


def ends_on(words: list[dict[str, Any]], model: Model, pid: str) -> str:
    kept = [i for i in model.owned(pid) if not model.cut[i]]
    return " ".join(words[i]["w"] for i in kept[-ENDS_ON_WORDS:])


def _inside(w: dict[str, Any], spans: list[dict[str, float]]) -> bool:
    mid = (w["start"] + w["end"]) / 2
    return any(s["start"] <= mid < s["end"] for s in spans)


def model_from_picks(words: list[dict[str, Any]], picks: list[dict[str, Any]]) -> Model:
    """Validate picks.json entries and assign each word to at most one pick."""
    metas: dict[str, PickMeta] = {}
    owner: list[str | None] = [None] * len(words)
    cut = [False] * len(words)
    for p in picks:
        pid, fmt = p.get("id"), p.get("format")
        if fmt not in FORMATS:
            die(f"pick {pid}: format must be short|clip, got {fmt!r}")
        if not pid or pid[0] != FORMATS[fmt] or not pid[1:].isdigit():
            die(f"pick id {pid!r} must be {FORMATS[fmt]}<number> for format {fmt}")
        if pid in metas:
            die(f"duplicate pick id {pid}")
        if not p.get("title"):
            die(f"pick {pid}: title is required")
        ranges = p.get("ranges") or []
        if not ranges or any(r["end"] <= r["start"] for r in ranges):
            die(f"pick {pid}: ranges must be non-empty with end > start")
        metas[pid] = PickMeta(pid, fmt, p["title"], p.get("why", ""))
        hit = [i for i, w in enumerate(words) if _inside(w, ranges)]
        if not hit:
            die(f"pick {pid}: its ranges contain no transcript words")
        for i in hit:
            if owner[i] is not None:
                die(f"picks {owner[i]} and {pid} both claim word #{i} {words[i]['w']!r}@{words[i]['start']:.1f}s — "
                    "picks must not overlap; trim one")
            owner[i] = pid
            cut[i] = _inside(words[i], p.get("cuts") or [])
    return Model(owner, cut, metas)
