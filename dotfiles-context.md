# dotfiles
> Symlink-based dev environment automation for Linux/macOS; all config and tools are version-controlled and installed via setup.sh
`11 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| setup.sh | Main orchestrator that installs all tools and symlinks configs to $HOME; idempotent (safe to re-run) |
| install/install_functions.sh | Core install helpers: install_if_missing, install_if_dir_missing, install_on_brew_or_mac, install_dotfiles ~160 symlink pairs |
| shell/.zshrc | Entry point for zsh shell; sources helper scripts, aliases, environment variables, themes, and fzf config in strict order |
| maintained_global_claude/ | Source of truth for Claude Code configuration (agents, commands, hooks, skills, settings.json); symlinked to ~/.claude during setup |

## Conventions
- **Shell scripts target zsh**, not bash; use `set -e` and guard with helper functions (command_exists, move_and_symlink)
- **All install functions are idempotent** — safe to run setup.sh multiple times; install_if_missing/install_if_dir_missing check before installing
- **OS branching via $OS_TYPE**: detect in install_functions.sh as "mac" or "linux"; use install_on_brew_or_mac for cross-platform package installation
- **Symlink pairs in install_dotfiles** define what gets linked from repo into $HOME (e.g., shell/.zshrc → ~/.zshrc, maintained_global_claude/* → ~/.claude/*)
- **force_replace_targets array** ensures Claude configs always match repo (deletes stale symlink targets before replacing)
- **Terminal UI via gum_utils.sh** — all user-facing output uses gum_success/gum_error/gum_warning/gum_info instead of raw echo; falls back gracefully in non-TTY
- **local/ is git-ignored** — contains .local_env.sh (API keys), .secrets, machine-specific overrides; never add secrets to tracked files

## Gotchas
- **.zshrc sources file order matters** — Zprezto init first, then helper_functions.sh, then gum_utils.sh, then aliases/paths; sourcing out of order breaks downstream scripts
- **install_dotfiles runs chmod +x on all .sh files** — if you add a shell script to the repo, setup.sh will automatically make it executable
- **OS_TYPE detection happens in install_functions.sh, not .zshrc** — some tools fail silently if you run setup.sh in the wrong shell; always run setup.sh directly (./setup.sh), not via bash
- **Claude config symlinks are force-replaced** — if you edit ~/.claude directly, setup.sh will overwrite it next time; make changes in maintained_global_claude/ instead
- **macOS/Linux npm and yarn install differently** — install_on_brew_or_mac abstracts this; check install_functions.sh for package name differences per OS
