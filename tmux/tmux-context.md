# tmux

## Purpose
Tmux configuration with vi-keybindings, dynamic status bar with system metrics, session management, and specialized agent toolbar. Includes platform-specific clipboard integration (macOS/Linux) and plugin infrastructure via TPM.

## Key Files
| File | Role | Notable Features |
|------|------|-----------------|
| `.tmux.conf` | Core tmux configuration | Vi-mode navigation, Catppuccin v2.1.3 theme, statusline setup, hotkeys (F11 agents, L sidepanel) |
| `cpu_status.sh` | CPU usage display | macOS (top) and Linux (/proc/stat) support, formatted percentage output |
| `ram_status.sh` | RAM usage display | Used/total GB format, cross-platform memory calculation |
| `network_status.sh` | Network monitoring | SSID detection, current/5m/1h max throughput tracking, history caching |
| `battery_status.sh` | Battery indicator | Dynamic color gradient (green→red), charging icons, dual-platform support |
| `gpu_status.sh` | GPU metrics | nvidia-smi query mode, multi-GPU aggregation, memory + utilization |
| `load_status.sh` | System load average | 1m/5m/15m format, cross-platform parsing |
| `agents_status_vscode.sh` | Claude usage metrics | 5h/7d/credits display with color gradients, countdown to reset |
| `agents_cache_refresh.sh` | Centralized API cache | Atomic mkdir locking, 60s TTL, single jq parse |
| `agents_count.sh` | Agent session pane count | Detects running agent processes in tmux |
| `update_session_status.sh` | Session-specific toolbar | Agents session gets special statusline (crab icon, usage pills) |

## Patterns
- **Status bar composability**: Pills built with repeating `#[fg=X,bg=Y]` format + Powerline separators (hex-escaped U+E0B6/U+E0B4)
- **Atomic caching**: mkdir-based locking (macOS-compatible alternative to flock) with double-check after acquisition
- **Background refresh**: Usage scripts trigger cache refresh asynchronously (`&>/dev/null &`) then read cache synchronously
- **Cross-platform detection**: `uname -s` branching for macOS/Linux in every system metric script
- **Session hooks**: `set-hook` triggers status bar updates when switching sessions (agents-specific styling)
- **Plugin management**: TPM auto-install on first run, loads Catppuccin, resurrect/continuum, extrakto, fzf-pane-switch

## Dependencies
- **External**: tmux plugins (tmux-sensible, tmux-resurrect, tmux-continuum, extrakto, fzf-pane-switch, catppuccin/tmux), nvidia-smi (optional GPU monitoring), jq (JSON parsing), gdate/date (countdown calc), pbcopy/xclip (clipboard)
- **Internal**: References symlinked `~/.tmux/plugins/tpm/tpm`, `~/.tmux.conf.local` (optional local overrides)

## Entry Points
- `.tmux.conf`: Main configuration sourced by tmux on startup; loads all plugins via TPM
- Status bar integration: Scripts called every 2-5s via tmux status-interval, run non-blocking via command substitution `#(...)`
- Session hooks: `client-session-changed` triggers `update_session_status.sh` to reapply agent toolbar on attach

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| `scripts/` | Executable status bar scripts, cache management, session hooks | No |
| `scripts/.claude/` | Claude Code workspace logs (temporary, not part of config) | No |
| `scripts/backup/` | Archived theme variants (dracula.sh, catppuccin.sh) | No |

## Notable Implementation Details
- **Catppuccin Macchiato colors**: Hardcoded hex values for base (#24273a), crust (#181926), semantic colors (peach, teal, sapphire, blue, green)
- **Network script caching**: Maintains `/tmp/tmux_net_history` to track min/5m/1hr throughput peaks across status bar updates
- **Battery interpolation**: Charts charging/discharging states with 15+ Nerd Font icons covering 0-100% ranges
- **GPU aggregation**: Sums memory/utilization across multiple GPUs, outputs "2x" prefix for multi-GPU systems
- **Claude usage gradients**: `lerp()` function blends green→red as usage % increases, countdown uses overlay→green gradient
- **Agents toolbar**: Special status-left "crab" pill with prefix indicator (yellow on prefix), window shows agent count via tmux pane introspection
