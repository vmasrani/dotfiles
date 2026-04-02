# shell
> Zsh configuration hub: rc files, aliases, path management, terminal UI wrappers, and helper functions sourced at shell startup.
`18 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `.zshrc` | Main interactive shell entry point — sources all other files in order; editor set to `hx` |
| `.aliases-and-envs.zsh` | All aliases and env vars; `fd` and `rg` are aliased to include hidden/ignored files by default |
| `.paths.zsh` | PATH construction using an ordered array — deduplicates at end with awk; earlier entries win |
| `helper_functions.sh` | Utility functions (`command_exists`, `move_and_symlink`, `file_count`); also registers zsh hooks to track tmux scroll positions for `copy-last-output` |
| `gum_utils.sh` | Semantic wrappers for `gum` with TTY detection fallback; all shell scripts should use these instead of raw `echo` |
| `lscolors.sh` | LS_COLORS / EZA color scheme definitions |
| `.zpreztorc` | Prezto module config (loaded before `.zshrc` via `~/.zprezto/init.zsh`) |
| `.p10k.zsh` | Powerlevel10k prompt config (sourced last) |
| `update_startup.sh` | Startup update checker script |
| **themes/** | iTerm2 ANSI palette switcher scripts — gruvbox-dark for SSH sessions, palenight locally |

<!-- peek -->

## Conventions
- Shell config files are symlinked directly to `$HOME` (e.g., `.zshrc` → `~/.zshrc`), not to `~/.config/`. Edit here, not in `$HOME`.
- All shell scripts intended for user-facing output must use `gum_utils.sh` functions (`gum_success`, `gum_error`, etc.), never raw `echo`. Functions fall back to plain text when gum is unavailable or in non-TTY contexts.
- `fd` and `rg` are aliased to always include hidden/ignored files (`fd -HI`, `rg --no-ignore`) — scripts relying on default ignore behavior will behave differently here.
- PATH order: entries in `.paths.zsh` `PATH_ADDITIONS` array are prepended in order (index 0 = highest priority). Deduplication runs at the end — first occurrence wins.
- Theme selection is automatic: `gruvbox-dark.zsh` is sourced on SSH sessions, `palenight` theme is set locally via `DOTFILES_THEME` env var.

## Gotchas
- `.zshrc` sources files via `~/` symlink paths (e.g., `~/helper_functions.sh`), not via `~/dotfiles/shell/`. Adding new sourced files requires a symlink entry in `install/install_functions.sh`.
- `helper_functions.sh` registers `preexec`/`precmd` zsh hooks only when `$TMUX` is set — these track scroll positions for tmux `copy-last-output`. Adding other hooks must use `add-zsh-hook` to avoid clobbering these.
- `gum_utils.sh` caches TTY/gum availability in `_GUM_AVAILABLE` after first call. Re-sourcing the file resets the cache because `_GUM_AVAILABLE` is reset to `""`.
- The `ssh()` function in `.aliases-and-envs.zsh` wraps the real `ssh` binary to switch iTerm2 profiles — calling `/usr/bin/ssh` directly bypasses this.
- `local/.local_env.sh` (API keys, secrets) is git-ignored and sourced from `.zshrc`. If it's missing, the shell still loads cleanly — no error.
