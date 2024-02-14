#!/bin/bash

set -e

mkdir -p $HOME/bin
chmod +x $HOME/dotfiles/bat_exa_preview.sh
chmod +x $HOME/dotfiles/rfz.sh
ln -sf $HOME/dotfiles/bat_exa_preview.sh $HOME/bin/bat_exa_preview
ln -sf $HOME/dotfiles/rfz.sh $HOME/bin/rfz

ln -sf /usr/bin/zsh $HOME/bin/zsh

# symlink dots
# this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
files=(.aliases.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .gitconfig .p10k.zsh .pdbhistory .profile .pylintrc .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc)
for file in "${files[@]}"
do
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
    echo "Creating ml3 conda env."
    conda create -n ml3 python=3.10
    conda activate ml3

    pip install ipykernel joblib seaborn pandas transformers pyarrow wandb scipy datasets scipy scikit-learn ipykernel ipython pyjanitor seaborn matplotlib typing-extensions requests ruff pylint datasets transformers spacy polars jupyter ipdb

    conda install pytorch==1.12.1 -c pytorch
    conda install cudatoolkit=10.2 -c pytorch
    conda install torchvision==0.13.1 -c pytorch
    conda install torchaudio==0.12.1 -c pytorch

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
wget -O $HOME/bin/tmux n0p.me/bin/tmux && chmod +x $HOME/bin/tmux
wget -O $HOME/bin/rg n0p.me/bin/rg && chmod +x $HOME/bin/rg
wget -O $HOME/bin/fd n0p.me/bin/fd && chmod +x $HOME/bin/fd


declare -A executables

executables["bat"]="https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
executables["eza"]="https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"

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

# remember my login for 1 yr
# testing to see if it worked
git config --global credential.helper 'cache --timeout=31536000'

for repo in "${!git_repos[@]}"; do
    if [ ! -d ~/$repo ]; then
        git clone ${git_repos[$repo]} ~/$repo
    else
        echo "~/$repo is already installed."
    fi
done

echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."



