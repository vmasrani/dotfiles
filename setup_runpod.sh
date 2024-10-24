#!/bin/bash
set -e

apt update && apt upgrade -y
apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
chsh -s $(which zsh)

my_dirs=(
    .bash_history
    .bashrc
    .cache
    .cargo
    .conda
    .config
    .fzf
    .gotty.auth
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

./setup.sh
