#!/bin/bash

install_miniconda() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        mkdir -p ~/miniconda
        wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda/miniconda.sh
        bash ~/miniconda/miniconda.sh -b -u -p ~/miniconda
        rm -rf ~/miniconda/miniconda.sh
    else
        echo "Unsupported OS. Please install Miniconda manually."
        exit 1
    fi
    export PATH="$HOME/miniconda/bin:$PATH"
    echo "export PATH=\"\$HOME/miniconda/bin:\$PATH\"" >>~/.zshrc
    conda init zsh
}

install_cargo() {
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
}

install_tealdeer() {
    source "$HOME/.cargo/env"
    cargo install tealdeer
    tldr --update
}

install_zprezto() {
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "${ZDOTDIR:-$HOME}/.zprezto"
}

install_npm() {
    bash install_npm.sh
}

install_go() {
    sudo bash update-golang/update-golang.sh
    source /etc/profile.d/golang_path.sh
}

install_fzf() {
    git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf"
    "$HOME/.fzf/install"
}
