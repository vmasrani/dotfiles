<div align="center">

<img src="assets/stewie.png" width="120" />

*"Named after the only baby who would insist on a properly configured terminal."*

# super-TUI

**Your terminal, but better.**

[![macOS](https://img.shields.io/badge/macOS-supported-blue?style=flat-square)](https://www.apple.com/macos/)
[![Linux](https://img.shields.io/badge/Linux-supported-blue?style=flat-square)](https://kernel.org/)
[![Zsh](https://img.shields.io/badge/Zsh-shell-green?style=flat-square)](https://www.zsh.org/)
[![tmux](https://img.shields.io/badge/tmux-multiplexer-green?style=flat-square)](https://github.com/tmux/tmux)
[![Helix](https://img.shields.io/badge/Helix-editor-purple?style=flat-square)](https://helix-editor.com/)
[![fzf](https://img.shields.io/badge/fzf-fuzzy%20finder-orange?style=flat-square)](https://github.com/junegunn/fzf)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

![demo](assets/demo.gif)

**60+ tools &middot; 20+ file previewers &middot; one command to install**

</div>

---

## Quick Start

```bash
git clone https://github.com/vmasrani/dotfiles.git ~/dotfiles && cd ~/dotfiles
./setup.sh
```

The setup script is idempotent -- safe to re-run at any time. It detects your OS, installs what's missing, and symlinks everything into place.

---

## Why super-TUI?

| | |
|---|---|
| **Everything previews in-place** | CSV, JSON, Parquet, images, PDFs, videos, notebooks, PyTorch tensors -- all rendered inline in fzf without leaving the terminal. |
| **Fuzzy-find everything** | Files, directories, history, tmux scrollback, git branches, kill targets. If it's text, you can fzf it. |
| **One setup command** | `./setup.sh` handles Homebrew, apt, npm, Cargo, Go, uv, Bun, and 60+ tools. Works on a fresh Mac or a headless Linux box. |
| **Modern CLI replacements** | `bat` over `cat`, `eza` over `ls`, `fd` over `find`, `rg` over `grep`, `bfs` over `find`, `gum` over `echo`. If there's a better version, it's already swapped in. |
| **AI-native** | Claude Code, Codex, and OpenCode are installed and configured out of the box. Custom agents, slash commands, hooks, and skills are version-controlled and symlinked. |
| **Works on Mac + Linux** | OS detection baked into every install function. Homebrew on macOS, apt on Linux, with graceful fallbacks throughout. |

> It's just dotfiles. Fork it, gut what you don't need, and make it yours.

---

## What's Inside

| Layer | Tool | Role |
|-------|------|------|
| Shell | Zsh + Zprezto + Powerlevel10k | Framework, prompt, completions |
| Multiplexer | tmux + Powerkit | Sessions, splits, status widgets |
| Fuzzy Finder | fzf + fzf-tab-completion | File/dir/history/tmux search |
| Editor | Helix | Modal editor with LSP, tree-sitter |
| AI | Claude Code, Codex, OpenCode | AI coding assistants |
| Tools | 60+ custom scripts | AI wrappers, data tools, system utils |
| Preview | fzf-preview dispatcher | 20+ file types rendered inline |
| Packages | Homebrew, apt, npm, Cargo, Go, uv, Bun | Language-specific package managers |

---

## Keybindings

These are the global keybindings that work everywhere in the shell. They are the selling point.

| Key | What it does | Sub-bindings |
|-----|-------------|--------------|
| `Ctrl-T` | Fuzzy file finder | `Ctrl-T` again toggles local (`.`) vs global (`~`), `Ctrl-R` toggles files vs dirs, `Ctrl-F` opens in Helix |
| `Ctrl-R` | Fuzzy history search | `Ctrl-V` view in pager, `Ctrl-Y` copy to clipboard, `Ctrl-T` track result |
| `Ctrl-G` | Fuzzy directory jump (fasd) | Jump to frecent directories |
| `Ctrl-X` | rfz (ripgrep fuzzy) | Live grep with preview |
| `Ctrl-N` | tmux scrollback autocomplete | Complete from visible terminal output |
| `Tab` | fzf tab completion | Contextual: git diff preview, process preview, dir drill-down |

> [!TIP]
> All fzf panels share vim-style nav: `Ctrl-J`/`K` scroll preview, `Ctrl-D`/`U` half-page, `Ctrl-/` toggles preview window.

---

## Omni-Preview

Every fzf panel can preview files inline. The format is detected automatically.

| Extension | Previewer |
|-----------|-----------|
| `.csv` | `print_csv` (colorized columns) |
| `.json` | `jq` (syntax-highlighted JSON) |
| `.parquet` | `parquet-tools` -> `jq` |
| `.md` | `glow` (rendered markdown) |
| `.pdf` | `pdftotext` |
| `.ipynb` | `rich --ipynb` |
| `.db` | `sqlite3` -> `print_csv` |
| `.pkl` / `.pickle` | `pkl-preview` (Python pickle) |
| `.pt` | `torch-preview` (PyTorch tensors) |
| `.npy` | `npy-preview` (NumPy arrays) |
| `.feather` | `feather-preview` (Arrow/Feather) |
| `.jpg` / `.png` | `chafa` (ASCII art) |
| `.mp4` / `.avi` / `.gif` / `.mkv` | `ffmpegthumbnailer` -> `chafa` |
| `.epub` | `markitdown` -> `glow` |
| `.zip` | `visidata` (archive listing) |
| `.sh` | `bat` (syntax-highlighted) |
| Directories | `eza --tree` (3-level tree) |
| Everything else | `bat` with fallback to `tldr` |

<details>
<summary><strong>How it works</strong></summary>

`fzf-preview.sh` is a case-switch dispatcher. Every time you move focus in an fzf panel, fzf calls this script with the highlighted path as its argument. The script checks the file extension and routes to the appropriate previewer.

Adding support for a new format is a one-liner: add a case branch to the `case "$1" in` block in `preview/fzf-preview.sh`, mapping your extension to whatever CLI tool renders it best.

```bash
# Example: adding YAML preview
*.yaml|*.yml)
  bat -n --color=always "$1"
  ;;
```

Directories get their own branch at the bottom, rendered as a 3-level tree via `eza`. Anything that doesn't match a known extension falls through to `bat`, with a secondary fallback to `tldr` if the argument happens to be a command name.

</details>

---

## tmux

![tmux](assets/tmux-screenshot.png)

The tmux configuration is built around a single-line status bar powered by [tmux-powerkit](https://github.com/fabioluciano/tmux-powerkit), with session-aware theming that changes based on whether you are local or remote.

### Status Bar Widgets

| Widget | Source | Refresh |
|--------|--------|---------|
| CPU % | `cpu_percent.sh` | 5s |
| Memory | `mem_usage.sh` | 5s |
| GPU (SSH only) | `gpu_status.sh` | 5s |
| Battery (local only) | `pmset` | 60s |
| Clock | `date` | 30s |
| Hostname | `hostname -s` | 3600s |
| SSH indicator (SSH only) | `ssh_status.sh` | 30s |

Each widget is rendered as a colored pill in the status bar. SSH sessions add GPU and SSH-indicator widgets and drop battery (servers do not have batteries). Local sessions do the reverse.

### Sessions and Popups

| Key | Session | Purpose |
|-----|---------|---------|
| `F11` | `agents` | Full-screen popup for AI coding agents, shows Claude usage metrics |
| `L` | `sidepanel` | VSCode-style popup panel (95% width) |
| `F12` | nested toggle | Disables outer prefix for SSH-inside-tmux |

The `agents` session is designed for running long-lived Claude Code instances. When you enter it, a session hook fires and the entire status bar swaps to display Claude usage metrics instead of system stats. When you switch away, the original system widgets restore automatically.

### Dual Theme System

| Context | Theme | Colors |
|---------|-------|--------|
| Local | Catppuccin Mocha Vibrant | Warm, high-contrast |
| SSH | Catppuccin Macchiato Vibrant | Cool, muted -- instantly tells you you're remote |

Theme selection is automatic. The config detects `$SSH_CLIENT` / `$SSH_TTY` at load time and sets both the powerkit theme path and pane border colors accordingly. There is nothing to configure.

<details>
<summary>Agents session: Claude usage metrics</summary>

When the active session is `agents`, the status bar pills are replaced with:

| Metric | Icon | Refresh |
|--------|------|---------|
| 5-hour usage | `` | 60s |
| 7-day usage | `󰃭` | 60s |
| Opus tokens | `` | 60s |
| Sonnet tokens | `` | 60s |
| Credits remaining | `󰠠` | 60s |
| Reset time | `󰦖` | 60s |

All metrics are sourced from `pk_claude_metric.sh`, which queries Claude API usage data. A session hook (`update_session_status.sh`) handles swapping and restoring the widget set, flushing the powerkit render cache on each transition.

</details>

<details>
<summary>Additional tmux features</summary>

| Feature | Detail |
|---------|--------|
| Copy mode | vi-mode keybindings (`v` to select, `y` to yank to system clipboard) |
| Mouse | Full mouse support for pane selection, resizing, and scroll |
| Session persistence | tmux-resurrect + tmux-continuum with auto-restore on |
| Text extraction | extrakto plugin for pulling text from pane output |
| Pane switching | fzf-pane-switch for fuzzy pane selection |
| Scrollback | 100,000 lines |
| Window naming | Automatic rename to current directory (`#{b:pane_current_path}`) |
| Nested sessions | F12 toggle disables outer prefix and dims the status bar |
| Pane borders | Shown only in `agents` session (top position with pane titles) |

</details>

---

## Modern CLI Tools

Every classic Unix tool has a faster, more informative modern replacement. These are installed by `setup.sh` and aliased in `.aliases-and-envs.zsh`.

<details open>
<summary>Core Replacements</summary>

| Classic | Modern | What changes |
|---------|--------|-------------|
| `find` | [`fd`](https://github.com/sharkdp/fd) + [`bfs`](https://github.com/tavianator/bfs) | 5x faster, colored output, sane defaults, breadth-first option |
| `grep` | [`ripgrep`](https://github.com/BurntSushi/ripgrep) (`rg`) | Respects .gitignore, multi-threaded, UTF-8 |
| `ls` | [`eza`](https://github.com/eza-community/eza) | Icons, git status, tree view, relative timestamps |
| `cat` | [`bat`](https://github.com/sharkdp/bat) | Syntax highlighting, line numbers, git integration |
| `top` | [`btop`](https://github.com/aristocratos/btop) | GPU/disk/network graphs, mouse support |
| `man` | [`tldr`](https://github.com/dbrgn/tealdeer) | Community examples instead of walls of text |
| `diff` | [`diff-so-fancy`](https://github.com/so-fancy/diff-so-fancy) | Word-level highlighting, cleaner git diffs |
| `echo` | [`gum`](https://github.com/charmbracelet/gum) | Styled prompts, spinners, confirmations, borders |

</details>

<details>
<summary>TUI Applications</summary>

| Tool | Purpose |
|------|---------|
| [`lazygit`](https://github.com/jesseduffield/lazygit) | Full git UI -- staging, branching, rebasing, stashing |
| [`lazydocker`](https://github.com/jesseduffield/lazydocker) | Docker container/image/volume management |
| [`lazysql`](https://github.com/jorgerojas26/lazysql) | Database browser (MySQL, PostgreSQL, SQLite) |
| [`visidata`](https://github.com/saulpw/visidata) | Swiss-army knife for tabular data (CSV, JSON, SQLite, etc.) |
| [`btop`](https://github.com/aristocratos/btop) | System resource monitor with graphs |
| [`neomutt`](https://github.com/neomutt/neomutt) | Terminal email client with isync, msmtp, notmuch |
| [`glow`](https://github.com/charmbracelet/glow) | Markdown renderer for the terminal |
| [`ctop`](https://github.com/bcicen/ctop) | Container metrics and monitoring |
| [`git-fuzzy`](https://github.com/bigH/git-fuzzy) | Fuzzy git diff, log, and status browser |

</details>

<details>
<summary>Data and Document Tools</summary>

| Tool | Purpose |
|------|---------|
| [`jq`](https://github.com/jqlang/jq) | JSON processor |
| [`yq`](https://github.com/mikefarah/yq) | YAML processor |
| [`pq`](https://github.com/sevagh/pq) | Protobuf processor |
| [`csvkit`](https://github.com/wireservice/csvkit) (`csvcut`) | CSV column extraction and manipulation |
| [`parquet-tools`](https://github.com/hangxie/parquet-tools) | Parquet file viewer and processor |
| [`rich-cli`](https://github.com/Textualize/rich-cli) | Rich terminal output (tables, syntax, markdown, Jupyter) |
| [`markitdown`](https://github.com/microsoft/markitdown) | Convert anything to Markdown (PDF, DOCX, EPUB, HTML) |
| [`chafa`](https://github.com/hpjansson/chafa) | Render images as ASCII art in terminal |

</details>

<details>
<summary>Development Tools</summary>

| Tool | Purpose |
|------|---------|
| [`shellcheck`](https://github.com/koalaman/shellcheck) | Shell script linter and static analysis |
| [`pm2`](https://github.com/Unitech/pm2) | Node.js process manager for background services |

</details>

<details>
<summary>Package Managers</summary>

| Manager | Language/Ecosystem |
|---------|-------------------|
| Homebrew | macOS system packages |
| apt | Linux system packages |
| npm + nvm | Node.js (with LTS auto-install) |
| Yarn | Node.js (alternative) |
| Bun | JavaScript runtime + package manager |
| Cargo + Rustup | Rust |
| Go | Go |
| uv | Python (fast pip replacement) |

</details>

---

## Editor: Helix

[Helix](https://helix-editor.com/) is the primary terminal editor. It is a post-modern modal editor with built-in LSP support, tree-sitter grammars, and multi-cursor editing out of the box -- no plugin manager required.

**Theme:** Material Palenight (transparent background, integrates with terminal opacity)

### Key Bindings

| Key | Action |
|-----|--------|
| `Ctrl-G` | Open lazygit in tmux popup |
| `Ctrl-T` | Fuzzy file finder (fzf-helix) |
| `Ctrl-S` | Save |
| `Ctrl-W` | Close buffer |
| `Ctrl-D` | Multi-cursor select (like VS Code) |
| `V` | Select entire line (visual line mode) |
| `Space-Q` | Quit |

> [!TIP]
> `Ctrl-D` works like VS Code's multi-cursor: in normal mode it selects the word under the cursor and enters select mode. Pressing `Ctrl-D` again in select mode extends to the next occurrence.

### Language Servers

| Server | Languages |
|--------|-----------|
| `bash-language-server` | Bash, Zsh, sh |
| `ruff` | Python (linting and formatting) |
| `ty` | Python (type checking, Astral) |
| `yaml-language-server` | YAML |
| `vscode-langservers-extracted` | HTML, CSS, JSON |
| `markdown-oxide` | Markdown |
| `simple-completion-language-server` | General completions |
| `taplo` | TOML |

<details>
<summary>Editor settings</summary>

| Setting | Value |
|---------|-------|
| Line numbers | Relative |
| Soft wrap | Enabled |
| Auto-format | On save |
| Bufferline | Always visible |
| Cursor shape (insert) | Bar |
| Cursor shape (select) | Underline |
| Inlay hints | Enabled |
| File picker | Shows hidden files |
| Completion timeout | 5ms |

</details>

---

## 60+ Custom Tools

Every tool is a single file in `tools/`. Python scripts use uv inline dependencies — no virtualenv needed.

<details>
<summary><strong>AI and Search</strong></summary>

| Tool | What it does |
|------|-------------|
| `oai` | OpenAI CLI wrapper |
| `gpt` | Alias for `oai` |
| `ddgs` | DuckDuckGo search from terminal |
| `google_search` | Google search from terminal |
| `summarize_url` | Fetch and summarize any URL with AI |
| `fetch_url` | Fetch URL content to markdown |
| `claude-session-digest` | Summarize Claude Code sessions |

</details>

<details>
<summary><strong>Data and Documents</strong></summary>

| Tool | What it does |
|------|-------------|
| `print_csv` | Pretty-print CSV files with colors |
| `colorize-columns` | Color columns in tabular output |
| `pdf_extract_pages` | Extract page ranges from PDFs |
| `pdf_to_png.py` | Convert PDF pages to PNG |
| `convert_ebook` | Convert between ebook formats |
| `rename_pdf` | AI-powered PDF renaming |
| `ocr_agent.sh` | OCR pipeline with AI |
| `ocr_book.py` | OCR entire books |
| `transcript_to_markdown` | Convert transcripts to markdown |
| `markdown_cleanup_agent.py` | Clean up markdown with AI |

</details>

<details>
<summary><strong>Email (NeoMutt ecosystem)</strong></summary>

| Tool | What it does |
|------|-------------|
| `mailsync` | Sync mail via isync/mbsync |
| `mailsync-daemon` | Background mail sync service |
| `beautiful_html_render` | Render HTML emails as markdown |
| `mutt-trim` | Trim email threads for replies |
| `mutt-viewical` | View calendar attachments |
| `msearch` | Search mail with notmuch |
| `msend` | Send emails from CLI |
| `mget` | Fetch specific emails |
| `mview` | View emails in terminal |

</details>

<details>
<summary><strong>System and Utilities</strong></summary>

| Tool | What it does |
|------|-------------|
| `rfz` | Ripgrep + fzf live search |
| `fzf-helix` | fzf file picker for Helix |
| `copy-last-output` | Copy last command output to clipboard |
| `system_info` | System information summary |
| `update-packages` | Update all package managers at once |
| `mount_remotes` | Mount remote filesystems |
| `rsync-all` | Sync dotfiles to remote machines |
| `start_aws` / `stop_aws` | AWS instance management |
| `ctx-index` / `ctx-peek` / `ctx-tree` | Codebase context generation tools |
| `watch_dir` | Watch directory for changes |
| `tagger` | File tagging utility |
| `split_by_size` | Split files by size |

</details>

> Every tool is a single file. No frameworks, no build steps. Read it, copy it, change it.

---

## Claude AI Integration

Configuration lives in `maintained_global_claude/` and is symlinked into `~/.claude/` during setup.

### Agents

| Agent | Purpose |
|-------|---------|
| `codebase-researcher` | Deep codebase exploration and analysis |
| `context-researcher` | Generate context files for progressive disclosure |
| `modern-translation` | Translate code to modern patterns/libraries |
| `plan-writer` | Write detailed implementation plans |
| `spec-interviewer` | Interview users to create specifications |
| `structural-completeness-reviewer` | Review code for structural completeness |
| `test-generator` | Generate comprehensive test suites |
| `vault-analyst` | Analyze knowledge vault contents |

### Skills

| Skill | Purpose |
|-------|---------|
| `create-plan` | Spec-driven development workflow |
| `data-visualization-techniques` | Chart/graph/dashboard guidance |
| `design-principles` | UI/UX design patterns |
| `log-to-daily` | Session logging to Dendron vault |
| `media-manager` | Plex media stack management |
| `polish` | Transform MVPs to production-grade apps |
| `request` | Quick-add media to Plex |

### Commands

| Command | Purpose |
|---------|---------|
| `/research` | Generate context files |
| `/arewedone` | Structural completeness review |
| `/generate-tests` | Generate test suites from specs |
| `/process-parallel` | Create parallel processing pipelines |

### Hooks

Hooks fire on session events: `notification.py` (desktop alerts), `pre_tool_use.py` (guardrails), `post_tool_use.py` (post-processing), `pre_compact.py` (context preservation), `session_start.py` (initialization), `stop.py` / `subagent_stop.py` (cleanup).

> The `agents` tmux session (F11) is purpose-built for AI work — status bar shows live Claude API usage, token counts, and credit balance.

---

## Architecture

```
dotfiles/
├── shell/          # Zsh config, aliases, paths, helper functions
├── tmux/           # tmux config + status bar scripts
├── fzf/            # fzf config, env vars, keybindings
├── editors/        # Helix config + themes + language servers
├── preview/        # fzf-preview dispatcher + format-specific previewers
├── tools/          # 60+ CLI utilities (AI, data, system)
├── install/        # Installation functions + helpers
├── maintained_global_claude/  # Claude Code agents, skills, commands, hooks
├── mutt/           # NeoMutt email client config
├── iterm2/         # iTerm2 profiles + SSH theme switching
├── linters/        # pylintrc, sourcery config
├── local/          # Machine-specific secrets (git-ignored)
├── codex/          # OpenAI Codex config
├── setup.sh        # Entry point — one command to install everything
└── CLAUDE.md       # AI assistant instructions for this repo
```

### Setup Flow

1. `setup.sh` sources `install/install_functions.sh`
2. Detects OS (`mac` vs `linux`)
3. Installs Homebrew (macOS) or uses apt (Linux)
4. Creates `~/dotfiles/local/` for secrets
5. Runs `install_dotfiles` — creates ~160 symlinks
6. Installs 60+ tools via `install_if_missing` guards (idempotent)
7. Builds Helix grammars, installs tmux plugins
8. Sets up NeoMutt email (isync, msmtp, notmuch)

### Shell Loading Order

```
.zshrc
├── Powerlevel10k instant prompt
├── Zprezto init
├── helper_functions.sh
├── gum_utils.sh
├── lscolors.sh
├── .aliases-and-envs.zsh
├── .local_env.sh (secrets, git-ignored)
├── .paths.zsh
├── .fzf.zsh + .fzf-config.zsh
└── .p10k.zsh (prompt theme)
```

> Everything is a symlink. Edit in `~/dotfiles/`, changes appear everywhere instantly. No copy-paste, no drift.

---

## Make It Yours

- **Change the theme**: Edit `tmux/catppuccin-*.sh` or `editors/hx_config.toml` (theme line)
- **Add a tool**: Drop a script in `tools/`, it's auto-symlinked to `~/tools/`
- **Add a preview format**: Add a `case` branch in `preview/fzf-preview.sh`
- **Add an alias**: Edit `shell/.aliases-and-envs.zsh`
- **Add a tmux widget**: Write a script in `tmux/scripts/`, reference it in `.tmux.conf`
- **Machine-specific config**: Put secrets in `local/.local_env.sh` (git-ignored)
- **Claude agents**: Add `.md` files to `maintained_global_claude/agents/`

---

## Documentation

| Guide | Covers |
|-------|--------|
| [`docs/tmux.md`](docs/tmux.md) | Keybindings, sessions, status bar, themes |
| [`docs/fzf.md`](docs/fzf.md) | Fuzzy finder config, preview system, keybindings |
| [`docs/setup.md`](docs/setup.md) | Installation deep-dive, OS-specific notes |
| [`docs/tools.md`](docs/tools.md) | Every tool with usage examples |

---

## Built With

This setup stands on the shoulders of [fzf](https://github.com/junegunn/fzf), [Powerlevel10k](https://github.com/romkatv/powerlevel10k), [Zprezto](https://github.com/sorin-ionescu/prezto), [tmux](https://github.com/tmux/tmux), [Catppuccin](https://github.com/catppuccin), [Helix](https://helix-editor.com), [gum](https://github.com/charmbracelet/gum), [eza](https://github.com/eza-community/eza), [bat](https://github.com/sharkdp/bat), [ripgrep](https://github.com/BurntSushi/ripgrep), [fd](https://github.com/sharkdp/fd), [bfs](https://github.com/tavianator/bfs), [lazygit](https://github.com/jesseduffield/lazygit), [tmux-powerkit](https://github.com/fabioluciano/tmux-powerkit), and the many other open-source projects that make terminal life worth living.

---

## License

MIT.
