#!/bin/bash
set -e

# Source the installation functions
source "$(dirname "$0")/install_functions.sh"

# install zsh
install_if_missing zsh install_zsh

# install dotfiles
install_if_dir_missing ~/bin install_dotfiles

# install essentials
install_if_dir_missing ~/miniconda install_miniconda
install_if_dir_missing ~/.zprezto install_zprezto
install_if_dir_missing ~/.zprezto/contrib/fzf-tab-completion install_fzf_tab_completion
install_if_dir_missing ~/.python install_ml_helpers
install_if_dir_missing ~/hypers install_hypers
install_if_dir_missing ~/.tmux/plugins/tpm install_tpm
install_if_dir_missing ~/bin/_git-fuzzy install_git_fuzzy
install_if_dir_missing ~/bin/_diff-so-fancy install_diff_so_fancy
install_if_dir_missing ~/.cursor-server/extensions install_finditfaster

# install binaries
install_if_missing eza install_eza
install_if_missing fzf install_fzf
install_if_missing mamba install_mamba
install_if_missing mamba install_ml3_env
install_if_missing cargo install_cargo
install_if_missing tldr install_tealdeer
install_if_missing npm install_npm
install_if_missing go install_go
install_if_missing hx install_helix
install_if_missing glow install_glow
install_if_missing lazygit install_lazygit
install_if_missing pipx install_pipx
install_if_missing nbpreview install_nbpreview
install_if_missing tte install_terminaltexteffects
install_if_missing bat install_bat
install_if_missing tmux install_tmux
install_if_missing rg install_rg
install_if_missing fd install_fd
install_if_missing jq install_jq
install_if_missing pq install_pq
install_if_missing bat install_bat
install_if_missing parquet-tools install_parquet_tools

echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."
