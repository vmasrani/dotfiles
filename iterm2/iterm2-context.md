# iterm2

## Purpose
Configuration files for iTerm2, the terminal emulator for macOS. Contains keyboard mappings and a custom hotkey window profile that integrates with the dotfiles system setup.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| iTerm2-profile-Hotkey Window.json | Terminal profile defining a floating hotkey window with color scheme, keybindings, and status bar components | Profile configuration (GUID: 2BE0D0A0-51AE-42CC-A602-72A2C20BA877) |
| iterm2-keybindings.itermkeymap | Keyboard mapping configuration for terminal key bindings | ~20 key-to-action mappings including navigation, editing, and special functions |

## Patterns
- **Configuration-as-Code**: iTerm2 native JSON and itermkeymap formats for reproducible terminal environments
- **Hotkey Window**: Configured floating terminal window (triggered by Tab key) for quick access, non-blocking (`HotKey Window Floats: false`)
- **Color Scheme**: Custom sRGB color palette with 16 ANSI colors (0-15) plus semantic colors (foreground, background, cursor, etc.)
- **Status Bar**: Displays CPU utilization and network utilization components with custom colors

## Configuration Details
- **Hotkey**: Tab key (keycode 48) with Ctrl modifier (262144)
- **Terminal Type**: xterm-256color
- **Font**: MesloLGS-NF-Regular 14pt (Nerd Font variant)
- **Window Size**: 80 columns, 35 rows
- **Visual Effects**: Blur enabled (radius 30), 54% blend, blinking cursor disabled
- **Keyboard Options**: Option key sends ESC+key (for vim/emacs navigation in SSH), right option sends nothing
- **Scroll Settings**: 1000 lines of scrollback, no unlimited scrollback

## Dependencies
- iTerm2 (macOS terminal emulator)
- MesloLGS-NF font (installed separately)
- Symlinked into `~/.config/iTerm2/` during dotfiles setup

## Entry Points
- Profile loaded automatically when iTerm2 opens
- Hotkey window accessible via Tab key press
- Keyboard mappings applied to all terminal sessions using this profile
