#!/bin/bash

install_if_missing() {
    local command_name=$1
    local install_function=$2

    if ! command -v "$command_name" &>/dev/null; then
        echo "$command_name is not installed. Installing $command_name..."
        $install_function
        echo "$command_name installed successfully."
    else
        echo "$command_name is already installed."
    fi
}


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
    conda init zsh
}

install_cargo() {
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
}

install_tealdeer() {
    source "$HOME/.cargo/env"
    export PATH="$HOME/.cargo/bin:$PATH"
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
    "$HOME/.fzf/install" --no-update-rc
}

install_helix() {
    bash install_helix.sh
}

install_glow() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/charmbracelet/glow@latest
}

install_lazygit() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/jesseduffield/lazygit@latest
}

install_pipx() {
    python3 -m pip install --user pipx
    export PATH="$HOME/.local/bin:$PATH"
    python3 -m pipx ensurepath
}

install_nbpreview() {
    export PATH="$HOME/.local/bin:$PATH"
    pipx install nbpreview
}

install_terminaltexteffects() {
    export PATH="$HOME/.local/bin:$PATH"
    pipx install terminaltexteffects
}
