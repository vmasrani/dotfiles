#!/bin/bash
# shellcheck shell=bash
# ===================================================================
# RunPod Dotfiles Setup Script
# ===================================================================
# Alternative entry point for RunPod pods with persistent /workspace.
# Phase A: Install dotfiles into /workspace/home (persistent)
# Phase B: Bridge /root -> /workspace/home (ephemeral -> persistent)
# Phase C: Install tools
# Usage: ./setup_runpod.sh
# ===================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"

# _setup_sudo_shim (in install_functions.sh) handles the sudo-as-root case
source "$SCRIPT_DIR/install/install_functions.sh"
source "$SCRIPT_DIR/install/runpod_functions.sh"
source "$SCRIPT_DIR/shell/.aliases-and-envs.zsh"
source "$SCRIPT_DIR/shell/gum_utils.sh"

# --- Phase A: Install into persistent /workspace/home ---
gum_info "Phase A: Installing dotfiles into /workspace/home ..."

mkdir -p /workspace/home

# zsh must be available before dotfiles are symlinked (shell configs depend on it)
install_if_missing zsh install_zsh

# Ensure dotfiles repo is at /workspace/dotfiles
if [[ ! -d "/workspace/dotfiles" ]]; then
    if [[ -d "$SCRIPT_DIR" && "$SCRIPT_DIR" != "/workspace/dotfiles" ]]; then
        ln -sf "$SCRIPT_DIR" /workspace/dotfiles
    fi
fi

install_if_dir_missing /workspace/dotfiles/local install_local_dotfiles
install_dotfiles "/workspace/dotfiles" "/workspace/home"

# --- Phase B: Bridge /root -> /workspace/home ---
gum_info "Phase B: Bridging /root -> /workspace/home ..."
bridge_root_to_workspace

# --- Phase C: Install tools ---
gum_info "Phase C: Installing tools ..."

install_meslo_font

# install essentials
install_if_dir_missing ~/.zprezto install_zprezto
install_if_dir_missing ~/.zprezto/contrib/fzf-tab-completion install_fzf_tab_completion
install_if_dir_missing ~/.tmux/plugins/tpm install_tpm
install_catppuccin_tmux
install_if_dir_missing ~/bin/_git-fuzzy install_git_fuzzy
install_if_dir_missing ~/bin/_diff-so-fancy install_diff_so_fancy

# install binaries
install_if_missing unzip install_unzip
install_if_missing bun install_bun
install_if_missing nvm install_nvm
install_if_missing npm install_npm
install_if_missing yarn install_yarn
install_if_missing pm2 install_pm2
install_if_missing go install_go
install_if_missing bfs install_bfs
install_if_missing eza install_eza
install_if_missing fzf install_fzf
install_if_missing cargo install_cargo
install_if_missing uv install_uv
install_if_missing tldr install_tealdeer
install_if_missing hx install_helix
install_if_missing glow install_glow
install_if_missing lazygit install_lazygit
install_if_missing lazydocker install_lazydocker
install_if_missing lazysql install_lazysql
install_if_missing btop install_btop
install_if_missing ctop install_ctop
install_if_missing bat install_bat
install_if_missing tmux install_tmux
install_if_missing rg install_rg
install_if_missing fd install_fd
install_if_missing jq install_jq
install_if_missing pq install_pq
install_if_missing yq install_yq
install_if_missing csvcut install_csvcut
install_if_missing parquet-tools install_parquet_tools
install_if_missing claude install_claude_code_cli
install_if_missing chafa install_chafa
install_if_missing xclip install_xclip
install_if_missing xsel install_xsel

# install tools that depend on uv (must be after uv installation)
install_if_missing rich install_rich_cli
install_if_missing markitdown install_markitdown
install_if_missing vd install_visidata
install_if_missing ty install_ty

# install language servers (must be after npm and cargo installation)
install_if_missing shellcheck install_shellcheck
install_if_missing bash-language-server install_bash_language_server
install_if_missing yaml-language-server install_yaml_language_server
install_if_missing vscode-html-language-server install_vscode_langservers_extracted
install_if_missing markdown-oxide install_markdown_oxide
install_if_missing simple-completion-language-server install_simple_completion_language_server
install_if_missing taplo install_taplo_cli

# update helix grammars
update_helix_grammars

gum_box_success "RunPod setup completed. Run 'exec zsh' to start a fresh shell."
