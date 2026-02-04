# editors

## Purpose

Configuration and tooling for text editors (Helix and Vim). This directory houses symlinked dotfiles for editor setup (`~/.config/helix/config.toml`, `~/.config/helix/languages.toml`, `~/.vimrc`) and supporting scripts for editor-integrated file selection.

## Key Files

| File | Role | Notable Content |
|------|------|-----------------|
| `hx_config.toml` | Helix editor main configuration | Theme (material_palenight), keybindings (normal/insert/select modes), LSP settings, editor UI layout |
| `hx_languages.toml` | Helix language server configuration | Bash and Python language definitions with LSP servers (bash-language-server, ruff, astral-ty) |
| `.vimrc` | Vim editor configuration | Legacy Vim config with keybindings, tab settings, autocmds, statusline, plugins (FZF integration) |
| `find_files.sh` | FZF-based file picker for editors | Shell script that wraps fzf with preview capabilities, integrates with editor extensions |
| `.viminfo` | Vim runtime data store | Binary/metadata file tracking cursor positions, command history, registers (auto-generated) |

## Patterns

- **Configuration as symlinks**: Both Helix and Vim configs are symlinked from this repo into the home directory during setup (`install_dotfiles` in `install_functions.sh`)
- **LSP-first approach**: Helix config integrates multiple language servers (bash-language-server, ruff, astral-ty) for real-time linting and type hints
- **Vim legacy support**: Maintains backwards-compatible Vim configuration alongside modern Helix setup
- **FZF integration**: Custom file picker script leverages fzf with previews for seamless editor file selection workflows
- **Keybinding customization**: Extensive custom keybindings in Helix for productivity (Ctrl+T for file picker, Ctrl+G for lazygit, word navigation with Alt+left/right)

## Dependencies

- **External**:
  - `fzf` (fuzzy finder)
  - `bat` (code preview in file picker)
  - `bash-language-server` (Bash LSP)
  - `ruff-lsp` (Python LSP, replaces pylsp)
  - `astral-ty` (Python type checker LSP)
  - `lazygit` (Git UI, invoked via Ctrl+G in Helix)
  - `tmux` (popup windows for lazygit)
  - `helix` editor
  - `vim` editor
- **Internal**: Sources `/EXTENSION_PATH/shared.sh` in `find_files.sh` (likely from fzf-helix extension or similar)

## Entry Points

- `hx_config.toml` — Symlinked to `~/.config/helix/config.toml` during setup
- `hx_languages.toml` — Symlinked to `~/.config/helix/languages.toml` during setup
- `.vimrc` — Symlinked to `~/.vimrc` during setup
- `find_files.sh` — Executed via `:insert-output fzf-helix` command within Helix editor

## Subdirectories

None. This is a flat configuration directory with no subdirectories.
