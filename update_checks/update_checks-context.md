# update_checks

## Purpose
Provides a caching system for checking package updates across multiple package managers (Homebrew, APT, Cargo, NPM, UV, Pip) with configurable intervals and startup integration to notify users of available updates without blocking shell initialization.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `update_config.sh` | Configuration center | `UPDATE_CACHE_DIR`, `UPDATE_CACHE_TIMEOUT`, `UPDATE_CHECK_ON_STARTUP`, `SHOW_UPDATES_ON_STARTUP`, `STARTUP_CHECK_INTERVAL` |
| `update_functions.sh` | Core logic for checking updates | `command_exists()`, `get_cache_file()`, `is_cache_valid()`, `get_cached_or_update()`, `check_all_updates()`, `show_update_commands()`, `refresh_update_cache()` |

## Patterns
- **Caching pattern**: Results cached with time-based invalidation to avoid repeated slow checks
- **Conditional package manager checks**: Each PM gets checked only if its CLI tool exists
- **Pluggable checker functions**: Individual `check_*_updates()` functions for each package manager
- **Background execution**: Startup checks run asynchronously to avoid blocking shell init

## Dependencies
- **External**: Homebrew, APT, Cargo, NPM, UV, Pip (all optional, checked before use)
- **Internal**: Sourced by `shell/update_startup.sh` and `tools/update-packages`

## Entry Points
- **`shell/update_startup.sh`** — Integrates into shell startup to show update notifications at configured intervals
- **`tools/update-packages`** — CLI tool with actions: `--check` (default), `--show`, `--refresh`

## Integration Points
- `update_functions.sh` is sourced by both `shell/update_startup.sh` and `tools/update-packages`
- Cache stored in `~/.cache/dotfiles_updates/` with per-PM cache files (`.brew_updates`, `.apt_updates`, etc.)
- Last startup check timestamp tracked in `.last_startup_check` to enforce `STARTUP_CHECK_INTERVAL`
