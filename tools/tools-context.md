# tools
> Collection of CLI utilities for AI, search, document processing, email, and system administration using modern patterns.
`46 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| oai | OpenAI/DSPy LLM wrapper with system prompts and context truncation |
| mtui.py | Gmail TUI (lazygit-style) using Textual, composes shell email tools |
| print_csv | Rich CSV/data inspector with type inference and statistics |
| msearch, mget, mview, msend | Email CLI tools around notmuch backend with gum UI |
| ctx-index | Build project map from *-context.md files with depth filtering |

## Patterns
- **uv inline dependencies**: Python scripts declare deps in shebang comments, isolated per-tool
- **Dual-mode CLI**: Tools support piped input + arguments
- **Shell composition**: Python TUIs call shell tools (e.g., mtui → msearch/mget/mview)
- **Rich/Textual UX**: Styled tables, panels, interactive data tables
- **Gum UI fallbacks**: Shell scripts degrade to echo when gum unavailable (non-TTY)
- **Parallel processing**: Agents use `mlh.parallel.pmap` for batch operations

## Dependencies
- **External (Python)**: dspy, openai, ddgs, requests, pandas, pymupdf, pypdf, typer, rich, loguru, textual, pydantic
- **External (CLI)**: gum, notmuch, jq, rg, fzf, bat, aws-cli, sshfs, git, curl, ssh, rsync
- **Internal**: gum_utils.sh, helper_functions.sh, ~/dotfiles/shell/

## Entry Points
- **Python CLI**: oai, ddgs, google_search, print_csv, pdf_extract_pages, mtui.py, markdown_cleanup_agent.py
- **Bash scripts**: update-packages, system_info, mount_remotes, start_aws, stop_aws
- **Gmail tools**: msearch, mget, mview, msend
- **Context tools**: ctx-index, ctx-peek, ctx-tree, ctx-skip, ctx-stale

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| .claude | no |
| .cursor | no |
| urls | no |
