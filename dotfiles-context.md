# dotfiles
> Automated dev environment setup across macOS and Linux with 60+ tools, AI config management, and in-place previews.
`10 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| setup.sh | Idempotent orchestration script; installs tools and symlinks all configs |
| install/install_functions.sh | Core install helpers: `install_if_missing`, `install_on_brew_or_mac`, `install_dotfiles` |
| CLAUDE.md | Claude Code guidance; symlink mappings, shell config chain, gum UI functions |
| shell/.zshrc | Entry point; sources Zprezto, helpers, UI, aliases, paths, fzf, prompt |
| README.md | Quick start, feature overview, keybindings (Ctrl-T, Ctrl-R, Ctrl-G, Ctrl-X) |

## Patterns
- **Idempotent Installation**: All install scripts skip if target already exists; safe to re-run
- **OS Abstraction**: `install_on_brew_or_mac` hides apt/brew differences via `$OS_TYPE`
- **Symlink Dispatch**: ~160 source→target pairs managed by `install_dotfiles` function
- **Shell Config Chain**: Sequential sourcing ensures deterministic initialization order
- **Force-Replace Claude**: `force_replace_targets` array ensures Claude configs always sync
- **Inline Python**: Tools use `#!/usr/bin/env -S uv run --script` shebang for dependencies

## Dependencies
- **External**: Homebrew (macOS), apt (Linux), zsh, tmux, fzf, gum, Helix, Node/npm/yarn/bun, Go, Rust/cargo, Python/uv, Git
- **CLI Tools**: bat, eza, fd, rg, jq, yq, lazygit, btop, claude, and 40+ others installed via `setup.sh`
- **Internal**: shell helpers, gum UI wrappers, fzf config, tmux plugins, Claude agents/commands/hooks/skills

## Entry Points
- **setup.sh**: Main orchestrator; run once on fresh system
- **shell/.zshrc**: Loaded on every shell; sources entire config chain
- **install/install_functions.sh**: Utility functions sourced by setup.sh and install scripts
- **maintained_global_claude/**: Version-controlled Claude config (agents, commands, hooks, skills, settings.json)

## Subdirectories
| Directory | Has Context | Role |
|-----------|-------------|------|
| shell | yes | Zsh config: aliases, env vars, paths, gum UI, helper functions |
| install | yes | Installation functions and tool-specific install scripts |
| tmux | yes | tmux config, plugins, status bar widgets |
| editors | yes | Helix config (hx_config.toml, hx_languages.toml) |
| tools | yes | 70+ CLI utilities (AI wrappers, data processors, system helpers) |
| preview | yes | 20+ fzf preview dispatchers for files, images, CSVs, PDFs, etc. |
| maintained_global_claude | yes | Claude Code agents, commands, hooks, skills, settings |
| fzf | yes | Fuzzy finder config and key bindings |
| mutt | yes | Email client config |
| vscode | yes | VS Code settings and extensions |
| linters | yes | Linter configs (shellcheck, prettier, flake8, etc.) |
| listeners | yes | Event-driven scripts |
| wip | yes | Work in progress experiments |
| prompt_bank | yes | Prompt templates for AI tasks |
| local | - | Git-ignored: `.local_env.sh` (secrets), machine-specific overrides |
| codex | yes | Codex-specific config |
| iterm2 | yes | iTerm2 profiles and settings |
| unused | yes | Archived/legacy configs |
| update_checks | yes | Package update monitoring scripts |
| logs | - | Archived logs |
