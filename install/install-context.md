# install
> Installation helper functions and tool-specific install scripts orchestrated by setup.sh.
`5 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| `install_functions.sh` | Core install utilities: `install_if_missing`, `install_if_dir_missing`, `install_on_brew_or_mac`, `install_dotfiles` |
| `install_helix_language_servers.sh` | Installs Helix language servers via npm and cargo |
| `install-parquet-tools.sh` | Downloads and installs parquet-tools binary |
| `install_htop.sh` | System monitor installation |
| `install_tar.sh` | Tar utility installation |

## Patterns
- **Idempotent install guards**: Each tool checked before installation to skip if already present
- **OS abstraction**: `install_on_brew_or_mac` abstracts apt (Linux) vs brew (macOS)
- **Shell sourcing**: Helper functions and gum utils sourced at entry point
- **Symlink delegation**: `install_dotfiles` creates ~160 symlinks from repo to `$HOME`

## Dependencies
- **External:** brew (macOS), apt (Linux), npm, cargo, wget, gunzip
- **Internal:** `shell/helper_functions.sh`, `shell/gum_utils.sh`

## Entry Points
- `install_functions.sh` — sourced by `setup.sh`, provides all install functions
- Individual install scripts — called via `install_if_missing` from `setup.sh`

## Subdirectories
None — this is a flat utilities directory.
