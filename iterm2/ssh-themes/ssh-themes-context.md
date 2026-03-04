# ssh-themes
> iTerm2 dynamic profiles for SSH sessions, with 10 pre-built theme configurations.
`11 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| switch-ssh-theme | CLI to select and activate SSH themes via gum selector |
| 01-subtle-tint.json | Warm amber tint theme for iTerm2 SSH profiles |
| 03-catppuccin-mocha.json | Popular pastel dark theme (Catppuccin Mocha) |
| 04-cyberpunk-neon.json | Electric pink/cyan neon theme on deep purple |
| 10-red-alert.json | High-contrast dark charcoal with red accents |

## Patterns
iTerm2 Dynamic Profiles: Each JSON file defines a profile named "SSH-Server" with custom colors (background, tab, badge) applied when SSH sessions connect. Profiles inherit from "Hotkey Window" parent.

## Dependencies
- **External:** iTerm2 (Terminal app on macOS)
- **Internal:** `shell/gum_utils.sh` (for interactive theme selection UI)

## Entry Points
- **switch-ssh-theme**: Zsh script that reads all theme files, displays them via gum selector, and symlinks selected theme to iTerm2 DynamicProfiles directory

## How It Works
1. Themes are JSON files stored in this directory
2. `switch-ssh-theme` reads all JSON files and presents them as menu choices
3. User selects a theme from the interactive prompt
4. Script creates symlink: `~/.Library/Application Support/iTerm2/DynamicProfiles/ssh-server.json` → selected theme
5. iTerm2 automatically applies the theme to SSH sessions (no restart needed)

## Theme Files (10 total)
01-subtle-tint, 02-frosted-glass, 03-catppuccin-mocha, 04-cyberpunk-neon, 05-ocean-depth, 06-amber-terminal, 07-tokyo-night, 08-solar-flare, 09-ghostly-matrix, 10-red-alert
