# unused

## Purpose

Archive directory containing deprecated configuration files and scripts that are no longer actively used but retained for reference or historical purposes.

## Key Files

| File | Role | Details |
|------|------|---------|
| `.curlrc` | Configuration | Curl proxy settings (commented out, no longer used) |
| `.wgetrc` | Configuration | Wget configuration file (empty) |
| `make-ml3.sh` | Setup script | Legacy Miniconda3 + PyTorch ML environment installer for Python 3.10 |
| `remove_submodule.sh` | Git utility | Helper script to remove a git submodule (`update-golang`) |
| `setup_runpod.sh` | Setup script | Legacy RunPod environment setup script with symlink bridging |

## Patterns

- Bash shell scripts with `set -e` for error handling
- Manual directory/file symlinking for environment setup
- Legacy conda/pip package management approach (superceded by uv)
- Git submodule management

## Dependencies

**External:**
- bash
- wget
- conda/miniconda
- git
- apt (Linux package manager)
- pip

**Internal:**
- None (standalone legacy scripts)

## Entry Points

- `setup_runpod.sh` — Historical RunPod environment setup (superseded by active `/setup_runpod.sh`)
- `make-ml3.sh` — Historical ML environment setup (deprecated in favor of uv)

## Notes

All files in this directory are marked as unused and kept for historical reference:
- `.curlrc` and `.wgetrc` contain proxy settings no longer needed
- `make-ml3.sh` represents an older Python/PyTorch setup approach before migration to uv-based dependency management
- `setup_runpod.sh` is an earlier version of RunPod bootstrap logic (active version exists in repository root)
- `remove_submodule.sh` is a one-off utility from past git submodule cleanup
