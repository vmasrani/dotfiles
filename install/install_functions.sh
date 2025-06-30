#!/bin/bash
# shellcheck shell=bash

source ~/dotfiles/shell/helper_functions.sh

# Detect operating system
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS_TYPE="mac"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS_TYPE="linux"
else
    echo "Unsupported operating system: $OSTYPE"
    exit 1
fi


install_on_brew_or_mac() {
    local linux_package=$1
    local mac_package=${2:-$1}  # Use first arg if second not provided

    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo apt -y install "$linux_package"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install "$mac_package"
    fi
}


install_if_missing() {
    local command_name=$1
    local install_function=$2

    if ! command_exists "$command_name"; then
        echo "$command_name is not installed. Installing $command_name..."
        $install_function
        echo "$command_name installed successfully."
    else
        echo "$command_name is already installed."
    fi
}

install_if_dir_missing() {
    local dir_path=$1
    local install_function=$2

    if [ ! -d "$dir_path" ]; then
        echo "Directory $dir_path does not exist. Installing..."
        $install_function
        echo "Installation completed successfully."
    else
        echo "Directory $dir_path already exists."
    fi
}

install_dotfiles() {

    mkdir -p "$HOME"/bin
    mkdir -p "$HOME/dev/projects"
    mkdir -p "$HOME/.config/helix"
    # chmod bash files
    find $HOME/dotfiles -name "*.sh" -type f -exec chmod +x {} \;
    touch $HOME/dotfiles/local/.local_env.sh

    echo "Creating symbolic links..."

  # Define base paths
    local dotfiles="$HOME/dotfiles"
    local bin="$HOME/bin"
    local home="$HOME"

    # Create an array of source:target pairs
    declare -a file_pairs=(
        "$dotfiles/tools/rfz.sh:$bin/rfz"
        "$dotfiles/tools/copy.sh:$bin/copy"
        "$dotfiles/tools/sshget:$bin/sshget"
        "$dotfiles/tools/fzf-helix.sh:$bin/fzf-helix"
        "$dotfiles/tools/rsync-all.sh:$bin/rsync-all"
        "$dotfiles/tools/colorize-columns.sh:$bin/colorize-columns"
        "$dotfiles/tools/convert_ebook.py:$bin/convert_ebook"
        "$dotfiles/tools/imgcat.sh:$bin/imgcat"
        # "$dotfiles/tmux/show-tmux-popup.sh:$bin/show-tmux-popup"

        # Preview files
        "$dotfiles/preview/fzf-preview.sh:$bin/fzf-preview"
        "$dotfiles/preview/torch-preview.sh:$bin/torch-preview"
        "$dotfiles/preview/npy-preview.py:$bin/npy-preview"
        "$dotfiles/preview/feather-preview.py:$bin/feather-preview"

        # editor dotfiles
        "$dotfiles/tmux/.tmux.conf:$home/.tmux.conf"
        "$dotfiles/editors/.vimrc:$home/.vimrc"

        # linters dotfiles
        "$dotfiles/linters/.pylintrc:$home/.pylintrc"
        "$dotfiles/linters/.sourcery.yaml:$home/.sourcery.yaml"

        # Shell dotfiles
        "$dotfiles/fzf/.fzf-config.zsh:$home/.fzf-config.zsh"
        "$dotfiles/fzf/.fzf.bash:$home/.fzf.bash"
        "$dotfiles/fzf/.fzf.zsh:$home/.fzf.zsh"
        "$dotfiles/fzf/.fzf-env.zsh:$home/.fzf-env.zsh"


        # Shell dotfiles
        "$dotfiles/shell/.p10k.zsh:$home/.p10k.zsh"
        "$dotfiles/shell/.aliases-and-envs.zsh:$home/.aliases-and-envs.zsh"
        "$dotfiles/shell/.bash_logout:$home/.bash_logout"
        "$dotfiles/shell/.bash_profile:$home/.bash_profile"
        "$dotfiles/shell/.bashrc:$home/.bashrc"
        "$dotfiles/shell/.zlogin:$home/.zlogin"
        "$dotfiles/shell/.zlogout:$home/.zlogout"
        "$dotfiles/shell/.zpreztorc:$home/.zpreztorc"
        "$dotfiles/shell/.zprofile:$home/.zprofile"
        "$dotfiles/shell/.profile:$home/.profile"
        "$dotfiles/shell/.zshenv:$home/.zshenv"
        "$dotfiles/shell/.zshrc:$home/.zshrc"
        "$dotfiles/shell/lscolors.sh:$home/lscolors.sh"
        "$dotfiles/shell/helper_functions.sh:$home/helper_functions.sh"

        # local dotfiles
        "$dotfiles/local/.local_env.sh:$home/.local_env.sh"
        "$dotfiles/local/.secrets:$home/.secrets"

        # agents
        "$dotfiles/cli_agents/agent.py:$bin/agent"

        # helix
        "$dotfiles/editors/hx_languages.toml:$home/.config/helix/languages.toml"
        "$dotfiles/editors/hx_config.toml:$home/.config/helix/config.toml"


    )

    # Create all symlinks in a single loop
    for pair in "${file_pairs[@]}"; do
        source="${pair%%:*}"
        target="${pair#*:}"
        echo "Linking $(basename "$source") to $target"
        ln -sf "$source" "$target"
        chmod +x "$source"
    done

}



install_local_dotfiles() {
    mkdir -p "$HOME/dotfiles/local"
    touch "$HOME/dotfiles/local/.local_env.sh"
    touch "$HOME/dotfiles/local/.secrets"
}


install_zsh() {
    read -p "zsh is not installed. Do you want to install zsh, build-essential, and vim? (y/n) " choice
    case "$choice" in
        y|Y )
            if [[ "$OS_TYPE" == "linux" ]]; then
                if [ "$(id -u)" -eq 0 ]; then
                    apt update && apt upgrade -y
                    apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                    chsh -s $(which zsh)
                else
                    sudo apt update && sudo apt upgrade -y
                    sudo apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                    sudo chsh -s $(which zsh) $USER
                fi
            elif [[ "$OS_TYPE" == "mac" ]]; then
                brew update
                brew install zsh vim
                chsh -s $(which zsh)
            fi
            echo "Installation complete. Please restart your shell to use zsh."
            ;;
        * )
            echo "Skipping installation."
            return 1
            ;;
    esac
}




install_cargo() {
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
}


install_uv() {
    curl -LsSf https://astral.sh/uv/install.sh | sh
    uv venv --python 3.12 $HOME/ml3

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
    bash install/install_npm.sh
}

install_go() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo add-apt-repository -y ppa:longsleep/golang-backports
        sudo apt update
        sudo apt install golang-go -y
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install go
    fi
}

install_fzf() {
    git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf"
    "$HOME/.fzf/install" --all --no-update-rc
}

install_helix() {
    bash install/install_helix.sh
}

install_glow() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/charmbracelet/glow@latest
}

install_lazygit() {
    export PATH="$HOME/go/bin:$PATH"
    go install github.com/jesseduffield/lazygit@latest
}


install_bfs() {
    install_on_brew_or_mac "bfs" "tavianator/tap/bfs"
}

install_shellcheck() {
    install_on_brew_or_mac "shellcheck"
}

install_claude_code_cli() {
    npm install -g @anthropic-ai/claude-code
}




install_yq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        sudo snap install yq
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install yq
    fi
}



install_xsel() {
    install_on_brew_or_mac "xclip xsel"
}


install_nbpreview() {
    uv tool install nbcat
}

install_tmux() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/tmux" "n0p.me/bin/tmux" && chmod +x "$HOME/bin/tmux"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install tmux
    fi
    echo "tmux installed successfully."
}

install_rg() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/rg" "n0p.me/bin/rg" && chmod +x "$HOME/bin/rg"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install ripgrep
    fi
    echo "rg installed successfully."
}

install_fd() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/fd" "n0p.me/bin/fd" && chmod +x "$HOME/bin/fd"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install fd
    fi
    echo "fd installed successfully."
}

install_jq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/jq" "n0p.me/bin/jq" && chmod +x "$HOME/bin/jq"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install jq
    fi
    echo "jq installed successfully."
}

install_pq() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        wget -O "$HOME/bin/pq" "https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq" && chmod +x "$HOME/bin/pq"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        wget -O "$HOME/bin/pq" "https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq" && chmod +x "$HOME/bin/pq"
    fi
    echo "pq installed successfully."
}

install_bat() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        bash install/install_tar.sh "https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install bat
    fi
    echo "bat installed successfully."
}

install_eza() {
    if [[ "$OS_TYPE" == "linux" ]]; then
        bash install/install_tar.sh "https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"
    elif [[ "$OS_TYPE" == "mac" ]]; then
        brew install eza
    fi
    echo "eza installed successfully."
}

install_parquet_tools() {
    go install github.com/hangxie/parquet-tools@latest
    echo "parquet-tools installed successfully."
}

install_fzf_tab_completion() {
    git clone https://github.com/lincheney/fzf-tab-completion "$HOME/.zprezto/contrib/fzf-tab-completion"
    echo "fzf-tab-completion installed successfully."
}

install_ml_helpers() {
    echo "WARNING!!!"
    echo "REPLACE THIS WITH UV"
    git clone https://github.com/vmasrani/machine_learning_helpers.git "$HOME/.python"
    echo "machine_learning_helpers installed successfully."
}


install_hypers() {
    echo "WARNING!!!"
    echo "REPLACE THIS WITH UV"
    git clone https://github.com/vmasrani/hypers.git "$HOME/hypers"
    echo "hypers installed successfully."
}

install_tpm() {
    git clone https://github.com/tmux-plugins/tpm "$HOME/.tmux/plugins/tpm"
    echo "tmux plugin manager installed successfully."
}

install_git_fuzzy() {
    git clone https://github.com/bigH/git-fuzzy.git "$HOME/bin/_git-fuzzy"
    ln -s "$HOME/bin/_git-fuzzy/bin/git-fuzzy" "$HOME/bin/git-fuzzy"
    echo "git-fuzzy setup completed."
}

install_diff_so_fancy() {
    git clone https://github.com/so-fancy/diff-so-fancy.git "$HOME/bin/_diff-so-fancy"
    ln -s "$HOME/bin/_diff-so-fancy/diff-so-fancy" "$HOME/bin/diff-so-fancy"
    git config --global core.pager "diff-so-fancy | less --tabs=4 -RF"
    git config --global interactive.diffFilter "diff-so-fancy --patch"
    echo "diff-so-fancy setup completed."
}

install_finditfaster() {
    cp ~/dotfiles/tools/find_files.sh "$(find ~/.cursor-server/extensions -type d -name 'tomrijndorp*' 2>/dev/null)" || :
    echo "find_files.sh copied to cursor extension directory successfully."
}

install_zprezto() {
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
    echo "zprezto installed successfully."
}

