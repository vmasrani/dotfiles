# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Dotfiles repository automating dev environment setup across Linux and macOS. Everything is symlinked from this repo into `$HOME` via `setup.sh`.

## Key Commands

```bash
./setup.sh                             # Full install + symlink pass (idempotent, safe to re-run)
source ~/.zshrc                        # Reload shell config (alias: refresh)
shellcheck setup.sh install/*.sh       # Lint shell scripts
```

## Architecture

### How Installation Works

`setup.sh` orchestrates everything by sourcing `install/install_functions.sh`, which provides:

- **`install_if_missing <cmd> <fn>`**: Skips if command already exists, otherwise calls the install function
- **`install_if_dir_missing <dir> <fn>`**: Skips if directory exists
- **`install_on_brew_or_mac <pkg>`**: Abstracts `apt` (Linux) vs `brew` (macOS) via `OS_TYPE` detection
- **`install_dotfiles`**: Creates all symlinks from this repo into `$HOME`

**To add a new tool**: Write an `install_<tool>` function in `install/install_functions.sh`, then add an `install_if_missing` line in `setup.sh`.

### Symlink System

`install_dotfiles` in `install/install_functions.sh` defines ~160 source→target pairs. Key mappings:

| Source | Target |
|--------|--------|
| `shell/.zshrc` | `~/.zshrc` |
| `shell/.aliases-and-envs.zsh` | `~/.aliases-and-envs.zsh` |
| `shell/.paths.zsh` | `~/.paths.zsh` |
| `tmux/.tmux.conf` | `~/.tmux.conf` |
| `editors/hx_config.toml` | `~/.config/helix/config.toml` |
| `editors/hx_languages.toml` | `~/.config/helix/languages.toml` |
| `tools/*` | `~/tools/` (entire directory) |
| `preview/*.sh` | `~/bin/` |
| `maintained_global_claude/agents` | `~/.claude/agents/` |
| `maintained_global_claude/commands` | `~/.claude/commands/` |
| `maintained_global_claude/hooks` | `~/.claude/hooks/` |
| `maintained_global_claude/skills` | `~/.claude/skills/` |
| `maintained_global_claude/settings.json` | `~/.claude/settings.json` |

The `force_replace_targets` array ensures Claude/Codex configs always match the repo (deletes stale targets before re-symlinking).

### Shell Configuration Chain

`.zshrc` sources files in this order:
1. Zprezto init (`~/.zprezto/init.zsh`)
2. `shell/helper_functions.sh` — utility functions (`command_exists`, `move_and_symlink`, etc.)
3. `shell/gum_utils.sh` — terminal UI wrappers with non-TTY fallback
4. `shell/lscolors.sh` — color scheme definitions
5. `shell/.aliases-and-envs.zsh` — all aliases and env vars
6. `local/.local_env.sh` — API keys and secrets (git-ignored)
7. `shell/.paths.zsh` — PATH construction with dedup
8. `fzf/.fzf-config.zsh` — fuzzy finder config
9. Powerlevel10k prompt (`~/.p10k.zsh`)

### Terminal UI: gum_utils.sh

All shell scripts should use these functions for user-facing output instead of raw `echo`:

```bash
gum_success "Done"          # Green ✓
gum_error "Failed"          # Red ✗ with border
gum_warning "Caution"       # Orange ⚠
gum_info "Starting..."      # Magenta →
gum_dim "Already installed" # Gray dimmed
gum_spin_quick "Loading..." cmd args  # Spinner
gum_confirm "Continue?"     # Interactive yes/no
```

All functions fall back to plain text when gum is unavailable or in non-TTY contexts.

### Claude AI Config Management

`maintained_global_claude/` is the source of truth for Claude Code configuration. It is version-controlled here and symlinked into `~/.claude/` during setup. Subdirectories:

- `agents/` — Agent definitions (e.g., structural-completeness-reviewer)
- `commands/` — Custom slash commands
- `hooks/` — Event-driven shell scripts
- `skills/` — Custom skill definitions
- `settings.json` — Global Claude settings

Changes to Claude config should be made in `maintained_global_claude/`, never directly in `~/.claude/`.

### tools/ Directory

CLI utilities (bash and Python) symlinked to `~/tools/`. Python scripts use uv inline dependencies with the shebang `#!/usr/bin/env -S uv run --script`. Key tools include AI wrappers (`oai`, `ddgs`, `google_search`), data processing utilities (`print_csv`, `pdf_extract_pages`), and system helpers.

### tmux Architecture

`tmux/.tmux.conf` with supporting scripts in `tmux/scripts/`:
- Vi-mode navigation, popup windows (`L` for sidepanel, `F11` for agents)
- Status bar scripts (`cpu_status.sh`, `ram_status.sh`, `agents_count.sh`, etc.)
- Agent session management with dynamic pane titles
- Plugins via TPM: tmux-sensible, extrakto, fzf-pane-switch

### Secrets and Local Overrides

`local/` is git-ignored. Contains `.local_env.sh` (API keys), `.secrets`, and `.mutt_secrets`. Machine-specific overrides go here, never in tracked files.

### RunPod Support

RunPod pods have ephemeral `/root` but persistent `/workspace`. The dotfiles support this via a two-layer approach:

1. **`setup_runpod.sh`** — Alternative entry point (instead of `setup.sh`):
   - Phase A: Installs dotfiles into `/workspace/home` (persistent across pod restarts)
   - Phase B: Bridges `/root` -> `/workspace/home` via symlinks
   - Phase C: Installs tools

2. **Boot guard** (`shell/runpod_boot_guard.sh`) — Sourced from `.zshrc`/`.bashrc` on every shell start. Re-establishes the `/root` -> `/workspace/home` bridge after pod restarts. No-op on non-RunPod machines (guard: `[[ -d "/workspace/home" ]]`).

3. **`install/runpod_functions.sh`** — Contains `bridge_root_to_workspace()` which creates force-mode symlinks for directories and dotfiles from `/root` to `/workspace/home`.

**RunPod workflow:**
```bash
# First time on a new pod:
git clone https://github.com/vmasrani/dotfiles.git /workspace/dotfiles
cd /workspace/dotfiles && ./setup_runpod.sh
exec zsh

# After pod restart (automatic via boot guard, or manual):
# Just open a new shell — the boot guard re-bridges automatically
```

Key design: `install_dotfiles()` accepts optional `[dotfiles_dir] [target_home]` args, defaulting to `$HOME/dotfiles` and `$HOME`. This keeps `setup.sh` backward-compatible while allowing `setup_runpod.sh` to target `/workspace/home`.

## Conventions

- **Shell scripts**: Target zsh, use `set -e`, guard with helpers from `helper_functions.sh`, use lowercase-hyphen CLI names (`update-packages`)
- **Idempotency**: All install scripts and setup.sh must be safe to run multiple times
- **OS branching**: Use `install_on_brew_or_mac` or check `$OS_TYPE` for platform-specific logic
- **Commit style**: Imperative one-liners (`fix tmux theme`, `add helix bindings`), group related changes