# install
> Installation helper functions and tool-specific install scripts orchestrated by setup.sh.
`5 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| `install_functions.sh` | Core helpers: `install_if_missing`, `install_if_dir_missing`, `install_on_brew_or_mac`, `install_dotfiles`. Provides idempotent install abstraction across OS |
| `install_helix_language_servers.sh` | Installs Helix LSPs via npm, cargo, and builds grammar with `hx --grammar` |
| `install-parquet-tools.sh` | Downloads parquet-tools binary release and places in ~/bin |

## Conventions
- All scripts use `OS_TYPE` (set in `install_functions.sh`) to branch between Linux (apt) and macOS (brew)
- Install function names follow pattern `install_<tool>` and are passed to `install_if_missing` by `setup.sh`
- Scripts source `shell/helper_functions.sh` and `shell/gum_utils.sh` instead of raw `echo`
- `install_dotfiles` handles ~160 symlinks with force-replace logic for Claude/Codex config directories

## Gotchas
- `install_on_brew_or_mac` takes positional args: ($1 = Linux pkg, $2 = macOS pkg); second arg defaults to first if omitted
- `install_helix_language_servers.sh` assumes npm, cargo, and hx already exist — fails if missing dependencies
- `install_dotfiles` symlink definitions are hardcoded inline (line 100+), not data-driven; changes require manual editing
