# backup

_Last updated: 2026-01-27_

## Purpose
Legacy theme configuration scripts for tmux status bar rendering. Contains backup/archived theme implementations (Dracula and Catppuccin color palettes) that configure tmux status bar appearance, plugins, and styling via tmux options.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| dracula.sh | Dracula theme configuration for tmux status bar | main() — applies color palette, status formatting, and plugin rendering |
| catppuccin.sh | Catppuccin Macchiato theme configuration for tmux status bar | main() — applies Catppuccin color palette with semantic aliases for backward compatibility |

## Patterns
**Theme Configuration Pattern**: Both files follow identical architecture: read tmux options using `get_tmux_option()` helper, define color palettes, apply conditional styling based on options, and render status bar with plugins via tmux set-option commands.

**Plugin System**: Modular plugin support via array iteration; each plugin branch reads its own color config, resolves the script path, and appends formatted output to status-right.

**Configuration Abstraction**: Color palette defined as bash variables, then aliased to semantic names (e.g., `white="$text"`, `cyan="$sapphire"`) for cross-theme option compatibility.

## Dependencies
- **Internal**: `/Users/vmasrani/dotfiles/tmux/scripts/utils.sh` (get_tmux_option helper function)
- **External**: tmux binary (set-option, set-window-option, set-status commands)

## Notable Features
- 40+ configuration options via `@dracula-*` tmux variables (military time, timezone, powerline separators, plugin selection)
- 30+ supported plugins (battery, network, weather, kubernetes, terraform, git, etc.)
- Conditional styling for powerline edges, transparent backgrounds, and window dividers
- Narrow mode support for compact status bar layouts
- Custom plugin support with executable script injection
- Dynamic color override system via `@dracula-colors` option
- Semantic color aliasing for backward compatibility between themes

## Subdirectories
None
