# miniconda
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

# cargo
if ! command -v cargo &> /dev/null
then
    echo "Cargo is not installed. Installing Cargo..."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
    echo "Cargo installed successfully."
else
    echo "Cargo is already installed."
fi


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
    "$HOME/.fzf/install" --all
    echo "fzf installed successfully."
else
    echo "fzf is already installed."
fi

declare -A commands

commands["bat"]="https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
commands["rg"]="https://github.com/BurntSushi/ripgrep/releases/download/13.0.0/ripgrep-13.0.0-x86_64-unknown-linux-musl.tar.gz"
commands["fd"]="https://github.com/sharkdp/fd/releases/download/v9.0.0/fd-v9.0.0-x86_64-unknown-linux-musl.tar.gz"
commands["eza"]="https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"

for command in "${!commands[@]}"; do
    if ! command -v $command &> /dev/null; then
        echo "$command is not installed. Installing $command..."
        bash install_tar.sh ${commands[$command]}
        echo "$command installed successfully."
    else
        echo "$command is already installed."
    fi
done

# # symlink dots
# # this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
# ln -sf $HOME/dotfiles/.aliases.zsh $HOME/.aliases.zsh
# ln -sf $HOME/dotfiles/.bash_logout $HOME/.bash_logout
# ln -sf $HOME/dotfiles/.bash_profile $HOME/.bash_profile
# ln -sf $HOME/dotfiles/.bashrc $HOME/.bashrc
# ln -sf $HOME/dotfiles/.fzf-config.zsh $HOME/.fzf-config.zsh
# ln -sf $HOME/dotfiles/.fzf.bash $HOME/.fzf.bash
# ln -sf $HOME/dotfiles/.fzf.zsh $HOME/.fzf.zsh
# ln -sf $HOME/dotfiles/.gitconfig $HOME/.gitconfig
# ln -sf $HOME/dotfiles/.p10k.zsh $HOME/.p10k.zsh
# ln -sf $HOME/dotfiles/.pdbhistory $HOME/.pdbhistory
# ln -sf $HOME/dotfiles/.profile $HOME/.profile
# ln -sf $HOME/dotfiles/.pylintrc $HOME/.pylintrc
# ln -sf $HOME/dotfiles/.tmux.conf $HOME/.tmux.conf
# ln -sf $HOME/dotfiles/.vimrc $HOME/.vimrc
# ln -sf $HOME/dotfiles/.zlogin $HOME/.zlogin
# ln -sf $HOME/dotfiles/.zlogout $HOME/.zlogout
# ln -sf $HOME/dotfiles/.zpreztorc $HOME/.zpreztorc
# ln -sf $HOME/dotfiles/.zprofile $HOME/.zprofile
# ln -sf $HOME/dotfiles/.zshenv $HOME/.zshenv
# ln -sf $HOME/dotfiles/.zshrc $HOME/.zshrc


git clone ssh://git@rnd-gitlab-ca-g.huawei.com:2222/EI/roma-scripts.git ~/.roma-scripts
git clone https://github.com/lincheney/fzf-tab-completion $ZPREZTODIR/contrib/fzf-tab-completion
git clone https://github.com/vmasrani/machine_learning_helpers.git ~/.python
git clone https://github.com/vmasrani/hypers.git ~/hypers


mkdir $HOME/bin
chmod -x $HOME/bin/bat_exa_preview.sh
chmod -x $HOME/bin/rfz.sh
ln -sf $HOME/dotfiles/bat_exa_preview.sh $HOME/bin/bat_exa_preview
ln -sf $HOME/dotfiles/rfz.sh $HOME/bin/rfz




