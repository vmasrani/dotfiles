# Dotfiles

_Last updated: 2026-01-27_

## Purpose

Comprehensive dotfiles repository automating development environment setup across Linux and macOS. All configurations are version-controlled and symlinked into `$HOME` via idempotent setup scripts. Includes shell configuration, editor configs, development tools, tmux/terminal setup, and Claude Code agent definitions.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| `setup.sh` | Main orchestrator (macOS/Linux) | Calls install_functions; installs 50+ tools; creates ~160 symlinks |
| `setup_runpod.sh` | RunPod-specific entry point | Three-phase setup: dotfiles → persistent storage, bridge `/root` → `/workspace/home`, install tools |
| `install/install_functions.sh` | Core installation library (892 lines) | `install_if_missing`, `install_if_dir_missing`, `install_on_brew_or_mac`, `install_dotfiles`, `ensure_symlink` |
| `shell/.zshrc` | Main zsh config (106 lines) | Zprezto init, sources helper funcs, gum_utils, aliases, paths, fzf, Powerlevel10k |
| `shell/.aliases-and-envs.zsh` | Aliases and environment (122 lines) | Command shortcuts, env vars, PATH entries |
| `shell/helper_functions.sh` | Zsh/bash utilities | `command_exists`, `move_and_symlink`, `file_count`, `remove_broken_symlinks`, `uwu` |
| `shell/gum_utils.sh` | Terminal UI wrappers | `gum_success`, `gum_error`, `gum_warning`, `gum_info`, `gum_dim`, `gum_spin_quick`, `gum_confirm` |
| `tmux/.tmux.conf` | Tmux config (302 lines) | Vi-mode, popup windows, status bar, TPM plugins, Catppuccin theme |
| `maintained_global_claude/settings.json` | Claude Code global config | Permissions, hooks, enabled plugins, environment variables |
| `CLAUDE.md` | Project guidelines | Architecture overview, conventions, symlink mappings, RunPod workflow |
| `tools/ctx-tree` | Directory tree visualization | Tree view with gitignore respecting via eza |
| `tools/ctx-peek` | Context file preview | Shows first few lines of *-context.md files |
| `tools/ctx-stale` | Stale context detection | Identifies outdated context files in repo |

## Patterns

**Idempotent Installation**: All install scripts check for existing installations via `install_if_missing` and `install_if_dir_missing`, allowing safe re-runs.

**Modular Shell Configuration**: Shell config sourced in fixed order (Zprezto → helpers → gum → aliases → paths → fzf → prompt), enabling flexible extension.

**Graceful Fallback**: `gum_utils.sh` detects TTY/non-TTY and env variables; falls back to plain text when gum unavailable.

**Cross-Platform Abstraction**: `install_on_brew_or_mac` and `install_with_fallback` handle macOS (brew) vs Linux (apt/snap) differences, with fallback chains.

**Symlink-Based Configuration**: ~160 symlinks from repo into `$HOME`, ensuring configs always sync to repo. `force_replace_targets` array ensures Claude/Codex configs overwrite stale symlinks.

**RunPod Ephemeral Bridge**: Two-layer approach bridges ephemeral `/root` to persistent `/workspace/home`. Boot guard on every shell start re-establishes links after pod restarts.

**Hook-Based Claude Integration**: Settings.json defines hooks (PostToolUse, Stop, SubagentStop, SessionStart, PreCompact) that execute Python scripts via uv.

## Dependencies

**External:**
- **Package managers**: brew (macOS), apt (Linux), snap (Linux fallback)
- **Shell frameworks**: Zprezto (zsh framework with themes/plugins), Powerlevel10k (zsh prompt)
- **Terminal UI**: gum (Charm), fzf (fuzzy finder), tmux (multiplexer), TPM (tmux plugin manager)
- **Dev tools**: Node.js/nvm, Rust/cargo, Go, Python/uv, Bun
- **Editors**: Helix (hx), Vim, VS Code, Cursor
- **CLI utilities**: lazygit, lazydocker, btop, bat, eza, rg, fd, jq, yq, csvkit, parquet-tools
- **Language servers**: Bash LSP, YAML LSP, Markdown LSP, HTML/CSS LSP
- **Email**: NeoMutt, isync, msmtp, notmuch
- **AI/Code**: Claude Code CLI, Codex CLI

**Internal:**
- `shell/` modules source each other (helper_functions.sh → gum_utils.sh → aliases/paths)
- `install/install_functions.sh` sources `shell/helper_functions.sh` and `shell/gum_utils.sh`
- `setup_runpod.sh` imports `install/runpod_functions.sh` for `/root` → `/workspace/home` bridging
- `maintained_global_claude/` symlinked to `~/.claude/` during setup (agents, commands, hooks, skills)

## Entry Points

- **`./setup.sh`** — Main entry point for macOS/Linux; orchestrates all installations and symlinks
- **`./setup_runpod.sh`** — RunPod entry point; three-phase setup with persistent storage bridging
- **`source ~/.zshrc`** — Shell initialization; sources all config files in defined order
- **Tools**: 55+ executable files in `/tools/` symlinked to `~/tools/` (bash/Python scripts with inline uv dependencies, including ctx-tree, ctx-peek, ctx-stale for context file management)
- **Tmux**: `~/.tmux.conf` with scripts in `/tmux/scripts/` for status bar, CPU, RAM, agent session management
- **Claude agents**: `maintained_global_claude/agents/` contains 5 agent definitions (codebase-researcher, spec-interviewer, plan-writer, context-researcher, structural-completeness-reviewer)

## Subdirectories

| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| `shell/` | Zsh/bash configs, helpers, colors, initialization | No |
| `install/` | Installation functions and RunPod-specific helpers | No |
| `editors/` | Helix config, Vim config, language settings | No |
| `tools/` | 50+ CLI utilities (Python + bash) for AI, data processing, system helpers | No |
| `tmux/` | Tmux config and status bar/session management scripts | No |
| `fzf/` | Fuzzy finder configuration and environment variables | No |
| `preview/` | File preview scripts (Feather, NPY, PyTorch, Parquet) | No |
| `linters/` | Pylint, Pyright, Sourcery configs | No |
| `listeners/` | File watching scripts for PDFs/ebooks in Downloads | No |
| `mutt/` | NeoMutt email client config (accounts, keys, scripts, isync, msmtp, notmuch) | No |
| `maintained_global_claude/` | Source of truth for Claude Code config; symlinked to `~/.claude/` | Yes (plugins/CLAUDE.md) |
| `maintained_global_claude/agents/` | Agent definitions (researcher, interviewer, plan-writer, etc.) | No |
| `maintained_global_claude/commands/` | Custom Claude Code slash commands | No |
| `maintained_global_claude/hooks/` | Event-driven scripts (PostToolUse, Stop, SessionStart, etc.) | No |
| `maintained_global_claude/skills/` | Custom skill definitions | No |
| `iterm2/` | iTerm2 terminal emulator profiles | No |
| `vscode/` | VS Code settings and extensions | No |
| `local/` | Git-ignored secrets, API keys, machine-specific overrides | No |
| `update_checks/` | Package update detection and management | No |
| `tabstack_comparison/` | Benchmark comparison project (Python) | No |
| `unused/` | Deprecated or archived configurations | No |
| `wip/` | Work-in-progress experiments | No |
| `tmp/` | Temporary working directory | No |

## Notable Architecture Decisions

**OS Detection**: `setup.sh` and `install_functions.sh` detect `$OSTYPE` and set `OS_TYPE` (mac/linux) for conditional tool installation.

**Symmetric Symlink System**: `install_dotfiles()` function in `install_functions.sh` accepts optional parameters `[dotfiles_dir] [target_home]`, defaulting to `$HOME/dotfiles` and `$HOME`. This enables both standard setup (`./setup.sh`) and RunPod setup (`./setup_runpod.sh /workspace/dotfiles /workspace/home`).

**Terminal UI Abstraction**: `gum_utils.sh` replaces all raw `echo` statements with semantic functions (gum_success, gum_error, etc.), with automatic fallback to plain text in non-TTY contexts (cron, launchd, pipes).

**Claude Config as Version-Controlled Source**: `maintained_global_claude/` is the authoritative source for Claude Code settings, agents, commands, hooks, and skills. Changes made directly in `~/.claude/` are overwritten during setup. Settings.json defines hooks that execute Python scripts via `uv run`.

**RunPod Ephemeral-to-Persistent Bridge**: Boot guard (`shell/runpod_boot_guard.sh`) sourced from `.zshrc` on every shell start re-establishes symlink bridge from `/root` to `/workspace/home`, automatically recovering after pod restarts.
