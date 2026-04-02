# tmux
> Tmux config with Catppuccin/powerkit status bar, vi-mode, popup sessions, and Claude API usage widgets.
`29 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `.tmux.conf` | Main config — keybindings, plugin declarations, powerkit theme, session hooks |
| `catppuccin-mocha-vibrant.sh` | Local theme override loaded by powerkit for non-SSH sessions |
| `catppuccin-macchiato-vibrant.sh` | Local theme override loaded by powerkit for SSH sessions |
| **scripts/** | Status bar scripts, session hooks, Claude usage cache |

<!-- peek -->

## Conventions

- **Powerkit plugins** use an `external(icon|value|bg|lighter|interval)` DSL — all status bar widgets are defined inline in `.tmux.conf` via `@powerkit_plugins`. Scripts in `scripts/` are referenced by absolute path (`$HOME/dotfiles/tmux/scripts/...`).
- **SSH vs local branching**: `.tmux.conf` uses `if-shell '[ -n "$SSH_CLIENT" ]...'` twice — once for powerkit theme path, once for the plugins list. SSH sessions include `gpu_status.sh` and `ssh_status.sh` but omit battery; local sessions include battery and weather.
- **Agents session** gets a fully custom status bar: `update_session_status.sh` is triggered by the `client-session-changed` hook and by `run-shell` at the end of `.tmux.conf` (post-TPM). It replaces powerkit's center render with `agents_status_bar.sh` and patches the session pill to orange with a 🦀 icon.
- **Claude usage cache**: `agents_cache_refresh.sh` writes to `/tmp/claude_usage_cache.json` with a 120-second TTL and `mkdir`-based atomic locking. `pk_claude_metric.sh` reads this cache and triggers background refresh on subsequent calls.
- **Transparency**: Popup and window backgrounds are forced to `bg=default` after TPM runs (post-TPM section) so iTerm2 transparency shows through. These overrides must stay after `run '~/.tmux/plugins/tpm/tpm'`.
- **Homebrew PATH fix**: `run-shell` near the bottom of `.tmux.conf` prepends `/opt/homebrew/bin` and `~/.fzf/bin` to tmux's PATH — required because powerkit needs bash 5+ from Homebrew.

## Gotchas

- **`update_session_status.sh` runs twice at startup** — once via the `client-session-changed` hook and once via `run-shell` at the very end of `.tmux.conf`. This is intentional: powerkit overwrites `status-format[0]`, so the second call re-applies the agents override after TPM finishes.
- **Pane border status** is session-specific: `off` globally, `top` only in the `agents` session. This is set by `update_session_status.sh`, not in `.tmux.conf` directly — editing `.tmux.conf` won't change agents behavior.
- **F12 nested session toggle** disables the prefix key entirely (sets `key-table off`) — the only way out is pressing F12 again. This is for SSH-within-tmux workflows to pass keys to the inner session.
- **`@sidepanel-pane-id` / `@sidepanel-session`** are set as tmux options but the `L` key binding uses `display-popup` + `new-session -A -s sidepanel` rather than those variables — the variables appear unused/legacy.
- **TPM auto-bootstraps**: if `~/.tmux/plugins/tpm` doesn't exist, the config clones it and runs `install_plugins` automatically on first launch.
- **`agents_cache_refresh.sh`** reads OAuth tokens from macOS Keychain (`security find-generic-password -s "Claude Code-credentials"`) with fallback to `~/.claude/.credentials.json`. If no token is found, writes zeros. If the API returns an error (e.g. rate limit), preserves existing cache data rather than overwriting with zeros.
