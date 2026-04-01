# tools
> Collection of CLI utilities for AI, search, document processing, email, and system administration.
`66 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| `oai` | OpenAI DSPy wrapper supporting system prompts and context truncation for LLM interactions |
| `ddgs` | DuckDuckGo web search with SQLite persistence and pandas DataFrame export |
| `ctx-tree`, `ctx-index`, `ctx-peek`, `ctx-skip`, `ctx-reset` | Context file management tools for progressive disclosure of codebase conventions |
| `mtui.py` | Gmail TUI (lazygit-style) using Textual, composes shell email tools (msearch, mget, mview) |
| `ocr_agent.py` | Vision API OCR orchestrator that reads `.claude/commands/ocr.md` for prompts |

## Conventions
- **Python shebang pattern**: All Python tools use `#!/usr/bin/env -S uv run --script` with inline uv dependencies in docstring block (lines 2-11)
- **Python tool style**: Use `typer` for CLI, `rich` for output, `pathlib.Path` for file paths, prefer functional style over try/except
- **Shell shebang**: Zsh tools use `#!/usr/bin/env zsh` with `set -e`; bash tools use `#!/bin/bash` with `# shellcheck shell=bash`
- **Sourcing convention**: Bash tools source helpers from `~/dotfiles/` subdirectories (e.g., `update_checks/update_functions.sh`)
- **Relative path assumptions**: Tools assume they're in `~/tools/` (symlinked from repo) and reference `~/.claude/`, `~/dotfiles/`, `~/.zshrc`
- **Command naming**: Lowercase with hyphens (e.g., `ctx-tree`, `update-packages`), no file extensions visible to users

## Gotchas
- **Python uv dependencies**: Must be declared in docstring block with exact formatting; typo in `requires-python` or missing commas breaks inline execution
- **Claude config paths hardcoded**: Tools like `ocr_agent.py` read from `~/.claude/commands/` — these paths are git-ignored and must exist locally
- **Symlink dependency**: Tools rely on being in `~/tools/` directory (via `setup.sh` symlink pass); running directly from repo path breaks relative imports
- **eza not tree**: Scripts use `eza --tree` with git-ignore flags; older `tree` command not guaranteed to exist
- **Email tools require notmuch**: Tools msearch, mget, mview, msend are thin wrappers around notmuch backend; they won't work without notmuch installation
