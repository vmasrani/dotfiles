# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

This is a comprehensive dotfiles repository that automates the setup and configuration of a development environment across Linux and macOS systems. The codebase is organized by functionality: shell configurations, tools, editor configs, and installation scripts.

## Key Commands

### Initial Setup
```bash
./setup.sh  # Master installation script - installs all tools and creates symlinks
```

### Shell Configuration
After running setup, refresh your shell environment:
```bash
source ~/.zshrc  # or use alias: refresh
```

### Linting and Validation
```bash
shellcheck setup.sh                    # Lint shell scripts
shellcheck install/*.sh tools/*.sh     # Lint all shell files
```

### Common Development Tools Installed
- **Shell**: zsh with Prezto framework and Powerlevel10k theme
- **Editor**: Helix (hx) with LSP support, Vim
- **Terminal**: tmux with custom configuration and popup support
- **Git**: Enhanced with git-fuzzy and diff-so-fancy
- **Search**: ripgrep (rg), fd, fzf with extensive configuration
- **File viewing**: bat, eza with icons and git integration
- **Python**: uv package manager, machine learning helpers
- **Network**: curl, wget for data transfer
- **Data processing**: jq, yq, parquet-tools

## Architecture and Conventions

### Directory Structure
- `shell/`: Shell configurations (.zshrc, .bashrc, aliases, environment variables)
- `install/`: Tool installation scripts with OS detection (Linux/macOS)
- `tools/`: Utility scripts for file management, AWS operations, system info
- `tmux/`: Tmux configuration with custom key bindings and session management
- `editors/`: Vim and Helix configurations with LSP setup
- `local/`: Local environment settings and secrets (not tracked in git)
- `fzf/`: Fuzzy finder configurations and environment setup
- `linters/`: Code quality configurations (pylint, sourcery, pyright)
- `preview/`: File preview scripts for various formats
- `claude/`: Claude AI integration and allowed tools ruleset

### Installation System Architecture
The setup uses a sophisticated modular approach:

1. **OS Detection**: `install_functions.sh` detects Linux vs macOS at runtime
2. **Conditional Installation**: Uses `install_if_missing` and `install_if_dir_missing` functions
3. **Package Manager Abstraction**: `install_on_brew_or_mac` handles apt/brew differences
4. **Fallback Strategy**: Downloads binaries when package managers fail
5. **Symlink Management**: Creates symlinks for all dotfiles to their proper locations
6. **Helper Functions**: Reusable functions in `shell/helper_functions.sh`

### Key Aliases and Functions
File operations are heavily enhanced:
- **File listing**: `l` (detailed), `lt` (by time), `lf` (by size), `ld` (directories only)
- **Tree views**: `t`, `t1`, `t2`, `t3`, `t4` (with depth levels), excludes common dev directories
- **Navigation**: `..`, `.1` through `.9` for quick parent directory access
- **Enhanced commands**: 
  - `fd -HI` (find with hidden and ignored files)
  - `rg --no-ignore` (ripgrep without ignore files)
  - `bat -n --color=always` (cat with line numbers and color)

### Environment Variables and PATH
Complex PATH management system in `shell/.aliases-and-envs.zsh`:
- Consolidates multiple tool paths (Node, Go, Python, npm, etc.)
- Removes duplicates automatically
- Handles version-specific paths (e.g., Node v18.20.8)
- Sets PYTHONPATH for custom modules

### Python Development Setup
- **Package Manager**: `uv` for modern Python dependency management
- **Custom Modules**: Machine learning helpers at `~/.python`
- **ML Tools**: PyTorch, scikit-learn, pandas, matplotlib pre-configured
- **Development Tools**: IPython, Jupyter, rich for enhanced REPL experience

### Security Considerations
- **Secrets Management**: Dedicated `local/` directory for API keys and tokens
- **Git Security**: `.gitignore` prevents sensitive data commits
- **SSL Warning**: Git config disables SSL verification (review this setting)
- **Allowed Tools**: Claude integration has extensive tool restrictions in `claude/allowed-tools-ruleset.txt`

### Cross-Platform Compatibility
- **OS Detection**: Automatic Linux/macOS detection
- **Package Managers**: Seamless apt (Linux) and brew (macOS) integration
- **Binary Fallbacks**: Downloads from GitHub releases when package managers unavailable
- **Path Handling**: OS-specific path configurations

## Custom Tools Available

### File and System Management
Located in `~/dotfiles/tools/`:
- `colorize-columns.sh`: Add color coding to columnar output
- `find_files.sh`: Enhanced file finding with filters
- `rfz.sh`: Fuzzy file search integration
- `system_info.sh`: Comprehensive system information display
- `copy.sh`: Enhanced file copying utilities
- `split_by_size.sh`: Split large files by size

### Development Workflow
- `fzf-helix.sh`: Fuzzy finder integration with Helix editor
- `imgcat.sh`: Display images in terminal (iTerm2 compatible)

### Remote Operations
- `start_aws.sh` / `stop_aws.sh`: AWS instance management
- `rsync-all.sh`: Batch rsync operations
- `run-command-on-all-addresses.sh`: Execute commands across multiple hosts
- `mount_remotes.sh`: Mount remote filesystems
- `sshget`: Secure file retrieval over SSH

### File Processing
- `symlink_pdfs.sh`: Create organized PDF symlinks
- Preview scripts for various formats (feather, numpy, torch files)

## tmux Configuration

Extensive tmux setup in `tmux/.tmux.conf`:
- **Custom Key Bindings**: Vi-mode navigation, pane management
- **Session Management**: Automatic session restoration
- **Popup Windows**: Integrated terminal popups for quick tasks
- **Plugin System**: TPM (Tmux Plugin Manager) integration
- **Status Bar**: Custom status bar with system information