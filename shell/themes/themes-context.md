# themes
> iTerm2 ANSI color palette definitions for terminal themes via OSC sequences.
`2 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| gruvbox-dark.zsh | Dark Gruvbox color palette with ANSI 0-15 mappings |
| palenight.zsh | Palenight color palette, reverses theme changes |

## Patterns
OSC sequence injection (iTerm2-specific). Handles tmux pane wrapping via `\033Ptmux;\033...\033\\`. Hex-to-RGB conversion inline.

## Dependencies
- **External:** None (pure zsh)
- **Internal:** Sourced from shell initialization chain

## Entry Points
- `source ~/dotfiles/shell/themes/gruvbox-dark.zsh` — Apply dark theme
- `source ~/dotfiles/shell/themes/palenight.zsh` — Revert to default
