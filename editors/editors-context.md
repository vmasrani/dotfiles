# editors
> Helix editor config (theme, LSP, keybindings) and a legacy vim config, symlinked into `~/.config/helix/` by setup.sh.
`5 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `hx_config.toml` | Main Helix config — custom keybindings, theme, statusline. `C-t` triggers fzf file picker via `fzf-helix` shell command. `C-g` opens lazygit in a tmux popup. |
| `hx_languages.toml` | Helix language overrides — Python uses `ruff` + `astral-ty` (not pyright), bash scope extended to cover `.tmux.conf` and zsh files. |
| `hx_themes/` | Custom themes; `material_palenight_transparent.toml` is the active theme referenced in `hx_config.toml`. |
| `find_files.sh` | fzf file-picker helper sourced by a Helix extension (`EXTENSION_PATH/shared.sh` must exist at runtime). |
| `.vimrc` | Legacy vim config — not actively maintained, kept for fallback. |

<!-- peek -->

## Conventions
- Both `hx_config.toml` and `hx_languages.toml` are symlinked to `~/.config/helix/` by `install_dotfiles` in `install/install_functions.sh` — edit here, not in `~/.config/helix/`.
- The active theme name in `hx_config.toml` (`material_palenight_transparent`) must match a filename under `hx_themes/` — mismatches silently fall back to the default theme.

## Gotchas
- Python LSP is `ruff` + `astral-ty` (`ty server`), NOT pyright or pylsp. If `ty` isn't installed, LSP silently fails for Python.
- `C-t` in Helix runs `:insert-output fzf-helix` — this requires a `fzf-helix` binary/script on `$PATH` (defined elsewhere in the dotfiles, likely `preview/` or `tools/`). Missing it causes a silent no-op.
- `find_files.sh` depends on `$EXTENSION_PATH/shared.sh` — it is part of an fzf Helix extension, not a standalone script. Running it directly without the extension context will fail.
- `hx_languages.toml` sets `ruff-lsp` as the command for the ruff server — the newer `ruff server` subcommand replaces `ruff-lsp`; if `ruff-lsp` is removed from future ruff releases this will break.
