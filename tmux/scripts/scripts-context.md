# tmux scripts
> Status bar and session management scripts for tmux statusline display and agent process monitoring.
`18 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| agents_status_bar.sh | Renders Claude metrics as powerline-style pills for agents session |
| agents_count.sh | Counts active agents/processes in agents tmux session |
| pm2_status.sh | Monitors PM2 process states and displays colored status |
| cpu_status.sh | Cross-platform CPU usage percentage for status bar |
| ram_status.sh | Cross-platform RAM utilization (used/total GB) |
| battery_status.sh | macOS battery percentage and charging indicator |

## Patterns
Status bar metric collectors using case statements for macOS (`darwin`) vs Linux platform detection. Each script outputs simple string formatted for tmux statusline integration. Agents status bar uses powerline-style separators and Material Design nerd font icons. Color palettes switch between SSH and local environments.

## Dependencies
- **External:** tmux, top/vm_stat (macOS), /proc/stat (Linux), pm2, jq, bc, pagesize
- **Internal:** None

## Entry Points
All scripts are called directly from tmux statusline format strings in `.tmux.conf`, passing metrics back as formatted strings for display. `agents_status_bar.sh` is the main agents session pills renderer, calling `pk_claude_metric.sh` for individual metric values.

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| backup | no |
