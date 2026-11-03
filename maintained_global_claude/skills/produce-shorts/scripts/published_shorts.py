#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "typer",
#   "loguru",
#   "rich",
#   "pydantic",
#   "rapidfuzz",
#   "machine-learning-helpers @ git+https://github.com/vmasrani/machine_learning_helpers.git",
# ]
# ///
"""Index every published short on the Increments Podcast channel and match them to episodes.

  index  [--refresh]              fetch shorts (<=180 s) + transcripts via the `yt` CLI into the cache
  match  EPISODE_DIR [--min-score] write EPISODE_DIR/published-overlap.json
  which                           map every indexed short to the local episode dirs it matches

Data path: `yt list` (table, parsed with COLUMNS widened so rows never wrap) for ids/titles/dates/
durations; `yt transcript --format json` for caption segments with timestamps.
"""
import json
import math
import os
import re
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import typer
from loguru import logger
from mlh.parallel import pmap
from pydantic import BaseModel
from rapidfuzz import fuzz
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False, no_args_is_help=True)
console = Console()

YT = "/Users/vmasrani/tools/yt"
CACHE = Path("/Volumes/external/dev/podcast_shorts/published-shorts")
EPISODES_GLOB = "/Volumes/external/dev/podcast_shorts"
SHORT_MAX_S = 180
SEED_N = 3  # n-gram size used to seed alignments
MAX_SEED_POSITIONS = 25  # ignore n-grams more frequent than this in an episode (filler phrases)
DIAG_TOL = 12  # token drift tolerated inside one region (caption insertions/deletions)
GAP_TOL = 40  # max episode-token gap between seeds of one region
MIN_SEEDS = 3
MIN_REGION_TOKENS = 8
LEN_SCALE = 10.0  # tokens; region score = ratio * (1 - exp(-tokens/LEN_SCALE))
DEFAULT_MIN_SCORE = 0.60  # chosen from the observed gap; see `match` docstring / report


class ShortMeta(BaseModel):
    video_id: str
    title: str
    published_at: str
    duration_s: int

    @property
    def url(self) -> str:
        return f"https://www.youtube.com/shorts/{self.video_id}"


class Region(BaseModel):
    video_id: str
    title: str
    url: str
    published_at: str
    source_start: float
    source_end: float
    start_word: int
    end_word: int
    match_score: float


# --------------------------------------------------------------------------- yt access


def run_yt(*args: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "COLUMNS": "600", "NO_COLOR": "1"}
    return subprocess.run([YT, *args], capture_output=True, text=True, env=env)


def parse_duration(text: str) -> int:
    return sum(int(p) * 60**i for i, p in enumerate(reversed(text.strip().split(":"))))


def list_shorts() -> list[ShortMeta]:
    proc = run_yt("list", "--max", "5000")
    if proc.returncode != 0:
        raise SystemExit(f"`yt list` failed (exit {proc.returncode}): {proc.stderr[-400:]}")
    rows = [
        [c.strip() for c in line.strip("│ ").split("│")]
        for line in proc.stdout.splitlines()
        if line.startswith("│")
    ]
    if not rows:
        raise SystemExit("`yt list` produced no table rows; its output format changed?")
    videos = [
        ShortMeta(video_id=r[0], published_at=r[1], duration_s=parse_duration(r[2]), title=r[5])
        for r in rows
    ]
    logger.info("channel videos: {}", len(videos))
    return [v for v in videos if v.duration_s <= SHORT_MAX_S]


def fetch_transcript(meta: ShortMeta) -> dict:
    proc = run_yt("transcript", "--format", "json", "--", meta.video_id)  # `--`: ids may start with "-"
    stdout = proc.stdout.strip()
    segments = json.loads(stdout[stdout.index("[") :]) if proc.returncode == 0 and "[" in stdout else None
    reason = None
    if proc.returncode != 0:
        lines = [l.strip("│ ").strip() for l in proc.stderr.splitlines() if re.search(r"[A-Za-z]{4}", l) and not l.startswith("╰")]
        reason = (lines or ["yt transcript failed"])[-1][:300]
    elif not segments:
        reason = "yt transcript returned no segments"
    return {**meta.model_dump(), "url": meta.url, "transcript": segments or None, "reason": reason}


# --------------------------------------------------------------------------- cache


def load_cached(video_id: str) -> dict | None:
    path = CACHE / f"{video_id}.json"
    return json.loads(path.read_text()) if path.exists() else None


def load_index() -> list[dict]:
    index_path = CACHE / "index.json"
    if not index_path.exists():
        raise SystemExit(f"no index at {index_path}; run `published_shorts.py index` first")
    return json.loads(index_path.read_text())["shorts"]


def load_transcripts() -> list[dict]:
    docs = [load_cached(e["video_id"]) for e in load_index()]
    return [d for d in docs if d and d["transcript"]]


def write_index_md(docs: list[dict]) -> None:
    def block(d: dict) -> str:
        body = " ".join(s["text"].replace("\n", " ") for s in d["transcript"]) if d["transcript"] else f"_no transcript: {d['reason']}_"
        return f"## {d['title']}\n\n{d['published_at']} · {d['url']} · {d['duration_s']}s\n\n{body}\n"

    header = f"# Published shorts ({len(docs)})\n\n"
    (CACHE / "index.md").write_text(header + "\n".join(block(d) for d in docs))


@app.command()
def index(refresh: bool = typer.Option(False, "--refresh", help="Re-fetch transcripts already cached")):
    """List every channel video <=180 s, fetch transcripts (timestamped), cache durably."""
    CACHE.mkdir(parents=True, exist_ok=True)
    shorts = list_shorts()
    todo = [s for s in shorts if refresh or not (cached := load_cached(s.video_id)) or cached["transcript"] is None]
    logger.info("shorts: {} | to fetch: {} | already cached: {}", len(shorts), len(todo), len(shorts) - len(todo))
    fetched = pmap(fetch_transcript, todo, n_jobs=4, prefer="threads") if todo else []
    for doc in fetched:
        (CACHE / f"{doc['video_id']}.json").write_text(json.dumps(doc, indent=1))
    docs = [load_cached(s.video_id) for s in shorts]
    entries = [
        {k: d[k] for k in ("video_id", "title", "url", "published_at", "duration_s", "reason")}
        | {"transcript_file": f"{d['video_id']}.json", "has_transcript": d["transcript"] is not None}
        for d in docs
    ]
    (CACHE / "index.json").write_text(
        json.dumps({"generated_at": datetime.now(timezone.utc).isoformat(), "shorts": entries}, indent=1)
    )
    write_index_md(docs)
    missing = [d for d in docs if d["transcript"] is None]
    console.print(f"[bold]{len(shorts)} shorts[/bold]: {len(shorts) - len(missing)} with transcripts, "
                  f"[bold red]{len(missing)} WITHOUT[/bold red] -> {CACHE}")
    for d in missing:
        console.print(f"  [red]no transcript[/red] {d['video_id']} {d['title'][:60]!r}: {d['reason']}")


# --------------------------------------------------------------------------- alignment


def norm_tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", re.sub(r"[’']", "", re.sub(r"\[[^\]]*\]", " ", text.lower())))


class Episode:
    """Normalized token stream of an episode, with a map back to transcript.json word indices."""

    def __init__(self, episode_dir: Path):
        path = episode_dir / "transcript" / "transcript.json"
        if not path.exists():
            raise SystemExit(f"missing {path}")
        self.words = json.loads(path.read_text())["words"]
        self.tokens: list[str] = []
        self.word_of: list[int] = []
        for i, w in enumerate(self.words):
            for t in norm_tokens(w["w"]):
                self.tokens.append(t)
                self.word_of.append(i)
        self.grams: dict[tuple, list[int]] = defaultdict(list)
        for i in range(len(self.tokens) - SEED_N + 1):
            self.grams[tuple(self.tokens[i : i + SEED_N])].append(i)


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
    ok = lambda a, b: fuzz.ratio(a, b) >= 80
    while j0 > 0 and i0 > 0 and ok(short[j0 - 1], ep.tokens[i0 - 1]):
        j0, i0 = j0 - 1, i0 - 1
    while j1 < len(short) - 1 and i1 < len(ep.tokens) - 1 and ok(short[j1 + 1], ep.tokens[i1 + 1]):
        j1, i1 = j1 + 1, i1 + 1
    return j0, i0, j1, i1


def match_short(ep: Episode, doc: dict) -> list[Region]:
    short = norm_tokens(" ".join(s["text"] for s in doc["transcript"]))
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
            video_id=doc["video_id"], title=doc["title"], url=doc["url"], published_at=doc["published_at"],
            source_start=float(ep.words[sw]["start"]), source_end=float(ep.words[ew]["end"]),
            start_word=sw, end_word=ew, match_score=round(score, 4),
        ))
    return dedupe(found)


def dedupe(regions: list[Region]) -> list[Region]:
    """Of regions overlapping in the episode, keep the best-scoring one."""
    kept: list[Region] = []
    for r in sorted(regions, key=lambda r: -r.match_score):
        if not any(r.start_word <= k.end_word and k.start_word <= r.end_word for k in kept):
            kept.append(r)
    return sorted(kept, key=lambda r: r.start_word)


def match_episode(episode_dir: Path, docs: list[dict]) -> list[Region]:
    ep = Episode(episode_dir)
    return sorted((r for d in docs for r in match_short(ep, d)), key=lambda r: r.start_word)


def mmss(t: float) -> str:
    return f"{int(t) // 60}:{int(t) % 60:02d}"


@app.command()
def match(
    episode_dir: Path,
    min_score: float = typer.Option(DEFAULT_MIN_SCORE, "--min-score", help="Drop regions scoring below this (0-1)"),
):
    """Find which published shorts came from EPISODE_DIR; write published-overlap.json.

    Score = rapidfuzz ratio between the short's matched span and the episode's span, discounted for short spans.
    Observed on the real channel: genuine regions score >=0.8; chance seed clusters (filler
    phrases) top out well below 0.5, so the 0.60 default sits in the empty gap.
    """
    episode_dir = episode_dir.resolve()
    docs = load_transcripts()
    regions = [r for r in match_episode(episode_dir, docs) if r.match_score >= min_score]
    out = {"episode_id": episode_dir.name.removeprefix("episode-"), "shorts": [r.model_dump() for r in regions]}
    (episode_dir / "published-overlap.json").write_text(json.dumps(out, indent=2))
    table = Table(title=f"{episode_dir.name}: {len(regions)} published regions (min score {min_score})")
    for col in ("short", "published", "source span", "words", "score"):
        table.add_column(col)
    for r in regions:
        table.add_row(r.title[:60], r.published_at[:10], f"{mmss(r.source_start)}-{mmss(r.source_end)}",
                      f"{r.start_word}-{r.end_word}", f"{r.match_score:.2f}")
    console.print(table)


@app.command()
def which(min_score: float = typer.Option(DEFAULT_MIN_SCORE, "--min-score")):
    """For every indexed short, list the local episode dirs it matches (and where)."""
    docs = load_transcripts()
    episodes = sorted(p for p in Path(EPISODES_GLOB).glob("episode-*") if (p / "transcript" / "transcript.json").exists())
    by_short: dict[str, list[str]] = defaultdict(list)
    for e in episodes:
        for r in match_episode(e, docs):
            if r.match_score >= min_score:
                by_short[r.video_id].append(f"{e.name} {mmss(r.source_start)}-{mmss(r.source_end)} ({r.match_score:.2f})")
    table = Table(title=f"{len(docs)} shorts vs {len(episodes)} local episodes")
    for col in ("short", "published", "matches"):
        table.add_column(col)
    for d in sorted(docs, key=lambda d: d["published_at"]):
        table.add_row(d["title"][:60], d["published_at"][:10], "\n".join(by_short.get(d["video_id"], [])) or "[dim]-[/dim]")
    console.print(table)
    console.print(f"{len(by_short)} of {len(docs)} shorts map to a local episode")


if __name__ == "__main__":
    app()
