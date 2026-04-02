# tools
> CLI utilities symlinked to `~/tools/` — AI wrappers, data processing, URL summarization, and the ctx-* context file system.
`57 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `oai` | OpenAI/DSPy CLI wrapper — pipe text in, get LLM response; reads system prompt from file via `--sysprompt` |
| `google_search` | Google search CLI backed by SQLite cache (`results.db`) to avoid redundant API calls |
| `ddgs` | DuckDuckGo search CLI, same caching pattern as `google_search` |
| `fetch_url` | Fetch and render a URL via `tabstack` — dependency for `summarize_url.py` |
| `summarize_url.py` | AI-powered URL summarizer using `tabstack` + Pydantic models; imports from `url_renderers.py` and `summarize_url_models.py` |
| `url_renderers.py` | Rendering helpers (`render_overview`, `render_one_pager`, `render_report`) imported by `summarize_url.py` — not standalone |
| `summarize_url_models.py` | Pydantic models and system prompts for `summarize_url.py` — not standalone |
| `print_csv` | Rich-formatted CSV/Parquet viewer; caps at 40 rows and 2MB sample for safety |
| `pdf_extract_pages` | Extract page ranges from PDFs to stdout or file |
| `update-packages` | Frontend to `update_checks/update_functions.sh`; wraps check/show/refresh actions |
| `ctx-index` | Build project map from `*-context.md` files — one summary line per directory |
| `ctx-peek` | Preview `*-context.md` files without full load; no-args = current dir only, explicit dir = dir + children |
| `ctx-stale` | Find dirs with missing or outdated context files (stale = any sibling newer than context file) |
| `ctx-tree` | Directory tree via `eza --tree`; used internally by the ctx-* system |
| `ctx-reset` | Remove all `*-context.md` files under a directory |
| `ctx-skip` | Mark a context file with SKIP so `/research` won't overwrite it |
| `aws_common.sh` | Shared AWS helpers sourced by `start_aws` and `stop_aws` — not standalone |
| `mtui.py` | Textual TUI for email (mutt-like); depends on `mtui_models.py` and `mtui_styles.tcss` |
| `ocr_agent.py` | AI OCR pipeline; `ocr_agent.sh` is the shell wrapper |
| `automate.py` | Browser automation helper |
| `tagger` | File tagging utility |
| `transcript_to_markdown` | Convert audio/video transcripts to clean markdown |
| `claude-session-digest` | Summarize Claude session logs |
| `copy-last-output` | Copy last terminal output to clipboard |
| `media-stack-backup` | Backup media stack config |
| `media-stack-status` | Show media stack service status |
| `media-stack-watchdog` | Restart failed media stack services |
| `sync-qbit-port` | Sync qBittorrent port with VPN |
| **urls/** | Subdirectory — likely URL-related helpers or cache (no context file yet) |

<!-- peek -->

## Conventions

- All Python scripts use the uv inline script shebang (`#!/usr/bin/env -S uv run --script`) with `# /// script` dependency declarations — no virtualenv needed, run directly.
- Several Python files are **modules, not entrypoints**: `url_renderers.py`, `summarize_url_models.py`, `mtui_models.py`, `aws_common.sh`. They are imported/sourced by sibling scripts. Do not run them directly.
- Shell scripts source `~/dotfiles/shell/gum_utils.sh` for styled output — they use `gum_*` functions for all user-facing messages.
- `results.db` (SQLite) is the shared search cache for `google_search` and `ddgs`. It persists between runs; delete it to force fresh results.
- The entire `tools/` directory is symlinked as-is into `~/tools/` by `install_dotfiles` in `install/install_functions.sh`. Editing any file here affects the live tool immediately.

## Gotchas

- `summarize_url.py` imports `url_renderers` and `summarize_url_models` by relative name — it must be run from the `tools/` directory (or `~/tools/`) where those modules are co-located, otherwise it fails with an import error.
- `update-packages` is a thin wrapper; the real logic lives in `update_checks/update_functions.sh`. Editing just this file won't change behavior.
- `ctx-stale` defines "stale" as any sibling file newer than the context file — a `results.db` write or `.DS_Store` touch will mark a directory stale even if code hasn't changed.
- `__pycache__/` contains `.pyc` files for the Python modules. These are in the symlinked live directory and may cause confusion if Python version changes.
