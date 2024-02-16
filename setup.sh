#!/bin/bash

set -e


mkdir -p $HOME/bin
chmod +x $HOME/dotfiles/fzf_preview.sh
chmod +x $HOME/dotfiles/rfz.sh

# remember my login for 1 yr
git config --global credential.helper 'cache --timeout=31536000'


echo "Creating symbolic links for custom scripts and zsh in $HOME/bin..."
declare -A links=(
    ["$HOME/dotfiles/fzf_preview.sh"]="$HOME/bin/fzf_preview"
    ["$HOME/dotfiles/rfz.sh"]="$HOME/bin/rfz"
    ["/usr/bin/zsh"]="$HOME/bin/zsh"
)

for source in "${!links[@]}"; do
    target=${links[$source]}
    ln -sf "$source" "$target"
    echo "Linked $(basename "$source") to $target"
done
# symlink dots
# this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
files=(.aliases.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env .gitconfig .p10k.zsh .pdbhistory .profile .pylintrc .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc)
for file in "${files[@]}"
do
    echo "Linking $file from dotfiles to home directory."
    ln -sf $HOME/dotfiles/$file $HOME/$file
done


if ! command -v conda &> /dev/null
then
    echo "Miniconda is not installed. Installing Miniconda..."
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda.sh
    bash ~/miniconda.sh -b -p $HOME/miniconda
    rm ~/miniconda.sh
    export PATH="$HOME/miniconda/bin:$PATH"
    echo 'export PATH="$HOME/miniconda/bin:$PATH"' >> ~/.zshrc
    conda init zsh
    echo "Miniconda installed successfully."
else
    echo "Miniconda is already installed."
fi

# # cargo
# if ! command -v cargo &> /dev/null
# then
#     echo "Cargo is not installed. Installing Cargo..."
#     curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
#     echo "Cargo installed successfully."
# else
#     echo "Cargo is already installed."
# fi


# zprezto
if [ ! -d "$HOME/.zprezto" ]; then
    echo "zprezto is not installed. Installing zprezto..."
    git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
    echo "zprezto installed successfully."
else
    echo "zprezto is already installed."
fi

# fzf
if ! command -v fzf &> /dev/null; then
    echo "fzf is not installed. Installing fzf..."
    git clone --depth 1 https://github.com/junegunn/fzf.git "$HOME/.fzf"
    "$HOME/.fzf/install"
    echo "fzf installed successfully."
else
    echo "fzf is already installed."
fi


# statically linked binaries from
# https://github.com/mosajjal/binary-tools
declare -A binaries=(
    [tmux]="n0p.me/bin/tmux"
    [rg]="n0p.me/bin/rg"
    [fd]="n0p.me/bin/fd"
    [jq]="n0p.me/bin/jq"
)

for bin in "${!binaries[@]}"; do
    if [ ! -f "$HOME/bin/$bin" ]; then
        wget -O "$HOME/bin/$bin" "${binaries[$bin]}" && chmod +x "$HOME/bin/$bin"
    else
        echo "$bin is already installed."
    fi
done

declare -A executables

executables["bat"]="https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
executables["eza"]="https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"
executables["parquet-tools"]="https://github.com/hangxie/parquet-tools/releases/download/v1.20.4/parquet-tools-1.20.4-1.x86_64.rpm"

for command in "${!executables[@]}"; do
    if ! command -v $command &> /dev/null; then
        echo "$command is not installed. Installing $command..."
        bash install_tar.sh ${executables[$command]}
        echo "$command installed successfully."
    else
        echo "$command is already installed."
    fi
done


declare -A git_repos

git_repos[".roma-scripts"]="https://rnd-gitlab-ca-g.huawei.com/EI/roma-scripts.git"
git_repos[".zprezto/contrib/fzf-tab-completion"]="https://github.com/lincheney/fzf-tab-completion"
git_repos[".python"]="https://github.com/vmasrani/machine_learning_helpers.git"
git_repos["hypers"]="https://github.com/vmasrani/hypers.git"
git_repos[".tmux/plugins/tpm"]="https://github.com/tmux-plugins/tpm"


for repo in "${!git_repos[@]}"; do
    if [ ! -d ~/$repo ]; then
        git clone ${git_repos[$repo]} ~/$repo
    else
        echo "~/$repo is already installed."
    fi
done

echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."



