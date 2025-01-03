#!/bin/bash

source ~/dotfiles/helper_functions.sh

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
    # chmod bash files
    chmod +x $HOME/dotfiles/*.sh

    echo "Creating symbolic links for custom scripts in $HOME/bin..."

    scripts=(
        "fzf-preview.sh"
        "rfz.sh"
        "copy.sh"
        "sshget"
        "show-tmux-popup.sh"
        "fzf-helix.sh"
        "torch-preview.sh"
        "npy-preview.py"
        "feather-preview.py"
        "rsync-all.sh"
        "colorize-columns.sh"
        )

    for script in "${scripts[@]}"; do
        source="$HOME/dotfiles/$script"
        target="$HOME/bin/${script%.*}"
        ln -sf "$source" "$target"
        echo "Linked $(basename "$source") to $target"
        chmod +x "$source"
    done

    # symlink dots
    # this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
    files=(.aliases-and-envs.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env.zsh .gitconfig .p10k.zsh .profile .pylintrc .sourcery.yaml .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc .curlrc)
    for file in "${files[@]}"; do
        echo "Linking $file from dotfiles to home directory."
        ln -sf "$HOME"/dotfiles/"$file" "$HOME"/"$file"
    done


}



install_zsh() {
    read -p "zsh is not installed. Do you want to install zsh, build-essential, and vim? (y/n) " choice
    case "$choice" in
        y|Y )
            if [ "$(id -u)" -eq 0 ]; then
                apt update && apt upgrade -y
                apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                chsh -s $(which zsh)
            else
                sudo apt update && sudo apt upgrade -y
                sudo apt install -y zsh build-essential vim libjpeg-dev zlib1g-dev
                sudo chsh -s $(which zsh) $USER
            fi
            echo "Installation complete. Please restart your shell to use zsh."
            ;;
        * )
            echo "Skipping installation."
            return 1
            ;;
    esac
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

install_ml3_env() {
    conda env create -f ~/dotfiles/ml3_env.yml
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

install_ml3_env() {
    mamba create -n ml3 python=3.10 -y
    mamba activate ml3
    mamba install numpy pandas matplotlib scikit-learn scipy seaborn joblib polars -y
}

install_mamba() {
    conda install -n base -c conda-forge mamba -y
}

install_npm() {
    bash install_npm.sh
}

install_go() {
    add-apt-repository ppa:longsleep/golang-backports
    apt update
    install golang-go
}

install_fzf() {
    git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf"
    "$HOME/.fzf/install" --all --no-update-rc
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
    python -m pip install --user pipx
    export PATH="$HOME/.local/bin:$PATH"
    python -m pipx ensurepath
}

install_nbpreview() {
    export PATH="$HOME/.local/bin:$PATH"
    pipx install nbpreview
}

install_terminaltexteffects() {
    export PATH="$HOME/.local/bin:$PATH"
    pipx install terminaltexteffects
}

install_tmux() {
    wget -O "$HOME/bin/tmux" "n0p.me/bin/tmux" && chmod +x "$HOME/bin/tmux"
    echo "tmux installed successfully."
}

install_rg() {
    wget -O "$HOME/bin/rg" "n0p.me/bin/rg" && chmod +x "$HOME/bin/rg"
    echo "rg installed successfully."
}

install_fd() {
    wget -O "$HOME/bin/fd" "n0p.me/bin/fd" && chmod +x "$HOME/bin/fd"
    echo "fd installed successfully."
}

install_jq() {
    wget -O "$HOME/bin/jq" "n0p.me/bin/jq" && chmod +x "$HOME/bin/jq"
    echo "jq installed successfully."
}

install_pq() {
    wget -O "$HOME/bin/pq" "https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq" && chmod +x "$HOME/bin/pq"
    echo "pq installed successfully."
}

install_bat() {
    bash install_tar.sh "https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
    echo "bat installed successfully."
}

install_eza() {
    bash install_tar.sh "https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"
    echo "eza installed successfully."
}

install_parquet_tools() {
    wget https://github.com/hangxie/parquet-tools/releases/download/v1.25.1/parquet-tools_1.25.1_amd64.deb
    sudo dpkg -i parquet-tools_1.25.1_amd64.deb
    rm parquet-tools_1.25.1_amd64.deb
    echo "parquet-tools installed successfully."
}

install_fzf_tab_completion() {
    git clone https://github.com/lincheney/fzf-tab-completion "$HOME/.zprezto/contrib/fzf-tab-completion"
    echo "fzf-tab-completion installed successfully."
}

install_ml_helpers() {
    git clone https://github.com/vmasrani/machine_learning_helpers.git "$HOME/.python"
    echo "machine_learning_helpers installed successfully."
}

install_hypers() {
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
    cp ~/dotfiles/find_files.sh "$(find ~/.cursor-server/extensions -type d -name 'tomrijndorp*')"
    echo "find_files.sh copied to cursor extension directory successfully."
}

install_zprezto() {
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
    echo "zprezto installed successfully."
}
