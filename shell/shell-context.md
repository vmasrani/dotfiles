# shell
> Zsh/bash configuration files with utilities for terminal UI, shell functions, and color schemes
`17 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| `.zshrc` | Main zsh entry point; sources zprezto, config files, and theme |
| `gum_utils.sh` | Terminal UI wrapper with semantic functions (success, error, warning, info) |
| `helper_functions.sh` | Shell utility functions (command_exists, tmux output tracking) |
| `.aliases-and-envs.zsh` | Aliases and environment variable definitions |
| `.paths.zsh` | PATH construction with deduplication |

## Patterns
- **Config chain**: `.zshrc` orchestrates sourcing of cascading config files in dependency order
- **Graceful fallback**: `gum_utils.sh` detects TTY and gum availability, falls back to plain text
- **Theme switching**: Detects SSH sessions and loads appropriate color scheme (gruvbox-dark SSH, palenight local)
- **Prezto integration**: Uses Zprezto for core zsh functionality

## Dependencies
- **External:** gum (terminal UI), zprezto (zsh framework), fzf (fuzzy finder), powerlevel10k (prompt)
- **Internal:** helper_functions.sh sourced by .zshrc; gum_utils.sh provides UI wrapper

## Entry Points
- `.zshrc` — main interactive shell config
- `.zshenv` — environment variables loaded before interactive shells
- `.zprofile` — login shell initialization
- `.bashrc`/`.bash_profile` — bash equivalents

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| themes | yes |
