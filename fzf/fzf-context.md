# fzf

## Purpose
Fuzzy finder (fzf) configuration for shell environments. Provides custom key bindings, completion settings, environment variables, and preview windows for interactive command-line fuzzy searching across files, directories, and shell history.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `.fzf-env.zsh` | Environment variables and styling | FZF_DEFAULT_OPTS, FZF_CTRL_T_OPTS, FZF_CTRL_R_OPTS, FD_EXCLUDE, BFS_EXCLUDE |
| `.fzf-config.zsh` | Zsh-specific keybindings and widgets | fzf-fasd-widget, fzf-tmux-widget, custom completion styles |
| `.fzf.zsh` | Zsh initialization script | Source fzf --zsh, PATH setup |
| `.fzf.bash` | Bash initialization script | Source fzf --bash, PATH setup |

## Patterns
- **Source composition**: Config files source `.fzf-env.zsh` for consistent environment setup
- **Zle widgets**: Custom Zsh line editor widgets for keybindings (`fzf-fasd-widget`, `fzf-tmux-widget`)
- **FZF options chaining**: Complex bind chains using `transform`, `reload`, and `execute` for interactive toggles
- **Preview window toggles**: Ctrl-slash binding for toggling preview visibility across multiple contexts
- **Fallback chains**: bfs -> fd for file discovery, with exclusion patterns

## Dependencies
- **External**: fzf (fuzzy finder), fd (fast find alternative), fasd (recent directories), bat (syntax-highlighted previews), tmux, git, helix (hx), bfs (breadth-first search, optional), pbcopy (macOS clipboard)
- **Internal**: Shell configuration sourced from `~/.zprezto/contrib/fzf-tab-completion`, references to helper scripts (`fzf-preview`)

## Entry Points
- `.fzf.zsh` — sourced from `~/.zshrc` for Zsh initialization
- `.fzf.bash` — sourced from `~/.bashrc` for Bash initialization
- `.fzf-config.zsh` — custom keybindings and completion (sourced from `.zshrc`)

## Key Keybindings
- `Ctrl-G` — fasd directory preview with fzf
- `Ctrl-N` — tmux scrollback autocomplete
- `Ctrl-X` — rfz command execution
- `Ctrl-T` — file/directory picker with local/global toggle (Ctrl-T), files/dirs toggle (Ctrl-R)
- `Ctrl-R` — shell history search with preview
- `Tab` — fzf-based completion
- `Ctrl-/` — toggle preview window visibility
- `Ctrl-D/U` — preview half-page navigation
- `Ctrl-J/K` — preview line navigation
- `Ctrl-S` — toggle sort
