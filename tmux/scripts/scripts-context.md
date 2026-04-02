# scripts
> Tmux status bar scripts providing system metrics and Claude AI usage monitoring for powerkit-style pill rendering.
`22 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `agents_cache_refresh.sh` | Fetches Claude OAuth usage from `api.anthropic.com` into `/tmp/claude_usage_cache.json`; uses atomic `mkdir` lock with 120s TTL to prevent concurrent calls |
| `pk_claude_metric.sh` | Reads the shared cache and outputs a single metric (five_hour, seven_day, opus, sonnet, credits, reset) as a short label; called per-pill by `agents_status_bar.sh` |
| `agents_status_bar.sh` | Renders all Claude usage metrics as powerline rounded pills with nerd font glyphs; detects SSH vs local to switch Catppuccin Macchiato vs Mocha palette |
| `update_session_status.sh` | Per-session hook: when session is `agents`, replaces `powerkit-render center` in `status-format[0]` with `agents_status_bar.sh` and patches pill to orange with 🦀; other sessions unset the override |
| `agents_count.sh` | Counts active panes in the `agents` tmux session matching claude/node processes |
| `claude_code_status.sh` | Counts `pgrep claude` processes for Dracula theme widget; outputs empty string (hides widget) when count is 0 |
| `pm2_status_wrapper.sh` | Wraps `pm2_status.sh` output with dynamic tmux background colors (green = all running, pink = stopped) |
| `cpu_status.sh`, `ram_status.sh`, `load_status.sh`, `battery_status.sh`, `gpu_status.sh`, `network_status.sh`, `weather_status.sh`, `ssh_status.sh`, `mem_usage.sh`, `cpu_percent.sh` | Standard system metric scripts for tmux status bar; cross-platform macOS/Linux where applicable |
| **backup/** | Old Dracula and Catppuccin theme shell files kept for reference |

<!-- peek -->

## Conventions

- All scripts use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` for self-relative paths — required because tmux invokes scripts from arbitrary cwd.
- `agents_cache_refresh.sh` is the single writer for `/tmp/claude_usage_cache.json`; all metric readers go through `pk_claude_metric.sh` which delegates refresh. Never read the cache file directly in new scripts.
- Cache locking uses `mkdir` (atomic on POSIX), not `flock` — intentional for macOS compatibility.
- `agents_status_bar.sh` is wired into `status-format[0]` by `update_session_status.sh` at session-switch time, not via a static tmux option — the swap is done by string-replacing the existing powerkit command string with sed.

## Gotchas

- `update_session_status.sh` depends on powerkit already having set `status-format[0]` before it runs. If powerkit hasn't rendered yet, the sed substitution finds nothing and falls back to the unmodified format (Claude pills won't appear).
- OAuth token lookup tries macOS keychain (`security find-generic-password`) first, then `~/.claude/.credentials.json`. If neither is present the cache is written as zeros — no error is surfaced to the status bar.
- `agents_count.sh` looks for the tmux session named exactly `agents`; renaming that session silently breaks the count.
- `pk_claude_metric.sh` spawns `agents_cache_refresh.sh` in the background on every call (after first run) — tmux calls status bar scripts on every interval tick, so background refresh fires frequently but is gated by the 120s TTL and lock.
- SSH detection in `agents_status_bar.sh` checks `$SSH_CLIENT`/`$SSH_TTY` — these are not set if you SSH then open a new tmux session locally, leading to Macchiato colors instead of Mocha.
