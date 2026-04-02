# dotfiles
> Dev environment automation repo — tools, shell config, Claude AI config, and editors symlinked into `$HOME` via `setup.sh`.
`7 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `setup.sh` | Master installer — idempotent orchestrator; run once to install all tools and create symlinks |
| `CLAUDE.md` | Project-level Claude instructions; authoritative source of architecture and conventions |
| `AGENTS.md` | Agent-specific guidance for this repo |
| **shell/** | `.zshrc` chain source files: aliases, paths, helper functions, gum UI wrappers, colors |
| **install/** | Core installation helpers and one-off install scripts orchestrated by `setup.sh` |
| **maintained_global_claude/** | Source of truth for `~/.claude/` — agents, commands, hooks, skills, settings |
| **tmux/** | `.tmux.conf` + status bar scripts, agent session management, TPM plugins |
| **editors/** | Helix editor config (theme, LSP, keybindings) and legacy vim config, symlinked into `~/.config/helix/` |
| **tools/** | CLI utilities symlinked to `~/tools/` — AI wrappers, data processing, URL summarization, ctx-* system |
| **fzf/** | Fuzzy finder config and key bindings for shell integration |
| **preview/** | FZF preview scripts for 30+ file types symlinked to `~/bin/` |
| **linters/** | Linter configs for shellcheck and other tools |
| **listeners/** | Background file-watchers that auto-process Downloads on arrival |
| **iterm2/** | iTerm2 profiles and SSH-triggered themes |
| **mutt/** | Mutt email client config with accounts, isync, msmtp, notmuch, and scripts |
| **update_checks/** | Shell library for checking outdated packages across multiple package managers |
| **prompt_bank/** | Reusable LLM system prompts for file renaming, OCR, and transcript cleanup |
| **codex/** | Codex-related config |
| **vscode/** | VSCode profiles for Python, Markdown, and LaTeX workflows |
| **wip/** | Scratch area for experimental and in-progress work |
| **unused/** | Graveyard of retired scripts and configs |

<!-- peek -->

## Conventions

- **Never edit `~/.claude/` directly** — `maintained_global_claude/` is the source of truth, symlinked in by `setup.sh`. Changes outside this repo will be overwritten on next setup run.
- **`force_replace_targets` array** in `install/install_functions.sh` causes certain targets (Claude/Codex configs) to be deleted and re-symlinked on every `setup.sh` run, not just when missing.
- **Adding a new tool**: write `install_<tool>` in `install/install_functions.sh`, then add `install_if_missing <cmd> install_<tool>` line in `setup.sh`. Do not add install logic directly in `setup.sh`.
- **Shell scripts must use `gum_utils.sh` functions** (`gum_success`, `gum_error`, `gum_info`, etc.) for all user-facing output — raw `echo` is non-standard here.
- Python tools in `tools/` use `#!/usr/bin/env -S uv run --script` shebang with inline dependency declarations.

## Gotchas

- `setup.sh` uses `set -e` and `cd "$(dirname "$0")"` — must be run from any location, not necessarily from the repo root, but the CWD is reset to repo root at line 12.
- Symlinks from `tools/*` go to `~/tools/` (entire directory), not `~/bin/`. Preview scripts go to `~/bin/`. Mixing these up breaks PATH resolution.
- `local/` is git-ignored and must be created separately (`install_local_dotfiles`). It holds API keys in `.local_env.sh` — without it, many tools silently lack credentials.
- `shell/.zshrc` sources `.local_env.sh` last in the chain; missing keys don't error but tools using them will fail at runtime.
- tmux plugins require TPM already installed before `setup.sh` runs `install_plugins` — the script handles this but order matters in `setup.sh`.
