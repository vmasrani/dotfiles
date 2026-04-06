# scripts
> Tmux status bar scripts providing system metrics and Claude AI usage monitoring for powerkit-style pill rendering.
`22 files | 2026-04-05`

| Entry | Purpose |
|-------|---------|
| `agents_cache_refresh.sh` | Single writer for `/tmp/claude_usage_cache.json`; fetches Claude OAuth usage from `api.anthropic.com` with 120s TTL and `mkdir`-based atomic lock; on API error, touches existing cache instead of overwriting with zeros |
| `pk_claude_metric.sh` | Reads shared cache and outputs one metric (five_hour, seven_day, opus, sonnet, credits, reset) as a short label; synchronous refresh on first run, background thereafter |
| `agents_status_bar.sh` | Renders all Claude usage pills as powerline rounded glyphs; SSH vs local detection switches Catppuccin Macchiato vs Mocha palette |
| `update_session_status.sh` | Per-session hook: for the `agents` session, replaces `powerkit-render center` in `status-format[0]` with `agents_status_bar.sh` and patches session pill to orange with 🦀; other sessions unset the override |
| `agents_count.sh` | Counts active panes in the `agents` tmux session matching claude/node processes |
| `claude_code_status.sh` | Counts `pgrep claude` processes; outputs empty string (hides widget) when count is 0 — used in Dracula theme |
| `pm2_status_wrapper.sh` | Wraps `pm2_status.sh` with dynamic tmux background colors (green = all running, pink = stopped) |
| `cpu_status.sh`, `ram_status.sh`, `load_status.sh`, `battery_status.sh`, `gpu_status.sh`, `network_status.sh`, `weather_status.sh`, `ssh_status.sh`, `mem_usage.sh`, `cpu_percent.sh` | Standard system metric scripts for tmux status bar; cross-platform macOS/Linux where applicable |
| **backup/** | Old Dracula and Catppuccin theme shell files kept for reference |

<!-- peek -->

## Conventions

- All scripts use `SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"` for self-relative paths — required because tmux invokes scripts from arbitrary cwd.
- `agents_cache_refresh.sh` is the single writer for `/tmp/claude_usage_cache.json`; all metric readers go through `pk_claude_metric.sh`. Never read the cache file directly in new scripts.
- Cache locking uses `mkdir` (atomic on POSIX), not `flock` — intentional for macOS compatibility.
- `agents_status_bar.sh` is wired into `status-format[0]` by `update_session_status.sh` at session-switch time via string-replacing the existing powerkit command string with sed — not via a static tmux option.
- `pk_claude_metric.sh` is called once per pill by `agents_status_bar.sh`; each call may spawn a background `agents_cache_refresh.sh`, but the TTL and lock gate prevent redundant API calls.

## Gotchas

- `update_session_status.sh` depends on powerkit having already set `status-format[0]` before it runs. If powerkit hasn't rendered yet, the sed substitution finds nothing and Claude pills won't appear.
- OAuth token lookup tries macOS keychain (`security find-generic-password`) first, then `~/.claude/.credentials.json`. If neither is present, the cache is written as zeros with no visible error in the status bar.
- On API error, `agents_cache_refresh.sh` touches the existing cache to extend its TTL rather than overwriting — good data is preserved but stale data is silently kept alive.
- `agents_count.sh` looks for the tmux session named exactly `agents`; renaming that session silently breaks the count.
- SSH detection checks `$SSH_CLIENT`/`$SSH_TTY` — these are unset if you SSH then open a new tmux session locally, leading to Macchiato colors instead of Mocha.
- `pk_claude_metric.sh` uses `gdate` (GNU date) for reset time parsing on macOS, falling back to BSD `date -j`. If neither parses the ISO timestamp, the reset pill is silently hidden.
