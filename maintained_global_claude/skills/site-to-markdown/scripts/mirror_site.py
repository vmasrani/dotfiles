#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "loguru",
#     "rich",
#     "curl_cffi",
#     "trafilatura",
#     "pandas",
#     "lxml",
#     "machine-learning-helpers",
# ]
#
# [tool.uv.sources]
# machine-learning-helpers = { git = "https://github.com/vmasrani/machine_learning_helpers.git" }
# ///
"""
mirror_site.py — mirror any website to clean markdown via its sitemaps, in two auditable phases.

Discovery is sitemap-based, not link-crawling: it reads the site's own published sitemaps
(from robots.txt + the usual /sitemap.xml locations, recursing into sitemap indexes). That is
faster, complete, and doesn't get blocked the way a wget crawl does — many sites 403 an unknown
crawler on the homepage, so a link-crawler silently discovers nothing.

Phase 1 — enumerate every URL into auditable files you eyeball before downloading anything:

    ./mirror_site.py urls example.com
    ./mirror_site.py urls example.com --host docs.example.com   # add extra hosts by hand

    Writes, into ./<domain>-md/:
      urls.txt        every discovered URL, one per line  (the full audit list)
      urls-keep.txt   URLs that look like real text pages -> become markdown
      urls-drop.txt   dropped URLs + reason (taxonomy/archive/asset pages)
      urls.csv        full annotated table (url, host, category, keep, reason)

    Inspect urls-drop.txt / urls-keep.txt, edit urls-keep.txt to taste, then run phase 2.

Phase 2 — download every kept URL and save its main text as markdown (no JS/nav/chrome):

    ./mirror_site.py fetch example.com

    Writes ./<domain>-md/<host>/<path>.md and a failures.txt for anything that errored.
"""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import trafilatura
import typer
from curl_cffi import requests as creq
from curl_cffi.requests.exceptions import RequestException
from loguru import logger
from lxml import etree
from rich.console import Console
from rich.table import Table

app = typer.Typer(add_completion=False, help=__doc__)
console = Console()


def get(url: str):
    """One HTTP GET impersonating a real Chrome (TLS fingerprint + full header set).

    Impersonation is load-bearing: Vercel/Cloudflare edge protection returns 403 to plain
    clients even when they send a browser User-Agent string, because it also checks the
    header set and the TLS/JA3 fingerprint. A UA-only request is the single most common
    reason a naive mirror comes back nearly empty. A fresh session per call keeps this
    safe to call from pmap worker threads (libcurl handles are not shareable across threads).
    """
    return creq.get(url, impersonate="chrome", timeout=30, allow_redirects=True)


# Subdomains that commonly hold readable content (docs are often on their own host with
# their own sitemap the main robots.txt never mentions). Probed unless --no-probe.
COMMON_SUBDOMAINS = ["docs", "developer", "developers", "help", "support", "learn", "blog"]

# Path fragments that mark a listing/taxonomy/system page rather than an article. These are
# best-effort: whatever slips through is caught by the human audit of urls-keep.txt, so the
# goal is to catch the obvious WordPress/CMS junk, not to be exhaustive.
DROP_PATH_RE = re.compile(
    r"/(category|categories|tag|tags|author|authors|topic|topics|"
    r"page/\d+|feed|amp|comment-page|wp-json|wp-admin|wp-login|xmlrpc|search)(/|$)",
    re.IGNORECASE,
)

# Extensions that are assets, not prose. Sitemaps rarely list these, but some do.
DROP_EXT = {
    "js", "css", "png", "jpg", "jpeg", "gif", "svg", "webp", "avif", "ico",
    "woff", "woff2", "ttf", "eot", "zip", "gz", "tar", "mp4", "mp3", "webm",
    "xml", "json", "rss", "atom", "map",
}

# Heading permalink cruft trafilatura leaves behind. Two forms:
#   1. a link whose text is only an anchor glyph / empty:  "## Title[⚓︎](…#title)"
#   2. a bare anchor glyph trailing a title/heading:        "## Title⚓︎"
# We strip both. The bare-glyph strip is limited to ⚓ (U+2693, always a permalink marker on
# these doc generators) plus its optional variation selector — deliberately NOT the section
# sign §, which is legitimate content on legal pages ("§ 4.2").
ANCHOR_LINK_RE = re.compile(r"\[[\s⚓¶#§︎]*\]\([^)]*\)")
BARE_ANCHOR_RE = re.compile(r"⚓︎?")


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------
def origin(domain: str) -> str:
    """'example.com' or 'https://example.com/x' -> 'https://example.com'."""
    p = urlparse(domain if "://" in domain else f"https://{domain}")
    return f"{p.scheme}://{p.netloc}"


def safe_root(body: bytes):
    """Parse XML, returning None instead of raising when the bytes aren't valid XML.

    Probing arbitrary URLs turns up HTML soft-404s and junk; a parse failure here means
    'not a sitemap', which is a normal probe outcome, not a program error.
    """
    try:
        return etree.fromstring(body)
    except etree.XMLSyntaxError:
        return None


def sitemap_root(url: str):
    """Fetch a URL and return its parsed root iff it's a real XML sitemap, else None.

    None is a *legitimate absence* (no sitemap at this location) — the caller decides
    whether that's expected (a probe) or worth warning about (a declared sitemap).
    """
    r = get(url)
    if r.status_code != 200:
        return None
    root = safe_root(r.content)
    if root is None or etree.QName(root).localname not in {"urlset", "sitemapindex"}:
        return None
    return root


def child_locs(root, parent: str) -> list[str]:
    """The <loc> directly under each <parent> element (<url> or <sitemap>).

    Deliberately ignores <image:loc> and other nested locs — Yoast/WordPress sitemaps embed
    every image referenced by a post, and we want to enumerate pages, not their assets.
    """
    return [loc.text.strip()
            for p in root.iter(f"{{*}}{parent}")
            for loc in [p.find("{*}loc")] if loc is not None and loc.text]


def sitemap_stem(url: str) -> str:
    return Path(urlparse(url).path).stem  # ".../post-sitemap.xml" -> "post-sitemap"


# ---------------------------------------------------------------------------
# phase 1 — discovery
# ---------------------------------------------------------------------------
def robots_sitemaps(base: str) -> list[str]:
    r = get(f"{base}/robots.txt")
    if r.status_code != 200:
        return []
    return re.findall(r"(?im)^\s*sitemap:\s*(\S+)", r.text)


def expand_sitemap(url: str, seen: set[str], depth: int = 0) -> list[tuple[str, str]]:
    """Return (page_url, source_sitemap_stem) for every page under a sitemap or index."""
    if url in seen or depth > 6:
        return []
    seen.add(url)
    root = sitemap_root(url)
    if root is None:
        return []
    if etree.QName(root).localname == "sitemapindex":
        return [pair for sub in child_locs(root, "sitemap")
                for pair in expand_sitemap(sub, seen, depth + 1)]
    stem = sitemap_stem(url)
    return [(u, stem) for u in child_locs(root, "url")]


def category_of(url: str, sitemap_stem: str) -> str:
    """A human-friendly grouping for the audit: the CMS sitemap name (WordPress gives us
    'post', 'page', 'glossary', ...) when it's meaningful, else the first path segment."""
    name = re.sub(r"[-_]?sitemap([-_]?index)?[-_]?\d*", "", sitemap_stem, flags=re.I).strip("-_")
    if name and not name.isdigit():
        return name
    seg = urlparse(url).path.strip("/").split("/")[0]
    return seg or "root"


def classify(url: str, sitemap_stem: str, host: str) -> dict:
    ext = Path(urlparse(url).path).suffix.lower().lstrip(".")
    category = category_of(url, sitemap_stem)
    if ext in DROP_EXT:
        return dict(url=url, host=host, category=category, keep=False, reason=f"asset file (.{ext})")
    if DROP_PATH_RE.search(urlparse(url).path):
        return dict(url=url, host=host, category=category, keep=False, reason="taxonomy/archive/system page")
    return dict(url=url, host=host, category=category, keep=True, reason="")


def discover_host(base: str, declared_ok: bool = True) -> list[dict]:
    """Find every page for one host via its sitemaps. Probed hosts pass declared_ok=False
    so a missing sitemap stays quiet; the primary host warns loudly if it yields nothing."""
    candidates = list(dict.fromkeys(
        robots_sitemaps(base) + [f"{base}/sitemap.xml", f"{base}/sitemap_index.xml"]))
    seen: set[str] = set()
    pairs = [p for sm in candidates for p in expand_sitemap(sm, seen)]
    pairs = list(dict.fromkeys(pairs))  # dedup, keep first sitemap that listed each URL
    host = urlparse(base).netloc
    if not pairs and declared_ok:
        logger.warning(f"no sitemap found for {host} (tried robots.txt + /sitemap.xml + "
                       f"/sitemap_index.xml) — this tool only mirrors sites that publish a sitemap")
    logger.info(f"{host}: {len(pairs)} urls from {len(seen)} sitemap(s)")
    return [classify(u, stem, host) for u, stem in pairs]


def host_has_sitemap(base: str) -> bool:
    """Existence probe for auto-discovered subdomains. A DNS/connection error just means the
    subdomain doesn't exist — a legitimate absence, so it's caught and reported as 'no'."""
    try:
        return bool(robots_sitemaps(base)) or sitemap_root(f"{base}/sitemap.xml") is not None
    except RequestException:
        return False


def discover(domain: str, extra_hosts: list[str], probe: bool) -> pd.DataFrame:
    base = origin(domain)
    hosts = [base]
    if probe:
        apex = re.sub(r"^www\.", "", urlparse(base).netloc)
        for sub in COMMON_SUBDOMAINS:
            candidate = f"https://{sub}.{apex}"
            if candidate != base and host_has_sitemap(candidate):
                logger.info(f"auto-discovered content host: {candidate}")
                hosts.append(candidate)
    hosts += [origin(h) for h in extra_hosts]
    hosts = list(dict.fromkeys(hosts))

    rows = [row for h in hosts for row in discover_host(h)]
    if not rows:
        raise typer.Exit(code=1)
    df = pd.DataFrame(rows)
    # A URL can appear in several sitemaps; when it does keep the keep=True copy so a real
    # page is never dropped just for also being listed in an archive sitemap.
    return (df.sort_values("keep", ascending=False)
              .drop_duplicates(subset="url", keep="first")
              .sort_values(["host", "category", "url"])
              .reset_index(drop=True))


# ---------------------------------------------------------------------------
# phase 2 — fetch + extract
# ---------------------------------------------------------------------------
def clean_markdown(md: str) -> str:
    """Deterministic tidy-up of trafilatura's output: strip heading-anchor cruft, trim
    trailing whitespace, collapse runs of blank lines, and end with a single newline.

    Pure string transforms — same input always yields the same output, no model involved.
    """
    md = ANCHOR_LINK_RE.sub("", md)
    md = BARE_ANCHOR_RE.sub("", md)
    md = "\n".join(line.rstrip() for line in md.splitlines())
    return re.sub(r"\n{3,}", "\n\n", md).strip() + "\n"


def fetch_one(url: str) -> dict:
    """Fetch one page and extract its main text as clean markdown.

    status: 'ok' (got markdown) | 'empty' (no extractable prose — thin/redirect/listing)
            | 'error: ...' (HTTP or network failure — recorded and surfaced, never hidden).

    The network error is caught only to attribute it to THIS url and keep the batch going;
    it is not swallowed — every failure lands in failures.txt and the run's summary.
    """
    try:
        r = get(url)
    except RequestException as e:
        return dict(url=url, status=f"error: {type(e).__name__}", markdown="")
    if r.status_code != 200:
        return dict(url=url, status=f"error: HTTP {r.status_code}", markdown="")
    md = trafilatura.extract(
        r.text, output_format="markdown", include_links=True,
        include_tables=True, with_metadata=True, url=url)
    if not md:
        return dict(url=url, status="empty", markdown="")
    return dict(url=url, status="ok", markdown=clean_markdown(md))


def url_to_path(outdir: Path, url: str) -> Path:
    """https://host/a/b/ -> outdir/host/a/b.md ; https://host/ -> outdir/host/index.md"""
    p = urlparse(url)
    rel = p.path.strip("/") or "index"
    return outdir / p.netloc / f"{rel}.md"


def save_llms_txt(base: str, outdir: Path) -> None:
    """Bonus: many sites now publish a curated /llms.txt overview. Grab it if present."""
    host = urlparse(base).netloc
    for name in ("llms.txt", "llms-full.txt"):
        r = get(f"{base}/{name}")
        if r.status_code == 200 and r.text.strip():
            path = outdir / host / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(r.text)
            logger.info(f"saved {host}/{name}")


# ---------------------------------------------------------------------------
# display (receives DataFrames; all Rich formatting lives here)
# ---------------------------------------------------------------------------
def show_discovery(df: pd.DataFrame) -> None:
    table = Table(title="Discovered URLs by category")
    for col, just in [("keep", "center"), ("host", "left"), ("category", "left"), ("count", "right")]:
        table.add_column(col, justify=just)
    summary = (df.groupby(["keep", "host", "category"]).size().reset_index(name="count")
                 .sort_values(["keep", "host", "count"], ascending=[False, True, False]))
    for _, r in summary.iterrows():
        table.add_row("[green]✓[/]" if r["keep"] else "[red]✗[/]",
                      r["host"], r["category"], str(r["count"]))
    console.print(table)
    kept = int(df["keep"].sum())
    console.print(f"[bold]{len(df)}[/] total urls  ·  [green]{kept} keep[/]  ·  [red]{len(df) - kept} drop[/]")


def show_fetch(df: pd.DataFrame) -> None:
    table = Table(title="Fetch results")
    table.add_column("status")
    table.add_column("count", justify="right")
    counts = df["status"].str.replace(r"error:.*", "error", regex=True).value_counts()
    for status, count in counts.items():
        table.add_row(status, str(count))
    console.print(table)


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------
def default_outdir(domain: str) -> Path:
    apex = re.sub(r"^www\.", "", urlparse(origin(domain)).netloc)
    return Path(f"{apex}-md")


@app.command()
def urls(
    domain: str = typer.Argument(..., help="site to mirror, e.g. example.com"),
    host: list[str] = typer.Option([], "--host", help="extra host(s) to include, repeatable"),
    outdir: Path = typer.Option(None, help="output dir (default: <domain>-md)"),
    probe: bool = typer.Option(True, help="auto-probe common content subdomains (docs., blog., ...)"),
) -> None:
    """Phase 1: enumerate every URL from the site's sitemaps into auditable .txt/.csv files."""
    outdir = outdir or default_outdir(domain)
    outdir.mkdir(parents=True, exist_ok=True)
    df = discover(domain, host, probe)

    (outdir / "urls.txt").write_text("\n".join(df["url"]) + "\n")
    (outdir / "urls-keep.txt").write_text("\n".join(df.loc[df["keep"], "url"]) + "\n")
    drop = df.loc[~df["keep"]]
    (outdir / "urls-drop.txt").write_text("".join(f"{r.url}\t{r.reason}\n" for r in drop.itertuples()))
    df.to_csv(outdir / "urls.csv", index=False)

    show_discovery(df)
    console.print(f"\nwrote [cyan]{outdir}/urls.txt[/] (all), [cyan]urls-keep.txt[/], "
                  f"[cyan]urls-drop.txt[/], [cyan]urls.csv[/]")
    console.print(f"audit urls-drop.txt, then run:  [bold]./mirror_site.py fetch {domain}[/]")


@app.command()
def fetch(
    domain: str = typer.Argument(..., help="same site you ran 'urls' on"),
    outdir: Path = typer.Option(None, help="output dir (default: <domain>-md)"),
    keep_file: Path = typer.Option(None, help="URL list to fetch (default: <outdir>/urls-keep.txt)"),
    n_jobs: int = typer.Option(8, help="concurrent downloads"),
) -> None:
    """Phase 2: download each kept URL and save its main text as markdown."""
    from mlh.parallel import pmap  # heavy import, only needed for this command

    outdir = outdir or default_outdir(domain)
    keep_file = keep_file or (outdir / "urls-keep.txt")
    if not keep_file.exists():
        raise typer.BadParameter(f"{keep_file} not found — run './mirror_site.py urls {domain}' first")

    urls_list = [u for u in keep_file.read_text().splitlines() if u.strip()]
    logger.info(f"fetching {len(urls_list)} urls with n_jobs={n_jobs}")
    df = pd.DataFrame(pmap(fetch_one, urls_list, prefer="threads", n_jobs=n_jobs))

    ok = df[df["status"] == "ok"]  # write markdown (IO, separated from the parallel fetch)
    for r in ok.itertuples():
        path = url_to_path(outdir, r.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.markdown)

    save_llms_txt(origin(domain), outdir)

    failures = df[df["status"].str.startswith("error")]
    if len(failures):
        (outdir / "failures.txt").write_text(
            "".join(f"{r.url}\t{r.status}\n" for r in failures.itertuples()))

    show_fetch(df)
    console.print(f"\nwrote [green]{len(ok)}[/] markdown files under [cyan]{outdir}/[/]")
    if len(failures):
        logger.warning(f"{len(failures)} urls FAILED — see {outdir}/failures.txt")


@app.command()
def clean(
    domain: str = typer.Argument(..., help="same site you fetched"),
    outdir: Path = typer.Option(None, help="output dir (default: <domain>-md)"),
) -> None:
    """Re-apply the deterministic cleanup to already-fetched markdown, in place.

    fetch already cleans each page as it writes it; this is the same transform exposed as a
    separate, idempotent stage so you can tighten the cleanup rules and re-run without
    re-downloading. Running it twice on the same files is a no-op.
    """
    outdir = outdir or default_outdir(domain)
    files = list(outdir.rglob("*.md"))
    if not files:
        raise typer.BadParameter(f"no .md files under {outdir} — run 'fetch {domain}' first")
    changed = 0
    for f in files:
        before = f.read_text()
        after = clean_markdown(before)
        if after != before:
            f.write_text(after)
            changed += 1
    console.print(f"cleaned [green]{changed}[/] of {len(files)} files under [cyan]{outdir}/[/] "
                  f"({len(files) - changed} already clean)")


if __name__ == "__main__":
    app()
