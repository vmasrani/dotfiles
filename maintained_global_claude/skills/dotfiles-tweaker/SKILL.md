---
name: dotfiles-tweaker
description: Tweak dotfiles configs — tmux, shell, fzf, helix, status bar, keybindings, themes, colors. Use when the user mentions dotfiles, tmux, zshrc, aliases, keybindings, status bar, fzf config, shell config, helix config, theme, colors, powerkit, or any config file modification.
---

# Dotfiles Tweaker

Comprehensive reference for making quick, informed changes to the dotfiles repo at `~/dotfiles/`.

## Repository Structure

```
~/dotfiles/
├── shell/           # zsh config, aliases, paths, helpers
├── tmux/            # tmux.conf + status bar scripts + themes
├── fzf/             # fzf defaults, integrations, tab completion
├── editors/         # helix config + languages
├── install/         # install_functions.sh (symlinks + installers)
├── tools/           # CLI utilities symlinked to ~/tools/
├── preview/         # fzf preview scripts symlinked to ~/bin/
├── local/           # git-ignored secrets, API keys
└── maintained_global_claude/  # Claude Code config (agents, hooks, skills, settings)
```

## Symlink Mappings (key files)

| Source (in repo) | Target (on system) |
|---|---|
| `shell/.zshrc` | `~/.zshrc` |
| `shell/.aliases-and-envs.zsh` | `~/.aliases-and-envs.zsh` |
| `shell/.paths.zsh` | `~/.paths.zsh` |
| `shell/helper_functions.sh` | `~/helper_functions.sh` |
| `shell/gum_utils.sh` | `~/gum_utils.sh` |
| `shell/lscolors.sh` | `~/lscolors.sh` |
| `shell/.zpreztorc` | `~/.zpreztorc` |
| `tmux/.tmux.conf` | `~/.tmux.conf` |
| `tmux/catppuccin-mocha-vibrant.sh` | `~/.config/tmux/catppuccin-mocha-vibrant.sh` |
| `tmux/catppuccin-macchiato-vibrant.sh` | `~/.config/tmux/catppuccin-macchiato-vibrant.sh` |
| `fzf/.fzf-env.zsh` | `~/.fzf-env.zsh` |
| `fzf/.fzf-config.zsh` | `~/.fzf-config.zsh` |
| `editors/hx_config.toml` | `~/.config/helix/config.toml` |
| `editors/hx_languages.toml` | `~/.config/helix/languages.toml` |
| `maintained_global_claude/settings.json` | `~/.claude/settings.json` |

**Important:** Always edit files in `~/dotfiles/`, never the symlink targets directly.

## Shell Source Chain

`.zshrc` sources files in this exact order:

1. **Powerlevel10k instant prompt** — `~/.cache/p10k-instant-prompt-*.zsh`
2. **Zprezto** — `~/.zprezto/init.zsh` (loads modules from `.zpreztorc`)
3. **Environment** — `EDITOR=hx`, `VISUAL=hx`, `PAGER='less -r'`, `KEYTIMEOUT=1`
4. **`helper_functions.sh`** — `command_exists()`, `move_and_symlink()`, `file_count()`, tmux copy-last-output hooks
5. **`gum_utils.sh`** — `gum_success`, `gum_error`, `gum_warning`, `gum_info`, `gum_dim`, `gum_spin_quick`, `gum_confirm`
6. **`lscolors.sh`** — LS_COLORS definitions
7. **`.aliases-and-envs.zsh`** — all aliases and env vars (see below)
8. **`.local_env.sh`** — API keys and secrets (git-ignored, in `local/`)
9. **Theme** — SSH: `shell/themes/gruvbox-dark.zsh`, Local: `DOTFILES_THEME="palenight"`
10. **`.paths.zsh`** — PATH construction with dedup
11. **fzf** — `~/.fzf.zsh` then `~/.fzf-config.zsh`
12. **Zsh options** — `numeric_glob_sort`, `APPEND_HISTORY`, `HIST_REDUCE_BLANKS`
13. **Vi-mode bindings** — `?`/`/` for search, `^f` edit-command-line, Alt+arrows word nav
14. **Powerlevel10k** — `~/.p10k.zsh`

**Where to put changes:**
- New aliases/env vars → `shell/.aliases-and-envs.zsh`
- PATH additions → `shell/.paths.zsh`
- New helper functions → `shell/helper_functions.sh`
- API keys/secrets → `local/.local_env.sh` (git-ignored)
- Zsh keybindings → `shell/.zshrc` (bottom section)
- fzf behavior → `fzf/.fzf-env.zsh` (defaults) or `fzf/.fzf-config.zsh` (integrations)

## Key Aliases

| Alias | Expands To |
|---|---|
| `l`, `L`, `lt`, `lf`, `ld` | eza variants (list, grid, by-time, by-size, dirs-only) |
| `t`, `t1`-`t4` | eza tree at depth levels |
| `p` | `fzf-preview` |
| `..`, `.2`-`.9` | `cd ../` repeated |
| `ta` | `tmux attach-session -t default \|\| tmux new-session -s default` |
| `refresh` | `source ~/.zshrc` |
| `dots` | `cd ~/dotfiles/` |
| `ga` | `lazygit` |
| `cc` | `claude` |
| `ccc` | `claude --continue` |
| `ccd` | `claude --dangerously-skip-permissions` |
| `upd` | `update-packages` |
| `fd` | `fd -HI` (hidden + ignored) |
| `rg` | `rg --no-ignore` |
| `bat` | `bat -n --color=always` |
| `g` | `glow` |
| `mutt` | `neomutt -F ~/.config/mutt/muttrc` |
| `::` | `uwu-cli` |
| `:::` | `uwu` (interactive wrapper) |

## Zprezto Modules (load order)

`environment`, `terminal`, `editor`, `history`, `directory`, `spectrum`, `utility`, `completion`, `history-substring-search`, `autosuggestions`, `fasd`, `syntax-highlighting`, `git`, `prompt`

- Editor mode: **emacs** (not vi)
- Prompt theme: **powerlevel10k**
- History: 1,000,000 entries

---

## tmux.conf (Complete)

```tmux
# vim:ft=conf:

# === Terminal & Core Settings ===
set -g default-terminal "tmux-256color"
set -g history-limit 100000
set -g base-index 1
set-option -g renumber-windows on
set -s escape-time 50
set-option -g set-clipboard on
set -g mouse on
set -g allow-passthrough on
set -g default-command "exec $(which zsh) -l"

# Environment settings
setenv -g SHOW_DIRECTORY_NAME 1
set-environment -gu GEM_EDITOR
set -ga update-environment "SSH_CLIENT SSH_TTY"

# Load local config
if-shell "test -f $HOME/.tmux.conf.local" "source $HOME/.tmux.conf.local"

# === Keybindings ===

# Create new panes and windows with current path
bind c new-window -c "#{pane_current_path}"
bind '"' split-window -c "#{pane_current_path}"
bind % split-window -h -c "#{pane_current_path}"
bind-key -n "M-'" split-window -h -c "#{pane_current_path}"
bind-key -n M-/ split-window -v -c "#{pane_current_path}"
bind-key -n M-n new-window -c "#{pane_current_path}"
bind-key -n M-N new-session -c "#{pane_current_path}"

# Sidepanel toggle (VSCode-style)
set -g @sidepanel-pane-id ""
set -g @sidepanel-session ""

bind-key L if-shell -F '#{==:#{session_name},sidepanel}' {
    detach-client
} {
    if-shell -F '#{session_exists:sidepanel}' {
        attach-session -t sidepanel
    } {
        display-popup -E -h 95% -w 95% -x C -y 55% "tmux new-session -A -s sidepanel"
    }
}

# Toggle agents session with F11
bind-key -n F11 if-shell -F '#{==:#{session_name},agents}' {
    detach-client
} {
    if-shell -F '#{session_exists:agents}' {
        display-popup -E -h 99% -w 95% -x C -y S "tmux attach-session -t agents"
    } {
        display-popup -E -h 99% -w 95% -x C -y S "tmux new-session -A -s agents"
    }
}

# Layout and process management
bind-key / next-layout
bind-key H display-popup -E -h 95% -w 95% -x C -y C 'htop -t'
bind-key g display-popup -E -h 95% -w 60% -x C -y C 'watch -n 1 nvidia-smi'

# Help and session management
bind-key ? split-window -h 'exec tmux list-keys | fzf-tmux -p80%,80%'
bind-key S command-prompt -p "New session name:" "new-session -s '%%'"

# Popup management
bind -n M-A display-popup -E -h 95% -w 95% -x 5% show-tmux-popup.sh popup1
bind -T popup M-A detach
bind -n M-S display-popup -E -h 95% -w 95% -x 5% show-tmux-popup.sh popup2
bind -T popup M-S detach
bind -T popup C-o copy-mode

# Copy last command output to clipboard (prefix + Y)
bind Y run-shell "$HOME/tools/copy-last-output"

# Pane navigation
unbind-key l
unbind-key h
bind-key -T prefix h swap-pane -U
bind-key -T prefix l swap-pane -D
bind-key -T prefix H rotate-window -D

# Resizing panes
unbind-key Left
bind-key -r Left resize-pane -L 5
unbind-key Right
bind-key -r Right resize-pane -R 5
unbind-key Down
bind-key -r Down resize-pane -D 5
unbind-key Up
bind-key -r Up resize-pane -U 5

# Window management
bind-key ^space last-window
bind-key p select-layout -o
bind-key '<' swap-window -d -t '{previous}'
bind-key '>' swap-window -d -t '{next}'

# Reload config
bind R source-file ~/.tmux.conf \; display "Reloaded .tmux.conf"

# Mark/copy feature
bind M run-shell '
  tmux display-message "Mark set";
  tmux set-option -g @mark_line "#{cursor_y}"
'

bind C run-shell '
  mark=$(tmux show-option -gqv @mark_line);
  if [ -z "$mark" ]; then
    tmux display-message "No mark set";
    exit 1;
  fi;

  current=$(tmux display -p "#{cursor_y}");

  if [ "$current" -lt "$mark" ]; then
    start=$current
    end=$mark
  else
    start=$mark
    end=$current
  fi

  tmux capture-pane -S $start -E $end -p | tmux load-buffer - ;
  tmux display-message "Copied from mark"
'

# === Copy Mode ===
bind -T copy-mode-vi v send -X begin-selection
bind P paste-buffer

if-shell "uname | grep -q Darwin" {
    bind -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "pbcopy"
    bind -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "pbcopy"
} {
    bind -T copy-mode-vi y send-keys -X copy-pipe-and-cancel "xclip -selection clipboard -i"
    bind -T copy-mode-vi MouseDragEnd1Pane send-keys -X copy-pipe-and-cancel "xclip -selection clipboard -i"
}

bind-key -T copy-mode MouseDragEnd1Pane send-keys -X copy-selection-and-cancel
bind-key -T copy-mode S-MouseDrag1Pane send-keys -X begin-selection \; send-keys -X rectangle-toggle
bind-key -T copy-mode-vi S-MouseDrag1Pane send-keys -X begin-selection \; send-keys -X rectangle-toggle

# === Status & Window Settings ===
set-option -g status-position top
set-option -g status-keys vi
set-option -g set-titles on
set-option -g set-titles-string 'tmux - #W'
set -g bell-action any
set-option -g visual-bell off
setw -g mode-keys vi
setw -g monitor-activity on
set -g visual-activity on
set-option -g automatic-rename on
set-option -g automatic-rename-format '#{b:pane_current_path}'

# === Session Hooks ===
set-hook -g client-session-changed 'run-shell "~/dotfiles/tmux/scripts/update_session_status.sh"'

# Pane borders (titles only shown in 'agents' session via hook)
set -g pane-border-status off
set -g pane-border-format "#{?pane_title, #{pane_title} ,}"
set-hook -g after-split-window 'select-pane -T ""'
set-hook -g after-new-window 'select-pane -T ""'

# === F12 Nested Session Toggle ===
color_status_text="#a5adcb"           # subtext0
color_window_off_status_bg="#363a4f"  # surface0
color_dark="#24273a"                  # base
color_window_off_status_current_bg="#5b6078"  # surface2

bind -T root F12  \
  set prefix None \;\
  set key-table off \;\
  set status-style "fg=$color_status_text,bg=$color_window_off_status_bg" \;\
  set window-status-current-format "#[fg=$color_window_off_status_bg,bg=$color_window_off_status_current_bg]#[default] #I:#W# #[fg=$color_window_off_status_current_bg,bg=$color_window_off_status_bg]#[default]" \;\
  set window-status-current-style "fg=$color_dark,bold,bg=$color_window_off_status_current_bg" \;\
  set window-status-format " #I:#W " \;\
  set window-status-style "fg=$color_status_text,bg=$color_window_off_status_bg" \;\
  if -F '#{pane_in_mode}' 'send-keys -X cancel' \;\
  refresh-client -S \;\

bind -T off F12 \
  set -u prefix \;\
  set -u key-table \;\
  set -u status-style \;\
  set -u window-status-current-style \;\
  set -u window-status-current-format \;\
  set -u window-status-style \;\
  set -u window-status-format \;\
  refresh-client -S

# === Powerkit Configuration ===
set -g @powerkit_theme "catppuccin"
set -g @powerkit_theme_variant "mocha"

if-shell '[ -n "$SSH_CLIENT" ] || [ -n "$SSH_TTY" ]' \
    'set -g @powerkit_custom_theme_path "~/.config/tmux/catppuccin-macchiato-vibrant.sh"' \
    'set -g @powerkit_custom_theme_path "~/.config/tmux/catppuccin-mocha-vibrant.sh"'
set -g @powerkit_separator_style "rounded"
set -g @powerkit_transparent "true"
set -g @powerkit_bar_layout "single"
set -g @powerkit_status_interval "5"

# Layout & Appearance
set -g @powerkit_status_order "session,plugins,windows"
set -g @powerkit_elements_spacing "false"
set -g @powerkit_window_index_style "box"
set -g @powerkit_window_index_icons "true"
set -g @powerkit_edge_separator_style "rounded:all"

# Pane Flash Effect
set -g @powerkit_pane_flash_enabled "true"
set -g @powerkit_pane_flash_duration "100"

# Plugins — external() wrappers (SSH vs local variants below)
# ...see full external() definitions in the Powerkit Plugin System section...

# === TPM Plugins ===
set -g @plugin 'tmux-plugins/tpm'
set -g @plugin 'tmux-plugins/tmux-sensible'
set -g @plugin 'fabioluciano/tmux-powerkit'
set -g @plugin 'laktak/extrakto'
set -g @plugin 'kristijan/tmux-fzf-pane-switch'
set -g @plugin 'tmux-plugins/tmux-resurrect'
set -g @plugin 'tmux-plugins/tmux-continuum'

# Continuum Settings
set -g @continuum-restore 'on'
set -g @extrakto_filter_order "line word all"

# Ensure homebrew bash 5+ and fzf are on PATH for plugins
run-shell 'tmux set-environment -g PATH "/opt/homebrew/bin:$HOME/.fzf/bin:$(tmux show-environment -g PATH | cut -d= -f2-)"'

# === TPM Bootstrap ===
if "test ! -d ~/.tmux/plugins/tpm" \
   "run 'git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm && ~/.tmux/plugins/tpm/bin/install_plugins'"

run '~/.tmux/plugins/tpm/tpm'

# === Post-TPM: Transparency overrides ===
set -g window-style bg=default
set -g window-active-style bg=default
set -g popup-style bg=default
set -g popup-border-style bg=default
set -g status on
```

## Tmux Keybindings Reference

### Root table (no prefix needed)

| Key | Action |
|---|---|
| `M-'` (Alt+') | Split horizontal |
| `M-/` (Alt+/) | Split vertical |
| `M-n` | New window |
| `M-N` | New session |
| `M-A` | Popup 1 toggle |
| `M-S` | Popup 2 toggle |
| `F11` | Toggle agents session popup |
| `F12` | Nested session toggle (disable local prefix) |

### Prefix table (Ctrl+b then...)

| Key | Action |
|---|---|
| `c` | New window (current path) |
| `"` | Split horizontal (current path) |
| `%` | Split vertical (current path) |
| `L` | Sidepanel toggle (popup session) |
| `/` | Next layout |
| `H` | htop popup |
| `g` | nvidia-smi popup |
| `?` | List keys in fzf |
| `S` | New named session |
| `Y` | Copy last command output |
| `h` | Swap pane up |
| `l` | Swap pane down |
| `H` | Rotate window |
| `Ctrl+Space` | Last window |
| `p` | Previous layout (select-layout -o) |
| `<` / `>` | Swap window left/right |
| `R` | Reload tmux.conf |
| `M` | Set mark at cursor |
| `C` | Copy from mark to cursor |
| `P` | Paste buffer |
| Arrow keys | Resize pane (repeatable, 5 units) |

### Copy mode (vi)

| Key | Action |
|---|---|
| `v` | Begin selection |
| `y` | Copy to system clipboard |
| `Shift+Drag` | Rectangle selection |

## Tmux Scripts

All in `~/dotfiles/tmux/scripts/`, called from status bar or hooks:

| Script | Purpose | Refresh |
|---|---|---|
| `cpu_percent.sh` | CPU usage % (macOS, uses `ps`) | 5s |
| `mem_usage.sh` | Memory usage % (macOS, uses `vm_stat`) | 5s |
| `gpu_status.sh` | GPU util/mem via `nvidia-smi` (SSH only) | 5s |
| `weather_status.sh` | Weather from API, cached 30min | 1800s |
| `ssh_status.sh` | Shows hostname when in SSH, empty otherwise | 30s |
| `battery_status.sh` | Battery % with dynamic color/icon | 60s |
| `agents_status_bar.sh` | Replaces center status in agents session | - |
| `agents_count.sh` | Count active Claude agents in agents session | - |
| `agents_cache_refresh.sh` | Refresh Claude usage cache (atomic lock) | - |
| `update_session_status.sh` | Hook: swaps status format for agents session | on session change |
| `cpu_status.sh` | CPU load (Linux/macOS) | - |
| `ram_status.sh` | RAM usage (Linux/macOS) | - |
| `load_status.sh` | System load average | - |
| `network_status.sh` | SSID + bandwidth stats | - |
| `claude_code_status.sh` | Claude Code status widget | - |
| `pk_claude_metric.sh` | Claude API usage metrics | - |
| `pm2_status.sh` / `pm2_status_wrapper.sh` | PM2 process status | - |

## Powerkit Plugin System

Plugin: `fabioluciano/tmux-powerkit` — requires bash 5+ (homebrew).

### external() Syntax

```
external("ICON"|"COMMAND"|"ACCENT_COLOR"|"ALT_COLOR"|"REFRESH_INTERVAL")
```

- **ICON**: Nerd Font icon (e.g., `󰘚` for CPU)
- **COMMAND**: Shell command, use `#(...)` for tmux command substitution
- **ACCENT_COLOR**: Primary hex color for the widget pill
- **ALT_COLOR**: Lighter variant for contrast
- **REFRESH_INTERVAL**: Seconds between updates

### Current Widgets

**Local (macOS):**
```
CPU (󰘚)  → cpu_percent.sh   │ #fab387 peach    │ 5s
MEM (󰍛)  → mem_usage.sh     │ #cba6f7 mauve    │ 5s
BAT (󰂄)  → pmset -g batt    │ #a6e3a1 green    │ 60s
WTH (󰖐)  → weather_status   │ #f9e2af yellow   │ 1800s
TIME (󰃰) → date             │ #74c7ec sapphire │ 30s
USER (󰒋) → whoami@hostname  │ #f5c2e7 pink     │ 3600s
```

**SSH (remote server):**
```
CPU (󰘚)  → cpu_percent.sh   │ #f5a97f peach    │ 5s
MEM (󰍛)  → mem_usage.sh     │ #c6a0f6 mauve    │ 5s
GPU (󰢮)  → gpu_status.sh    │ #a6da95 green    │ 5s
SSH (󰣀)  → ssh_status.sh    │ #8aadf4 blue     │ 30s
WTH (󰖐)  → weather_status   │ #eed49f yellow   │ 1800s
TIME (󰃰) → date             │ #7dc4e4 sapphire │ 30s
USER (󰒋) → whoami@hostname  │ #f5bde6 pink     │ 3600s
```

### Key Powerkit Options

| Option | Value | Effect |
|---|---|---|
| `@powerkit_theme` | `catppuccin` | Base theme |
| `@powerkit_theme_variant` | `mocha` | Catppuccin flavor |
| `@powerkit_custom_theme_path` | path to `.sh` | Custom color overrides |
| `@powerkit_separator_style` | `rounded` | Pill separator shape |
| `@powerkit_transparent` | `true` | Transparent backgrounds |
| `@powerkit_bar_layout` | `single` | Single-line status bar |
| `@powerkit_status_interval` | `5` | Global refresh (seconds) |
| `@powerkit_status_order` | `session,plugins,windows` | Left-to-right layout |
| `@powerkit_elements_spacing` | `false` | No gaps between elements |
| `@powerkit_window_index_style` | `box` | Window number style |
| `@powerkit_window_index_icons` | `true` | Show devicons |
| `@powerkit_edge_separator_style` | `rounded:all` | Rounded edges |
| `@powerkit_pane_flash_enabled` | `true` | Flash on pane switch |
| `@powerkit_pane_flash_duration` | `100` | Flash duration (ms) |

## Status Bar Architecture

### Session Hooks

`client-session-changed` hook runs `update_session_status.sh` on every session switch:

- **agents session**: Replaces powerkit's center render with `agents_status_bar.sh`, sets session pill to orange (default) / green (prefix) / blue (copy-mode), replaces icon with crab emoji
- **Other sessions**: Unsets overrides, falls back to powerkit's global rendering, disables pane border titles

### Agents Session

The `agents` session is a popup (F11) for managing Claude Code agents. Features:
- Custom status bar showing agent pane status
- Pane border titles enabled (shows agent names)
- Orange session pill with crab icon
- Each pane runs a Claude agent

## Catppuccin Color Palette

### Mocha (local) — `catppuccin-mocha-vibrant.sh`

| Role | Color | Hex |
|---|---|---|
| Base (background) | dark blue-gray | `#1e1e2e` |
| Surface0 (statusbar bg) | | `#313244` |
| Surface1 (inactive) | | `#45475a` |
| Text | | `#cdd6f4` |
| Mauve (session/pane border) | purple | `#cba6f7` |
| Pink (active window) | | `#f5c2e7` |
| Peach (prefix indicator) | orange | `#fab387` |
| Sapphire (copy/zoomed) | blue | `#74c7ec` |
| Yellow (search) | | `#f9e2af` |
| Green (good) | | `#a6e3a1` |
| Blue (ok/info, vibrant) | | `#89b4fa` |
| Red (error) | | `#f38ba8` |
| Overlay0 (disabled) | gray | `#6c7086` |

### Macchiato (SSH) — `catppuccin-macchiato-vibrant.sh`

| Role | Color | Hex |
|---|---|---|
| Base (background) | | `#24273a` |
| Surface0 | | `#363a4f` |
| Surface1 | | `#494d64` |
| Text | | `#cad3f5` |
| Mauve | | `#c6a0f6` |
| Pink | | `#f5bde6` |
| Peach | | `#f5a97f` |
| Sapphire | | `#7dc4e4` |
| Yellow | | `#eed49f` |
| Green | | `#a6da95` |
| Blue | | `#8aadf4` |
| Red | | `#ed8796` |
| Overlay0 | | `#6e738d` |

### Theme Color Array Format

Both theme files export `THEME_COLORS` associative array with keys:
`background`, `statusbar-bg`, `statusbar-fg`, `session-bg`, `session-fg`, `session-prefix-bg`, `session-copy-bg`, `session-search-bg`, `session-command-bg`, `window-active-base`, `window-active-style`, `window-inactive-base`, `window-inactive-style`, `window-activity-style`, `window-bell-style`, `window-zoomed-bg`, `pane-border-active`, `pane-border-inactive`, `ok-base`, `good-base`, `info-base`, `warning-base`, `error-base`, `disabled-base`, `message-bg`, `message-fg`, `popup-bg`, `popup-fg`, `popup-border`, `menu-bg`, `menu-fg`, `menu-selected-bg`, `menu-selected-fg`, `menu-border`

## FZF Configuration

### Defaults (`fzf/.fzf-env.zsh`)

- Style: `full`, reverse, ansi, border, padding
- Preview: `fzf-preview {}` in right:70%:nowrap
- File finder: `bfs` (preferred) or `fd` fallback
- Excludes: `.git`, `__pycache__`, `.venv`, `.mypy_cache`

### Key Bindings

| Context | Key | Action |
|---|---|---|
| Global | `Ctrl+T` | File/dir finder (toggle local/global with Ctrl+T, files/dirs with Ctrl+R) |
| Global | `Ctrl+R` | History search with bat preview |
| Global | `Ctrl+G` | fasd recent directories |
| Global | `Ctrl+N` | Tmux scrollback autocomplete |
| Global | `Ctrl+X` | rfz (ripgrep+fzf) |
| Global | `Tab` (Ctrl+I) | fzf-tab-completion |
| Ctrl+T | `Ctrl+F` | Open in helix |
| Ctrl+R | `Ctrl+Y` | Copy to clipboard |
| Ctrl+R | `Ctrl+V` | View in less |
| All fzf | `Ctrl+/` | Toggle preview window |
| All fzf | `Ctrl+D/U` | Preview scroll half-page |
| All fzf | `Ctrl+J/K` | Preview scroll line |
| All fzf | `Ctrl+B` | Preview bottom |
| All fzf | `Ctrl+S` | Toggle sort |

## Zsh Keybindings

| Key | Action | Source |
|---|---|---|
| `Ctrl+F` | Edit command line in $EDITOR | `.zshrc` |
| `Alt+Left/Right` | Word navigation | `.zshrc` |
| `?` (vicmd) | History search backward | `.zshrc` |
| `/` (vicmd) | History search forward | `.zshrc` |
| `Ctrl+G` | fasd directory picker | `.fzf-config.zsh` |
| `Ctrl+N` | Tmux scrollback autocomplete | `.fzf-config.zsh` |
| `Ctrl+X` | rfz (ripgrep+fzf search) | `.fzf-config.zsh` |
| `Ctrl+I` (Tab) | fzf-tab-completion | `.fzf-config.zsh` |

## Helix Editor

### Config (`editors/hx_config.toml`)

- Theme: `material_palenight_transparent`
- Line numbers: relative
- Soft wrap: enabled
- Bufferline: always shown
- Auto-format: on
- Cursor: bar (insert), underline (select)
- LSP: inlay hints + messages enabled

### Key Helix Bindings

| Mode | Key | Action |
|---|---|---|
| Normal | `Ctrl+S` | Save |
| Normal | `Ctrl+W` | Close buffer |
| Normal | `Ctrl+G` | Lazygit popup |
| Normal | `Ctrl+V` | Paste from clipboard |
| Normal | `Ctrl+D` | Select word + search (multi-cursor) |
| Normal | `V` | Select to line end |
| Normal | `X` / `x` | Extend line (up / down) |
| Normal | `Ctrl+T` | fzf file picker |
| Normal | `Ctrl+Left/Right` | Buffer prev/next |
| Normal | `Space q` | Quit |
| Select | `Ctrl+D` | Add next occurrence |
| Select | `;` | Collapse + normal mode |

### Languages (`editors/hx_languages.toml`)

- **Python**: ruff-lsp + astral-ty (ty server)
- **Bash/Zsh**: bash-language-server (also handles `.tmux.conf`)

## Verification Steps

After making changes:

```bash
# Reload tmux config
tmux source-file ~/.tmux.conf
# Or from inside tmux: prefix + R

# Reload shell config
source ~/.zshrc
# Or: refresh (alias)

# Test tmux scripts
~/dotfiles/tmux/scripts/cpu_percent.sh
~/dotfiles/tmux/scripts/mem_usage.sh

# Check for shell syntax errors
zsh -n ~/.zshrc

# Verify symlinks
ls -la ~/.tmux.conf ~/.zshrc ~/.aliases-and-envs.zsh

# Re-run setup if symlinks are broken
cd ~/dotfiles && ./setup.sh
```

## TPM Plugin Management

```bash
# Install new plugins (after adding to tmux.conf)
# prefix + I

# Update plugins
# prefix + U

# Remove plugins not in tmux.conf
# prefix + Alt+u
```
