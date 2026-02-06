# tools

_Last updated: 2026-01-27_

## Purpose
Symlinked CLI utilities for AI, web search, document processing, email management, and system administration. All tools use modern patterns: Python scripts use uv with inline dependencies; bash scripts use gum UI helpers and shell utility functions from the dotfiles repo.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| oai | OpenAI/DSPy LLM wrapper | `prompt_llm()` - supports system prompts, context truncation |
| ddgs | DuckDuckGo text search | `search()` - returns list of dicts, SQLite persistence |
| google_search | Google Custom Search API | `search_google_all()` - pagination, markdown/JSON output |
| print_csv | Rich CSV/data inspector | `overview_panel()`, `column_stats_table()` - infers types |
| pdf_extract_pages | PDF/EPUB page extraction | `extract_pages_from_pdf_bytes()`, EPUB→PDF conversion |
| summarize_url.py | URL content analyzer | Compact/full LLM-powered summaries via Tabstack |
| ocr_agent.py | OCR extraction agent | Reads Claude OCR commands, outputs markdown |
| mtui.py | Gmail TUI (Textual) | Lazygit-style email interface, composes shell tools |
| markdown_cleanup_agent.py | Parallel markdown processor | Uses `mlh.parallel.pmap` for OpenAI batch processing |
| update-packages | Package update checker | Sources `~/dotfiles/update_checks/update_functions.sh` |
| msearch, mget, mview, msend | Email CLI tools | Compose around notmuch backend + gum UI |

## Patterns
- **uv inline dependencies**: Python scripts declare deps in shebang comments, isolated per-tool
- **Dual-mode CLI**: Tools support piped input + arguments (e.g., `oai`, `ddgs`, `google_search`)
- **SQLite persistence**: Search/query tools optionally save results via `--db` flag
- **Output format flexibility**: Markdown, JSON, plain text modes
- **Rich/Textual UX**: Styled tables, panels, interactive data tables
- **Shell composition**: Python TUIs call shell tools (e.g., mtui calls msearch/mget/mview)
- **Gum UI fallbacks**: Shell scripts degrade to echo when gum unavailable (non-TTY)
- **Parallel processing**: Markdown/OCR agents use `mlh.parallel.pmap`

## Dependencies
- **External (Python)**: dspy, openai, ddgs, requests, pandas, sqlalchemy, pymupdf, pypdf, typer, rich, loguru, textual, pydantic, tabstack, ipdb
- **External (CLI)**: gum, notmuch, jq, rg, fzf, bat, helix, aws-cli, sshfs, fusermount, fswatch, git, curl, ssh, rsync
- **Internal**: gum_utils.sh, helper_functions.sh, update_functions.sh, ~/dotfiles/prompt_bank/ocr.md

## Entry Points
- **Python CLI tools**: oai, ddgs, google_search, print_csv, pdf_extract_pages, summarize_url.py, ocr_agent.py, mtui.py, markdown_cleanup_agent.py, check_limits.py
- **Bash script tools**: update-packages, rsync-all, run-command-on-all-addresses, system_info, copy, find_files, fzf-helix, rfz, tagger, mount_remotes, start_aws, stop_aws
- **Gmail CLI**: msearch, mget, mview, msend (each sources aws_common.sh)
- **Specialized utilities**: fetch_url, bypass_login, convert_ebook, watch_dir, sshget, rename_pdf, symlink_pdfs, transcript_to_markdown, split_by_size, colorize-columns

## Subdirectories
None — flat structure. Related directories referenced:
- `~/dotfiles/update_checks/` — update check functions
- `~/dotfiles/prompt_bank/` — OCR and cleanup prompt definitions
- `~/dotfiles/shell/` — gum_utils.sh, helper_functions.sh
