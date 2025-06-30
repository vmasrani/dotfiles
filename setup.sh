#!/bin/bash
# shellcheck shell=bash
# shellcheck source=install/install_functions.sh
# ===================================================================
# Dotfiles Setup Script
# ===================================================================
# Installs and configures all dotfiles and required tools
# Usage: ./setup.sh
# ===================================================================

set -e


# Source the installation functions
source "$(dirname "$0")/install/install_functions.sh"
source "$(dirname "$0")/shell/.aliases-and-envs.zsh"
# install zsh
install_if_missing zsh install_zsh

# install dotfiles
install_if_dir_missing ~/dotfiles/local install_local_dotfiles

install_dotfiles

# install essentials
install_if_dir_missing ~/.zprezto install_zprezto                                # Zsh framework for configuration with themes and plugins
install_if_dir_missing ~/.zprezto/contrib/fzf-tab-completion install_fzf_tab_completion  # Tab completion with fuzzy search for Zsh
install_if_dir_missing ~/.python install_ml_helpers                              # Python utilities for machine learning tasks
install_if_dir_missing ~/hypers install_hypers                                   # Hyperparameter optimization tools and utilities
install_if_dir_missing ~/.tmux/plugins/tpm install_tpm                           # Tmux Plugin Manager for extending tmux functionality
install_if_dir_missing ~/bin/_git-fuzzy install_git_fuzzy                        # Fuzzy finder for git commands and operations
install_if_dir_missing ~/bin/_diff-so-fancy install_diff_so_fancy                # Git diff output formatter with improved readability
install_if_dir_missing ~/.cursor-server/extensions install_finditfaster          # Fast file finder extension for Cursor editor

# install binaries
install_if_missing npm install_npm # Node.js package manager
install_if_missing go install_go # Go programming language and toolchain
install_if_missing bfs install_bfs # Breadth-first search for filesystem traversal
install_if_missing eza install_eza # Modern replacement for ls with color and git integration
install_if_missing fzf install_fzf # Command-line fuzzy finder for files, history, and more
install_if_missing cargo install_cargo # Rust package manager and build system
install_if_missing tldr install_tealdeer # Simplified and community-driven man pages
install_if_missing hx install_helix # Modern terminal-based text editor
install_if_missing glow install_glow # Markdown terminal viewer with style
install_if_missing lazygit install_lazygit # Terminal UI for git commands
# install_if_missing nbpreview install_nbpreview # Jupyter notebook terminal previewer # TODO: add this back in
# install_if_missing tte install_terminaltexteffects # Terminal text effects and animations
install_if_missing bat install_bat # Syntax highlighting cat replacement
install_if_missing tmux install_tmux # Terminal multiplexer for multiple sessions
install_if_missing rg install_rg # Fast recursive grep alternative
install_if_missing fd install_fd # Fast find alternative
install_if_missing jq install_jq # Command-line JSON processor
install_if_missing pq install_pq # Command-line protobuf processor
install_if_missing yq install_yq # Command-line yaml processor
install_if_missing parquet-tools install_parquet_tools # Parquet file viewer and processor
install_if_missing shellcheck install_shellcheck # Shell script linter
install_if_missing claude install_claude_code_cli # Claude code CLI

echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."
