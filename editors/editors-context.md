# editors
> Helix editor configuration with keybindings, LSP settings, and custom themes for Vi-style development workflow.
`4 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| hx_config.toml | Main Helix editor config: keybindings, statusline, theme, LSP settings |
| hx_languages.toml | Language server and syntax highlighting configuration |
| hx_themes/material_palenight_transparent.toml | Custom theme inheriting material_palenight with transparent background |
| find_files.sh | FZF-based file picker integration for Helix |

## Patterns
Vi-mode navigation with Helix bindings; FZF integration for file picker; LSP-driven development workflow with inlay hints and diagnostics.

## Dependencies
- **External:** Helix editor, FZF, Bat (preview), Lazygit (via tmux popup)
- **Internal:** Symlinked to `~/.config/helix/` during setup via `install_dotfiles`

## Entry Points
`hx_config.toml` — Main configuration file loaded by Helix on startup

## Notes
Keybindings heavily favor modal editing with Ctrl-modifiers for common operations (save, buffer navigation, file picker). LSP enabled with display-messages and inlay-hints. Custom file picker invokes FZF with Bat preview pane.
