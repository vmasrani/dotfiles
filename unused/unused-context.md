# unused
> Graveyard of retired scripts and configs kept for reference but not symlinked or sourced anywhere.
`5 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `make-ml3.sh` | Creates a conda env named `ml3` with PyTorch 1.12 + CUDA 10.2 — pinned to old versions, not used in current uv-based workflow |
| `remove_submodule.sh` | One-shot script that removed an `update-golang` git submodule; hardcoded to push to `mac` branch, not idempotent |
| `setup_runpod.sh` | Bootstraps a RunPod cloud GPU instance: installs zsh, symlinks `/workspace/*` dirs to `$HOME`, sets up dotfiles — Linux-only |
| `.curlrc` | curl defaults (e.g., silent flags); not symlinked by `install_dotfiles` |
| `.wgetrc` | wget defaults; not symlinked by `install_dotfiles` |

<!-- peek -->

## Conventions
Nothing here is wired into `setup.sh` or `install_dotfiles` — files are retained purely as reference snippets, not active config.

## Gotchas
`remove_submodule.sh` contains hardcoded branch name `mac` and submodule name `update-golang`; running it blindly on the current repo would corrupt git state.
`make-ml3.sh` uses conda and pins very old CUDA/PyTorch versions — incompatible with the project's current `uv`-based Python toolchain.
