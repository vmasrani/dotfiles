#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "platformdirs>=4",
#   "httpx>=0.27",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "rapidfuzz>=3.9",
#   "yt-dlp[default]>=2026.8.19",
#   "youtube-transcript-api>=1.2",
# ]
# ///
"""Published-shorts overlap check — don't re-cut a moment the channel already published.

  index  [--channel URL] [--refresh]       list the channel's /shorts tab + fetch each transcript (cached)
  match  EPISODE [--picks picks.json]      write EPISODE/published-overlap.json; table of overlapping shorts

No login anywhere: the listing uses the yt-dlp Python API (flat extraction of public pages) and the
transcripts use `youtube-transcript-api` (public captions). The cache lives under the per-user cache dir
(platformdirs, same place as the Anton font / end tag) and is incremental: `index` only fetches IDs it has no
definitive answer for. A short with captions turned off is recorded as `no_transcript` (legitimate absence);
a network/blocked/parse failure is recorded as `error` per short, retried on the next `index`, and
reported loudly by both commands — it is never treated as "no overlap".
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from loguru import logger
from rapidfuzz import fuzz
from rich.console import Console
from rich.table import Table

from assets import cache_dir

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

DEFAULT_CHANNEL = "https://www.youtube.com/@IncrementsPod"
FETCH_WORKERS = 4

SEED_N = 3  # n-gram size used to seed alignments
MAX_SEED_POSITIONS = 25  # ignore n-grams more frequent than this in an episode (filler phrases)
DIAG_TOL = 12  # token drift tolerated inside one region (caption insertions/deletions)
GAP_TOL = 40  # max episode-token gap between seeds of one region
MIN_SEEDS = 3
MIN_REGION_TOKENS = 8
LEN_SCALE = 10.0  # tokens; region score = ratio * (1 - exp(-tokens/LEN_SCALE))
DEFAULT_MIN_SCORE = 0.60  # genuine regions scored >=0.8, chance filler-phrase clusters <0.5 on the real channel
PICK_DUPLICATE = 0.50  # share of a pick's words inside published regions => "duplicate"
PICK_PARTIAL = 0.15  # ... => "partial"

OK, NO_TRANSCRIPT, ERROR = "ok", "no_transcript", "error"


# --------------------------------------------------------------------------- listing + transcripts (network)


def shorts_tab(channel: str) -> str:
    return channel.rstrip("/") if channel.rstrip("/").endswith("/shorts") else channel.rstrip("/") + "/shorts"


def list_shorts(channel: str) -> list[dict]:
    """Every short on the channel's /shorts tab: [{video_id, title, url}]. Public page, no login."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError

    url = shorts_tab(channel)
    opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "skip_download": True}
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
    except DownloadError as e:
        raise SystemExit(f"could not list shorts at {url}: {e}\nCheck --channel (a youtube.com/@handle URL) and your network.") from e
    entries = [e for e in (info or {}).get("entries") or [] if e and e.get("id")]
    if not entries:
        raise SystemExit(f"{url} listed no shorts; check --channel is a youtube.com/@handle URL with a /shorts tab")
    return [
        {"video_id": e["id"], "title": e.get("title") or e["id"], "url": f"https://www.youtube.com/shorts/{e['id']}"}
        for e in entries
    ]


def fetch_transcript(video_id: str) -> dict:
    """{status, segments, reason}. Captions off/absent = NO_TRANSCRIPT; any other failure = ERROR (retried later)."""
    from youtube_transcript_api import NoTranscriptFound, TranscriptsDisabled, YouTubeTranscriptApi

    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["en"])
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        return {"status": NO_TRANSCRIPT, "segments": None, "reason": type(e).__name__}
    except Exception as e:  # per-short boundary: recorded and surfaced, never swallowed
        return {"status": ERROR, "segments": None, "reason": f"{type(e).__name__}: {str(e).strip()[:200]}"}
    segments = [{"text": s.text, "start": s.start, "duration": s.duration} for s in fetched]
    if not segments:
        return {"status": ERROR, "segments": None, "reason": "transcript fetched but contained no segments"}
    return {"status": OK, "segments": segments, "reason": None}


# --------------------------------------------------------------------------- cache


def channel_cache(channel: str) -> Path:
    u = urlparse(channel)
    key = re.sub(r"[^A-Za-z0-9]+", "-", f"{u.netloc}{u.path}").strip("-").lower() or "channel"
    d = cache_dir() / "published-shorts" / key
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_json(path: Path, data: object) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def load_short(root: Path, video_id: str) -> dict | None:
    path = root / f"{video_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def needs_fetch(root: Path, video_id: str, refresh: bool) -> bool:
    """Only IDs without a definitive answer: never fetched, or last attempt errored. --refresh refetches all."""
    cached = load_short(root, video_id)
    return refresh or cached is None or cached["status"] == ERROR


def sync_index(root: Path, listing: list[dict], fetch: Callable[[str], dict], refresh: bool = False,
               workers: int = FETCH_WORKERS) -> dict:
    """Fetch transcripts for the IDs that need one, write per-short files + index.json. Returns a summary."""
    todo = [s for s in listing if needs_fetch(root, s["video_id"], refresh)]
    logger.info("shorts: {} | to fetch: {} | cached: {}", len(listing), len(todo), len(listing) - len(todo))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda s: fetch(s["video_id"]), todo))
    for meta, res in zip(todo, results, strict=True):
        _write_json(root / f"{meta['video_id']}.json", {**meta, **res, "fetched_at": datetime.now(timezone.utc).isoformat()})
    docs = [load_short(root, s["video_id"]) for s in listing]
    entries = [{k: d[k] for k in ("video_id", "title", "url", "status", "reason")} for d in docs]
    _write_json(root / "index.json", {"generated_at": datetime.now(timezone.utc).isoformat(), "shorts": entries})
    counts = {s: sum(e["status"] == s for e in entries) for s in (OK, NO_TRANSCRIPT, ERROR)}
    return {"total": len(entries), "fetched": len(todo), "entries": entries, **counts}


def load_docs(root: Path) -> list[dict]:
    index_path = root / "index.json"
    if not index_path.exists():
        raise SystemExit(f"no published-shorts index at {root}; run `uv run scripts/published_shorts.py index` first")
    return [load_short(root, e["video_id"]) for e in json.loads(index_path.read_text())["shorts"]]


# --------------------------------------------------------------------------- alignment (word n-gram seeds -> regions)


def norm_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", re.sub(r"[’']", "", re.sub(r"\[[^\]]*\]", " ", text.lower())))


@dataclass
class Region:
    video_id: str
    title: str
    url: str
    source_start: float
    source_end: float
    start_word: int
    end_word: int
    match_score: float
    short_coverage: float  # share of the short's own words that fall inside this region


class Episode:
    """Normalized token stream of an episode, with a map back to transcript.json word indices."""

    def __init__(self, words: list[dict]):
        self.words = words
        self.tokens: list[str] = []
        self.word_of: list[int] = []
        for i, w in enumerate(words):
            for t in norm_tokens(w["w"]):
                self.tokens.append(t)
                self.word_of.append(i)
        if not self.tokens:
            raise SystemExit("episode transcript has no words")
        self.grams: dict[tuple, list[int]] = defaultdict(list)
        for i in range(len(self.tokens) - SEED_N + 1):
            self.grams[tuple(self.tokens[i : i + SEED_N])].append(i)

    @classmethod
    def load(cls, episode_dir: Path) -> Episode:
        path = episode_dir / "transcript" / "transcript.json"
        if not path.exists():
            raise SystemExit(f"missing {path}; run ingest + transcribe for this episode first")
        return cls(json.loads(path.read_text())["words"])


def seed_regions(ep: Episode, short: list[str]) -> list[list[tuple[int, int]]]:
    """Cluster shared n-grams (short pos j, episode pos i) by diagonal i-j, split on episode gaps."""
    seeds = [
        (j, i)
        for j in range(len(short) - SEED_N + 1)
        if len(pos := ep.grams.get(tuple(short[j : j + SEED_N]), ())) <= MAX_SEED_POSITIONS
        for i in pos
    ]
    seeds.sort(key=lambda s: s[1] - s[0])
    groups: list[list[tuple[int, int]]] = []
    for s in seeds:
        if groups and (s[1] - s[0]) - (groups[-1][-1][1] - groups[-1][-1][0]) <= DIAG_TOL:
            groups[-1].append(s)
        else:
            groups.append([s])
    regions: list[list[tuple[int, int]]] = []
    for g in groups:
        g.sort(key=lambda s: s[1])
        cur = [g[0]]
        for s in g[1:]:
            if s[1] - cur[-1][1] > GAP_TOL:
                regions.append(cur)
                cur = []
            cur.append(s)
        regions.append(cur)
    return [r for r in regions if len(r) >= MIN_SEEDS]


def extend(ep: Episode, short: list[str], j0: int, i0: int, j1: int, i1: int) -> tuple[int, int, int, int]:
    """Grow a region outward in lockstep while tokens still fuzzy-match (caption errors tolerated)."""
    ok = lambda a, b: fuzz.ratio(a, b) >= 80  # noqa: E731
    while j0 > 0 and i0 > 0 and ok(short[j0 - 1], ep.tokens[i0 - 1]):
        j0, i0 = j0 - 1, i0 - 1
    while j1 < len(short) - 1 and i1 < len(ep.tokens) - 1 and ok(short[j1 + 1], ep.tokens[i1 + 1]):
        j1, i1 = j1 + 1, i1 + 1
    return j0, i0, j1, i1


def dedupe(regions: list[Region]) -> list[Region]:
    """Of regions overlapping in the episode, keep the best-scoring one."""
    kept: list[Region] = []
    for r in sorted(regions, key=lambda r: -r.match_score):
        if not any(r.start_word <= k.end_word and k.start_word <= r.end_word for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start_word)


def match_short(ep: Episode, doc: dict) -> list[Region]:
    short = norm_tokens(" ".join(s["text"] for s in doc["segments"]))
    found: list[Region] = []
    for cluster in seed_regions(ep, short):
        j0 = min(s[0] for s in cluster)
        j1 = max(s[0] for s in cluster) + SEED_N - 1
        i0 = min(s[1] for s in cluster)
        i1 = max(s[1] for s in cluster) + SEED_N - 1
        j0, i0, j1, i1 = extend(ep, short, j0, i0, j1, i1)
        n = min(j1 - j0, i1 - i0) + 1
        if n < MIN_REGION_TOKENS:
            continue
        ratio = fuzz.ratio(" ".join(short[j0 : j1 + 1]), " ".join(ep.tokens[i0 : i1 + 1])) / 100
        score = ratio * (1 - math.exp(-n / LEN_SCALE))  # short chance matches are discounted
        sw, ew = ep.word_of[i0], ep.word_of[i1]
        found.append(Region(
            video_id=doc["video_id"], title=doc["title"], url=doc["url"],
            source_start=float(ep.words[sw]["start"]), source_end=float(ep.words[ew]["end"]),
            start_word=sw, end_word=ew, match_score=round(score, 4),
            short_coverage=round(min(1.0, (j1 - j0 + 1) / len(short)), 4),
        ))
    return dedupe(found)


def match_episode(ep: Episode, docs: list[dict], min_score: float) -> list[Region]:
    usable = [d for d in docs if d["status"] == OK]
    regions = [r for d in usable for r in match_short(ep, d) if r.match_score >= min_score]
    return sorted(regions, key=lambda r: r.start_word)


# --------------------------------------------------------------------------- picks


def pick_word_indices(words: list[dict], pick: dict) -> set[int]:
    """Words a pick keeps: midpoint inside a range and outside every cut (same rule as picklib)."""
    mid = lambda w: (w["start"] + w["end"]) / 2  # noqa: E731
    inside = lambda w, spans: any(s["start"] <= mid(w) < s["end"] for s in spans)  # noqa: E731
    return {i for i, w in enumerate(words) if inside(w, pick.get("ranges") or []) and not inside(w, pick.get("cuts") or [])}


def check_pick(words: list[dict], pick: dict, regions: list[Region]) -> dict:
    kept = pick_word_indices(words, pick)
    if not kept:
        raise SystemExit(f"pick {pick.get('id')}: its ranges contain no transcript words")
    hit = [r for r in regions if any(r.start_word <= i <= r.end_word for i in kept)]
    covered = sum(any(r.start_word <= i <= r.end_word for r in hit) for i in kept)
    pct = covered / len(kept)
    verdict = "duplicate" if pct >= PICK_DUPLICATE else "partial" if pct >= PICK_PARTIAL else "clear"
    return {"id": pick.get("id"), "title": pick.get("title"), "overlap_pct": round(pct * 100, 1), "verdict": verdict,
            "shorts": sorted({r.video_id for r in hit})}


# --------------------------------------------------------------------------- commands


def mmss(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


def report_problems(entries: list[dict]) -> None:
    for e in entries:
        if e["status"] == ERROR:
            console.print(f"  [bold red]ERROR[/bold red] {e['video_id']} {e['title'][:60]!r}: {e['reason']}")
        elif e["status"] == NO_TRANSCRIPT:
            console.print(f"  [yellow]no captions[/yellow] {e['video_id']} {e['title'][:60]!r}: {e['reason']} (cannot be compared)")


@app.command()
def index(
    channel: str = typer.Option(DEFAULT_CHANNEL, "--channel", help="Channel URL (youtube.com/@handle)"),
    refresh: bool = typer.Option(False, "--refresh", help="Refetch transcripts already cached"),
):
    """List the channel's shorts and cache every transcript (incremental: only new IDs are fetched)."""
    root = channel_cache(channel)
    summary = sync_index(root, list_shorts(channel), fetch_transcript, refresh)
    console.print(f"[bold]{summary['total']} shorts[/bold] ({summary['fetched']} fetched this run): "
                  f"{summary[OK]} with transcripts, {summary[NO_TRANSCRIPT]} without captions, "
                  f"[bold red]{summary[ERROR]} failed[/bold red] -> {root}")
    report_problems(summary["entries"])
    if summary[OK] == 0:
        raise SystemExit(f"no short has a usable transcript ({summary[ERROR]} failed). If these are network or IP-block "
                         "errors, retry later or from another network; then re-run `index`.")
    if summary[ERROR]:
        console.print("[red]Failed shorts are NOT checked for overlap; re-run `index` to retry just those.[/red]")


@app.command()
def match(
    episode: Path = typer.Argument(..., help="Episode folder containing transcript/transcript.json"),
    picks: Path | None = typer.Option(None, "--picks", help="picks.json; each pick's span is checked too"),
    channel: str = typer.Option(DEFAULT_CHANNEL, "--channel", help="Channel whose cached index to use"),
    min_score: float = typer.Option(DEFAULT_MIN_SCORE, "--min-score", help="Drop regions scoring below this (0-1)"),
):
    """Find published shorts whose words appear in EPISODE; write EPISODE/published-overlap.json."""
    episode = episode.resolve()
    ep = Episode.load(episode)
    docs = load_docs(channel_cache(channel))
    checkable = [d for d in docs if d["status"] == OK]
    if not checkable:
        raise SystemExit("the cached index has no usable transcripts; run `uv run scripts/published_shorts.py index` first")
    unchecked = [{k: d[k] for k in ("video_id", "title", "status", "reason")} for d in docs if d["status"] != OK]
    regions = match_episode(ep, docs, min_score)
    pick_rows = [check_pick(ep.words, p, regions) for p in json.loads(picks.read_text())["picks"]] if picks else []
    out = {"episode_id": episode.name.removeprefix("episode-"), "channel": channel, "min_score": min_score,
           "shorts_checked": len(checkable), "unchecked": unchecked,
           "overlaps": [asdict(r) for r in regions], "picks": pick_rows}
    (episode / "published-overlap.json").write_text(json.dumps(out, indent=2))

    table = Table(title=f"{episode.name}: {len(regions)} published short(s) overlap ({len(checkable)} checked)")
    for col in ("short", "title", "episode time", "overlap %", "score"):
        table.add_column(col)
    for r in regions:
        table.add_row(r.video_id, r.title[:60], f"{mmss(r.source_start)}-{mmss(r.source_end)}",
                      f"{r.short_coverage * 100:.0f}%", f"{r.match_score:.2f}")
    console.print(table)
    if pick_rows:
        pt = Table(title="proposed picks vs published shorts")
        for col in ("pick", "overlap %", "verdict", "shorts"):
            pt.add_column(col)
        for p in pick_rows:
            pt.add_row(f"{p['id']} {str(p['title'])[:40]}", f"{p['overlap_pct']:.0f}%", p["verdict"], ", ".join(p["shorts"]) or "-")
        console.print(pt)
    if unchecked:
        console.print(f"[bold red]{len(unchecked)} short(s) could NOT be compared:[/bold red]")
        report_problems(unchecked)
    console.print(f"wrote {episode / 'published-overlap.json'}")


if __name__ == "__main__":
    app()
