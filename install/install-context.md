# install

## Purpose
Provides modular installation functions and entry points for setting up development tools, language servers, dotfiles, and environment configuration across macOS and Linux systems with OS-specific fallback chains.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| install_functions.sh | Core installation framework with 70+ tool installers and symlink management | `install_if_missing`, `install_on_brew_or_mac`, `install_with_fallback`, `install_dotfiles`, `ensure_symlink`, `OS_TYPE` |
| runpod_functions.sh | RunPod-specific bridge for ephemeral /root to persistent /workspace/home | `bridge_root_to_workspace` |
| install_helix_language_servers.sh | Installs language servers (markdown-oxide, yaml-language-server, bash-language-server, taplo, simple-completion-language-server, pyright) | N/A (direct npm/cargo calls) |
| install_tar.sh | Generic tar.gz/tar.xz extractor and binary linker to ~/bin | URL parameter; extracts and symlinks executables |
| install_npm.sh | NVM installation with LTS Node.js setup | N/A (nvm shell script) |
| install_htop.sh | Linux-specific htop build from source with autotools | Builds htop from repo, installs to ~/bin |
| install-parquet-tools.sh | Downloads and installs parquet-tools binary | Fetches v1.22.0 Linux binary from GitHub releases |

## Patterns

**Idempotent Installer Pattern:**
- `install_if_missing <cmd> <fn>` — Checks if command exists before calling install function
- `install_if_dir_missing <dir> <fn>` — Checks directory existence to avoid redundant installs
- All install functions follow convention: `install_<tool>` callable by name

**OS-Aware Fallback Chain:**
- `install_with_fallback <pkg> <snap_flags> <fallback_fn>` — Attempts apt → snap → fallback function (macOS defaults to brew)
- `install_on_brew_or_mac <linux_pkg> <mac_pkg>` — Simple abstraction for apt vs brew

**Symlink Management:**
- `ensure_symlink <source> <target> <force_link>` — Creates/validates symlinks with optional force-replace mode
- Force-replace targets: Claude/Codex config, agents, skills (always synced with repo)

**Modular Dotfile Linking:**
- `install_dotfiles [dotfiles_dir] [target_home]` — Declarative array of ~160 source:target pairs
- Supports custom home path for RunPod `/workspace/home` bridging
- Auto-creates parent directories and chmod+x all shell scripts

## Dependencies

**External:**
- `brew` (macOS package manager)
- `apt` (Linux package manager)
- `snap` (Linux fallback)
- `npm`, `cargo` (language-specific package managers)
- `git`, `wget`, `curl` (download/clone tools)
- `gum` (terminal UI — required by all scripts, fallback to plain text)
- Language servers: markdown-oxide, simple-completion-language-server, taplo-cli, yaml-language-server, vscode-langservers-extracted, bash-language-server, pyright

**Internal:**
- `../shell/helper_functions.sh` — `command_exists`, `move_and_symlink` utilities
- `../shell/gum_utils.sh` — `gum_success`, `gum_error`, `gum_warning`, `gum_info`, `gum_dim` terminal output functions
- Sourced by `setup.sh` and `setup_runpod.sh` as the orchestration engine

## Entry Points

- **`setup.sh`** (parent): Sources `install_functions.sh`, calls `install_if_missing` chains
- **`setup_runpod.sh`** (parent): Calls `install_dotfiles "$dotfiles_dir" "/workspace/home"` for RunPod persistence
- **`install_functions.sh`**: Primary entry point when sourced; exports 70+ install functions
- **`install_helix_language_servers.sh`**: Standalone executable for language server setup
- **`install_tar.sh`**: Reusable utility called by install functions (e.g., `install_bat`, `install_eza`)
- **`install_npm.sh`**: Dedicated NVM bootstrap script
- **`runpod_functions.sh`**: Exports `bridge_root_to_workspace`, called by boot guard to restore symlinks after pod restart

## Notable Implementation Details

- **~160 symlink pairs** in `install_dotfiles` covering shell, editors, Claude/Codex config, mutt, fzf, tmux
- **TPM (Tmux Plugin Manager)** auto-installation with Catppuccin theme
- **claude/codex force-replace array** ensures config always matches repo on re-runs
- **RunPod dual-layer architecture**: Phase A (install to /workspace), Phase B (bridge /root → /workspace/home), Phase C (install tools)
- **Binary download strategy**: nopme.in mirrors for Linux (tmux, rg, fd, jq), GitHub releases for specialized tools (bat, eza, parquet-tools)
- **Email stack setup** (neomutt + isync + msmtp + notmuch) with pm2 background sync
