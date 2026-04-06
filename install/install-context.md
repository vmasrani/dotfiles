# install
> Core installation helpers and one-off install scripts orchestrated by `setup.sh` at the repo root.
`6 files | 2026-04-05`

| Entry | Purpose |
|-------|---------|
| `install_functions.sh` | The heart of the install system — sourced by `setup.sh`. Defines `install_if_missing`, `install_if_dir_missing`, `install_on_brew_or_mac`, and the critical `install_dotfiles` function that manages all symlinks |
| `install_helix_language_servers.sh` | One-shot script to install LSPs via npm/cargo and build Helix grammars — run manually, not via setup.sh |
| `install_htop.sh` | Builds htop from source into `~/bin` — Linux-only, raw bash (no gum), pre-dates current conventions |
| `install_tar.sh` | One-off tar installation helper |
| `install-parquet-tools.sh` | One-off Linux amd64 parquet-tools binary installer (hardcodes v1.22.0); downloads to `~/bin` |

<!-- peek -->

## Conventions

`install_functions.sh` sources `shell/helper_functions.sh` and `shell/gum_utils.sh` at the top — these must exist before this file is usable. It detects `$OS_TYPE` (mac/linux) at load time; all platform branching uses `install_on_brew_or_mac <linux-pkg> [mac-pkg]` where the mac package defaults to the linux package name if omitted.

`install_dotfiles` uses `ensure_symlink source target force_link`. By default, symlinks are skipped if target already exists and is not broken — it does NOT overwrite. The `force_replace_targets` array is the exception: those targets (all `~/.claude/*` and `~/.codex/config.toml`) are always deleted and re-linked, making Claude/Codex config idempotent.

One-off scripts (`install_htop.sh`, `install_helix_language_servers.sh`, etc.) are NOT called from `setup.sh` — they are standalone scripts invoked manually for specific situations.

## Gotchas

`install_dotfiles` skips symlinking `maintained_global_claude/plugins/` — that directory contains machine-specific absolute paths generated from `*.template` files via `generate_plugin_configs()`; symlinking it would break on other machines.

`install_htop.sh` uses raw `echo` and `apt` without gum wrappers and assumes Linux — running on macOS will fail silently partway through.

Local (machine-specific) skills in `$dotfiles/local/local_skills/` are symlinked into `maintained_global_claude/skills/` at the end of `install_dotfiles` — they won't appear in `~/.claude/skills/` until `setup.sh` is re-run.

`install_functions.sh` uses `find` (not `fd`) for `chmod +x` on `.sh` files — intentional legacy behavior inside the install system, not a bug to fix.

On Apple Silicon Macs, `install_homebrew` appends `/opt/homebrew/bin` to PATH for the current session only — the permanent PATH comes from `.paths.zsh` after a shell restart.
