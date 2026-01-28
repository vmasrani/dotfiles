#!/bin/bash
# shellcheck shell=bash
# RunPod-specific functions for bridging ephemeral /root to persistent /workspace/home

_RUNPOD_FUNCS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
_RUNPOD_DOTFILES_ROOT="$(dirname "$_RUNPOD_FUNCS_DIR")"
source "$_RUNPOD_DOTFILES_ROOT/install/install_functions.sh"

bridge_root_to_workspace() {
    local workspace_home="/workspace/home"
    local workspace_dotfiles="/workspace/dotfiles"
    local root="/root"

    if [[ ! -d "$workspace_home" ]]; then
        gum_error "/workspace/home does not exist — run setup_runpod.sh first"
        return 1
    fi

    gum_dim "Bridging $root -> $workspace_home ..."

    # Bridge dotfiles repo itself
    ensure_symlink "$workspace_dotfiles" "$root/dotfiles" "true"

    # Directories to bridge
    local -a dirs=(
        .config .local .cache .cargo .rustup .nvm .fzf .tmux .zprezto
        .ssh .claude .codex .bun bin go tools dev
    )

    for d in "${dirs[@]}"; do
        [[ -d "$workspace_home/$d" ]] && ensure_symlink "$workspace_home/$d" "$root/$d" "true"
    done

    # Dotfiles (individual files) to bridge
    local -a dotfiles=(
        .zshrc .tmux.conf .gitconfig .bashrc .bash_profile .zshenv .zprofile
        .zpreztorc .zlogin .zlogout .p10k.zsh .vimrc .pylintrc .sourcery.yaml
        .aliases-and-envs.zsh .paths.zsh .profile .bash_logout
        .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env.zsh
        .local_env.sh .secrets .mutt_secrets
        helper_functions.sh gum_utils.sh lscolors.sh update_startup.sh
    )

    for f in "${dotfiles[@]}"; do
        [[ -e "$workspace_home/$f" ]] && ensure_symlink "$workspace_home/$f" "$root/$f" "true"
    done

    gum_dim "Bridge complete."
}
