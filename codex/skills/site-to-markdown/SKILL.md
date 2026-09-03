---
name: site-to-markdown
description: Mirror an entire website/domain to clean local markdown by reading its sitemaps, in two auditable phases (enumerate every URL → download kept pages as markdown). Use this skill whenever the user wants to archive, mirror, scrape, crawl, or download a website or its docs/blog to markdown or text — for offline reading, feeding docs into an LLM/RAG, building a knowledge base, or competitor research. Trigger on phrases like "mirror this site", "scrape example.com to markdown", "download all the docs", "archive this website", "grab every page from <domain>", "convert this site to markdown/text", "get a competitor's site as markdown", "make an offline copy of these docs", or any mention of a site's sitemap or llms.txt. Prefer this over hand-rolling wget/curl/BeautifulSoup — it handles sitemap indexes, bot/edge protection (Cloudflare/Vercel 403s), and boilerplate stripping that naive crawls get wrong.
---

# Site → Markdown

Mirror any website to clean markdown using the site's own **sitemaps** as the source of truth, so the process is complete and auditable rather than a best-effort link crawl.

Everything runs through one bundled script: **`scripts/mirror_site.py`** (a self-contained `uv run` script — dependencies install automatically on first run). Invoke it by its absolute path from this skill's directory, e.g. `~/.codex/skills/site-to-markdown/scripts/mirror_site.py`.

The whole pipeline is **deterministic** — `curl_cffi` fetch → `trafilatura` rule-based extraction → regex cleanup → write. No LLM is involved in fetching, converting, or cleaning, so re-running on unchanged pages reproduces byte-identical markdown.

## Why sitemaps, not crawling

A naive `wget`/`curl` crawl starts at the homepage and follows links. Two things break it: many sites return **403 Forbidden** to non-browser clients (so the crawl discovers *nothing* and silently "succeeds" with almost no pages), and JS-rendered nav means links aren't in the initial HTML. Reading the site's published sitemaps sidesteps both — it's the site telling you every URL it wants indexed. The script fetches with a real Chrome TLS+header fingerprint (`curl_cffi` impersonation), which clears the common Cloudflare/Vercel edge blocks that a mere User-Agent string does not.

If a site publishes **no** sitemap (some SPAs/landing pages don't), the script says so loudly and stops — it does not fall back to crawling. That's the honest outcome; tell the user the site isn't sitemap-mirrorable rather than pretending otherwise.

## The workflow — two phases, with a human audit in between

The whole point is that the user **sees and approves the URL list before anything is downloaded**. Don't collapse the two phases; run phase 1, help them audit, then run phase 2.

### Phase 1 — enumerate URLs

```
<script> urls <domain>
```

- `<domain>` is bare like `example.com` (no scheme needed).
- Auto-discovers common content subdomains (`docs.`, `blog.`, `help.`, `support.`, `developer.`, `learn.`) that have their own sitemaps. Add more by hand with `--host docs.example.com` (repeatable). Disable probing with `--no-probe`.
- Writes into `./<domain>-md/`: `urls.txt` (all), `urls-keep.txt`, `urls-drop.txt` (with reasons), `urls.csv` (full annotated table), and prints a category summary table.

**Then present the summary to the user and help them audit**, because keep/drop is a best-effort heuristic (it drops obvious asset files and taxonomy/archive pages like `/category/`, `/author/`, `/tag/`, but can't know every site's junk). Look especially for:
- **Locale duplicates** — e.g. a `/jp/`, `/fr/`, `/de/` category that mirrors the English content. Usually the user wants only one language.
- **High-volume low-value categories** — press-release wires, `/videos/`, event pages. Great to drop if the user only wants docs + blog.
- **Anything in `urls-drop.txt` that's actually wanted** — surface it so they can rescue it.

To trim, the user (or you, on their behalf) either edits `urls-keep.txt` directly (it's just one URL per line) or narrows scope by re-running with `--host`. `urls-keep.txt` is what phase 2 reads, so editing it is the audit knob.

### Phase 2 — fetch as markdown

```
<script> fetch <domain>
```

- Reads `./<domain>-md/urls-keep.txt` by default (override with `--keep-file <path>`).
- Downloads each URL concurrently (`--n-jobs N`, default 8) and extracts the **main text** as markdown via `trafilatura` — no nav, sidebars, cookie banners, or JS. Each file gets a YAML frontmatter block (title, author, date, description) where the page provides it.
- Runs a **deterministic cleanup pass** on every page (`clean_markdown`): strips trafilatura's heading-anchor cruft (`## Title[⚓︎](…)` → `## Title`), trims trailing whitespace, and collapses blank-line runs.
- Writes `./<domain>-md/<host>/<path>.md`, mirroring the URL structure. Also grabs `/llms.txt` if the site publishes one (a curated overview — handy context).
- Pages with no extractable prose come back `empty` and are skipped; real HTTP/network failures are written to `failures.txt` and reported in a loud summary. If there are failures, tell the user the count and that they can re-run — don't bury it.

### Optional — re-clean without re-downloading

```
<script> clean <domain>
```

`fetch` already cleans each page as it writes it, so you normally don't need this. It exists because cleanup is a pure, deterministic transform kept separate from the network stage: if you tighten the cleanup rules (in `clean_markdown` / the `ANCHOR_*` regexes), run `clean` to re-apply them to the existing `<domain>-md/` tree in place — no re-fetching. It's idempotent (running twice changes nothing) and reports how many files it touched.

## Running it

- Run from the directory where the user wants the `<domain>-md/` output (usually their current project). Confirm the target directory if it's ambiguous.
- For a large site (thousands of pages), say so after phase 1 and let the user decide scope before the fetch — mirroring 5,000 pages is slower and noisier than they may want.
- `<script> urls --help` / `<script> fetch --help` list all flags.

## Good defaults to remember

- Always do phase 1 and show the user the table before fetching. The audit is the feature, not a formality.
- When the user's goal is narrow ("just the docs"), point `urls` at the docs host directly (`<script> urls docs.example.com --no-probe`) instead of mirroring the whole marketing site.
- Never try to defeat a hard bot challenge (login walls, interactive CAPTCHAs) — if `curl_cffi` impersonation still gets blocked, report it plainly rather than escalating.
