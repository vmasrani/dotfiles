# iterm2
> iTerm2 terminal configuration including hotkey window profile, keybindings, and SSH-specific color themes for macOS.
`14 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| iTerm2-profile-Hotkey Window.json | Floating hotkey window profile with color scheme, keybindings, status bar setup |
| iterm2-keybindings.itermkeymap | Key bindings mapping (navigation, editing, special functions) |
| LOCAL-AGENTS-BRAIN.iterm2arrangement | Saved window arrangement for agent workspace sessions |
| switch-ssh-theme | Script to dynamically apply SSH-specific color themes |

## Patterns
- **Profile-as-Code**: iTerm2 native JSON formats for reproducible terminal configuration
- **Hotkey Window**: Floating terminal (Tab key trigger) for quick context switching
- **SSH Color Themes**: 10 curated profiles for different SSH contexts (development, production, etc.)
- **Status Bar**: CPU and network utilization components with custom styling

## Dependencies
- **External:** iTerm2 (macOS terminal emulator), MesloLGS-NF font
- **Internal:** Symlinked to `~/.config/iTerm2/` during dotfiles setup via `setup.sh`

## Entry Points
- Profile auto-loads when iTerm2 starts
- Hotkey window triggered via Tab key
- SSH themes applied via `switch-ssh-theme` script

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| ssh-themes | yes |
