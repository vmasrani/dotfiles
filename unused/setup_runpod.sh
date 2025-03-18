#!/bin/bash
set -e

apt update && apt upgrade -y
apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
apt install locales
locale-gen en_US.UTF-8
chsh -s $(which zsh)

my_dirs=(
    .bash_history
    .bashrc
    .cache
    .cargo
    .conda
    .config
    .fzf
    .ipython
    .jupyter
    .launchpadlib
    .local
    .nv
    .nvm
    .python
    .rustup
    .ssh
    .tmux
    .zprezto
    bin
    dev
    dotfiles
    go
    hypers
    miniconda
)

for dir in "${my_dirs[@]}"; do
	source="/workspace/$dir"
	target="$HOME/$dir"
	ln -sf "$source" "$target"
	echo "Linked $(basename "$source") to $target"
done

files=(.aliases-and-envs.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env.zsh .gitconfig .p10k.zsh .profile .pylintrc .sourcery.yaml .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc .curlrc)
for file in "${files[@]}"; do
	echo "Linking $file from dotfiles to home directory."
	ln -sf "$HOME"/dotfiles/"$file" "$HOME"/"$file"
done


echo "Linking helix from dotfile to ~/.config/helix"
mkdir -p ~/.config/helix/
ln -sf ~/dotfiles/hx_config.toml ~/.config/helix/config.toml
ln -sf ~/dotfiles/hx_languages.toml  ~/.config/helix/languages.toml
