# dotfiles
> Dev environment automation repo — tools, shell config, Claude AI config, and editors symlinked into `$HOME` via `setup.sh`.
`8 files | 2026-04-05`

| Entry | Purpose |
|-------|---------|
| `setup.sh` | Idempotent orchestrator: installs all tools and runs `install_dotfiles` to symlink everything into `$HOME`. Re-runnable safely. |
| `CLAUDE.md` | Project-level instructions for Claude Code — architecture notes, symlink map, and conventions. Read this before editing anything. |
| `AGENTS.md` | Agent-specific guidance for automated agents working in this repo. |
| `lefthook.yml` | Git hook config (lefthook). Currently untracked — check if hooks need registering after clone. |
| **install/** | Core installation helpers and one-off install scripts orchestrated by `setup.sh` at the repo root. |
| **shell/** | Zsh configuration hub: rc files, aliases, path management, terminal UI wrappers, and helper functions sourced at shell startup. |
| **maintained_global_claude/** | Version-controlled source of truth for Claude Code configuration — symlinked to `~/.claude/` on setup. |
| **tools/** | CLI utilities symlinked to `~/tools/` — AI wrappers, data processing, URL summarization, and the ctx-* context file system. |
| **tmux/** | Tmux config with Catppuccin/powerkit status bar, vi-mode, popup sessions, and Claude API usage widgets. |
| **editors/** | Helix editor config (theme, LSP, keybindings) and a legacy vim config, symlinked into `~/.config/helix/` by setup.sh. |
| **preview/** | FZF preview scripts for 30+ file types (data, ML, docs, images, archives) symlinked to `~/bin/`. |
| **linters/** | Universal linter dispatcher and config files for Python, JS/TS, shell, and Rust — used as fallback configs project-wide. |
| **listeners/** | Background file-watchers that auto-process Downloads: PDFs get renamed, ebooks get converted on arrival. |
| **mutt/** | Neomutt email client config for Gmail: local Maildir sync via mbsync, sent via msmtp, indexed by notmuch. |
| **iterm2/** | iTerm2 profiles, keybindings, window arrangements, and SSH theme switcher for macOS terminal configuration. |
| **fzf/** | FZF shell integration and keybinding config sourced by `.zshrc`. |
| **prompt_bank/** | Collection of reusable LLM system prompts for specific tasks: file renaming, OCR transcription, and transcript cleanup. |
| **update_checks/** | Shell library for checking outdated packages across brew, apt, cargo, npm, uv, and pip with file-based caching. |
| **vscode/** | VSCode profiles for Python, Markdown, and LaTeX workflows — exported as `.code-profile` JSON blobs for manual import. |
| **wip/** | Scratch area for experimental and in-progress work — iMessage extraction scripts, tmux config experiments, and GitHub parallel-dev process docs. |
| **unused/** | Graveyard of retired scripts and configs kept for reference but not symlinked or sourced anywhere. |
| **local/** | Machine-specific secrets and overrides (git-ignored): `.local_env.sh`, `.secrets`, `.mutt_secrets`. |

<!-- peek -->

## Conventions

- **Never edit `~/.claude/` directly** — `maintained_global_claude/` is the source of truth, symlinked on setup. Changes to agents, commands, hooks, skills, or `settings.json` go there.
- **Adding a new tool to setup**: Write `install_<tool>` in `install/install_functions.sh`, then add `install_if_missing <cmd> install_<tool>` in `setup.sh`. Do not add logic directly to `setup.sh`.
- **Shell scripts**: Use `gum_utils.sh` functions (`gum_success`, `gum_error`, etc.) for all user-facing output — never raw `echo`. Functions fall back to plain text in non-TTY contexts.
- **OS branching**: Use `install_on_brew_or_mac` or check `$OS_TYPE` for platform differences. Never use `apt` or `brew` directly in install functions.
- **Commit style**: Imperative one-liners, group related changes (`fix tmux theme`, `add helix bindings`).

## Gotchas

- `local/` is git-ignored and must be created manually on new machines via `install_local_dotfiles`. The setup script checks for it with `install_if_dir_missing`.
- `force_replace_targets` in `install/install_functions.sh` causes certain symlinks (Claude/Codex configs) to be deleted and re-created on every `setup.sh` run — intentional to keep them in sync.
- `lefthook.yml` is currently untracked (shown in git status). Run `lefthook install` after clone if hooks are needed.
- The `install_dotfiles` function defines ~160 source→target pairs inline — the symlink map is not auto-discovered, so adding a new file requires explicitly adding a pair there.
- `tmp/` and `logs/` are working directories, not config — don't symlink or commit contents.
