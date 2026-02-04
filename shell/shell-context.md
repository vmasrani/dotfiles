# Shell Configuration Directory

## Purpose
Central location for zsh and bash initialization, configuration, and utility functions. Orchestrates the complete shell environment setup including prompt configuration (Powerlevel10k), aliases, PATH management, and terminal UI utilities. Supports both standard Linux/macOS and RunPod ephemeral container environments.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| .zshrc | Main zsh initialization script | EDITOR, VISUAL, PAGER, KEYTIMEOUT |
| .aliases-and-envs.zsh | All shell aliases and environment variables | Aliases for ls, navigation, git, tools; TABSTACK_API_KEY |
| helper_functions.sh | Utility functions for shell operations | command_exists(), move_and_symlink(), file_count(), remove_broken_symlinks() |
| gum_utils.sh | Terminal UI wrapper with graceful fallback | gum_success(), gum_error(), gum_warning(), gum_info(), gum_spin_quick(), gum_confirm() |
| .paths.zsh | PATH construction and environment setup | PATH (deduplicated), NVM_DIR, BAT_THEME, HTOP_FILTER |
| runpod_boot_guard.sh | RunPod ephemeral storage bridge | Restores /root -> /workspace/home symlinks on pod restart |
| .zpreztorc | Prezto framework configuration | Prompt theme (powerlevel10k), history, modules, keybindings |
| lscolors.sh | Terminal color scheme (LS_COLORS) | LS_COLORS (256 color definitions) |
| .zshenv | Zsh environment variables (non-login) | LANG, fpath additions |
| .zprofile | Zsh login shell initialization | PATH deduplication, cargo env sourcing |
| .bashrc | Bash initialization (RunPod fallback) | RunPod boot guard, zsh execution |

## Patterns
- **Initialization Chain**: .zshenv (env vars) -> .zprofile (login) -> .zshrc (interactive) with conditional RunPod support
- **Graceful Degradation**: gum_utils.sh provides terminal UI with plain-text fallback for non-TTY environments (cron, pipes, launchd)
- **Idempotent PATH Management**: Array-based PATH additions with deduplication and directory existence checks
- **RunPod Two-Layer Approach**: Ephemeral /root bridges to persistent /workspace/home via boot guard on every shell start
- **Modular Sourcing**: Core functionality split into helper_functions.sh, gum_utils.sh, and lscolors.sh for reusability
- **Feature Flags**: Environment variables (NO_GUM, DOTFILES_NO_GUM) control behavior across tools

## Dependencies
- **External Tools**: gum (terminal UI), fzf (fuzzy finder), bat (syntax highlighting), eza (ls replacement), ripgrep (rg), fd, htop, lazygit
- **Frameworks**: Prezto (zsh framework), Powerlevel10k (prompt), zprezto modules (editor, history, completion, syntax-highlighting, autosuggestions, git, fasd)
- **External Integrations**: Cargo (.cargo/env), NVM (Node.js), Bun runtime, FZF, iTerm2 shell integration
- **Internal**: References to ~/dotfiles/install/runpod_functions.sh, ~/dotfiles/update_checks/update_functions.sh, ~/.local_env.sh (secrets, git-ignored)

## Entry Points
- **.zshrc** - Main entry point for interactive zsh shells; sources all configuration files in specific order
- **.bashrc** - Bash fallback (minimal); executes zsh on RunPod or sources RunPod boot guard
- **.zshenv** - Earliest entry point for all zsh shells; sets LANG and fpath
- **runpod_boot_guard.sh** - Called from .zshrc/.bashrc on RunPod to re-establish symlink bridges

## Subdirectories
None. This directory is flat; all shell configuration files are at root level.

## Configuration Chain (from .zshrc)
1. Zprezto instant prompt (p10k cache)
2. RunPod boot guard (if /workspace/home exists)
3. Zprezto initialization (.zprezto/init.zsh)
4. Core utilities (helper_functions.sh, gum_utils.sh, lscolors.sh)
5. Aliases and environment (.aliases-and-envs.zsh)
6. Local secrets (.local_env.sh, git-ignored)
7. PATH management (.paths.zsh)
8. FZF configuration (.fzf.zsh, .fzf-config.zsh)
9. Powerlevel10k prompt (.p10k.zsh)
10. Cargo, Bun, and other tool integrations

## Notable Environment Variables
| Variable | Purpose | Source |
|----------|---------|--------|
| EDITOR, VISUAL | Default editor (hx/helix) | .zshrc |
| PAGER | Default pager (less with flags) | .zshrc |
| KEYTIMEOUT | Vi-mode transition speed | .zshrc |
| DIRSTACKSIZE | Directory stack size | .zshrc |
| TABSTACK_API_KEY | External service key | .aliases-and-envs.zsh |
| HTOP_FILTER | Processes to exclude from htop | .paths.zsh |
| EZA_TREE_IGNORE | Directories to hide in tree view | .aliases-and-envs.zsh |
| BAT_THEME | Syntax highlighting theme | .paths.zsh |
| UPDATE_CHECK_ON_STARTUP | Enable startup update checks | update_startup.sh |
