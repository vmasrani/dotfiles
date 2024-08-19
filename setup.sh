#!/usr/local/bin/bash

set -e

# sudo chsh -s $(which zsh) $USER

mkdir -p $HOME/bin
mkdir -p dev/projects

# chmod bash files
chmod +x *.sh

# update submodules
git submodule update --init --recursive

# remember my login for 1 yr
git config --global credential.helper 'cache --timeout=31536000'

echo "Creating symbolic links for custom scripts and zsh in $HOME/bin..."
declare -A links=(
	["$HOME/dotfiles/fzf-preview.sh"]="$HOME/bin/fzf-preview"
	["$HOME/dotfiles/rfz.sh"]="$HOME/bin/rfz"
	["$HOME/dotfiles/copy.sh"]="$HOME/bin/copy"
	["$HOME/dotfiles/sshget"]="$HOME/bin/sshget"
	["$HOME/dotfiles/show-tmux-popup.sh"]="$HOME/bin/show-tmux-popup.sh"
	["$HOME/dotfiles/fzf-helix.sh"]="$HOME/bin/fzf-helix"
	["$HOME/dotfiles/colorize-columns.sh"]="$HOME/bin/colorize-columns"
)

for source in "${!links[@]}"; do
	target=${links[$source]}
	ln -sf "$source" "$target"
	echo "Linked $(basename "$source") to $target"
	chmod +x "$source"
done

# symlink dots
# this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
files=(.aliases-and-envs.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env.zsh .gitconfig .p10k.zsh .profile .pylintrc .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc)
for file in "${files[@]}"; do
	echo "Linking $file from dotfiles to home directory."
	ln -sf $HOME/dotfiles/$file $HOME/$file
done


echo "Linking helix from dotfile to ~/.config/helix"
mkdir -p ~/.config/helix/
ln -sf ~/dotfiles/hx_config.toml ~/.config/helix/config.toml
ln -sf ~/dotfiles/hx_languages.toml  ~/.config/helix/languages.toml

if ! command -v conda &>/dev/null; then
	if [[ "$OSTYPE" == "linux-gnu"* ]]; then
		mkdir -p ~/miniconda
		wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda/miniconda.sh
		bash ~/miniconda/miniconda.sh -b -u -p ~/miniconda
		rm -rf ~/miniconda/miniconda.sh
	elif [[ "$OSTYPE" == "darwin"* ]]; then
		mkdir -p ~/miniconda
		curl https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-arm64.sh -o ~/miniconda/miniconda.sh
		bash ~/miniconda/miniconda.sh -b -u -p ~/miniconda
		rm -rf ~/miniconda/miniconda.sh
	else
		echo "Unsupported OS. Please install Miniconda manually."
		exit 1
	fi
	export PATH="$HOME/miniconda/bin:$PATH"
	echo 'export PATH="$HOME/miniconda/bin:$PATH"' >>~/.zshrc
	conda init zsh
	echo "Miniconda installed successfully."
else
	echo "Miniconda is already installed."
fi

# cargo
if ! command -v cargo &> /dev/null
then
    echo "Cargo is not installed. Installing Cargo..."
    brew install cargo
    echo "Cargo installed successfully."
else
    echo "Cargo is already installed."
fi

# tealdear
if ! command -v tldr &> /dev/null
then
    cargo install tealdeer
    tldr --update
else
    echo "tldr is already installed."
fi

# zprezto
if [ ! -d "$HOME/.zprezto" ]; then
	echo "zprezto is not installed. Installing zprezto..."
	git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
	echo "zprezto installed successfully."
else
	echo "zprezto is already installed."
fi

# node
if ! command -v npm &>/dev/null; then
    echo "npm is not installed. Installing npm..."
    brew install npm
    echo "npm installed successfully."
else
    echo "npm is already installed."
fi


# go
if ! command -v go &>/dev/null; then
    echo "go is not installed. Installing go..."
    brew install go
    echo "go installed successfully."
else
    echo "go is already installed."
fi

# pipx
if ! command -v pipx &>/dev/null; then
	echo "pipx is not installed. Installing pipx..."
	python3 -m pip install --user pipx
	python3 -m pipx ensurepath
	echo "pipx installed successfully."
else
	echo "pipx is already installed."
fi

if ! command -v nbpreview &>/dev/null; then
	echo "nbpreview is not installed. Installing nbpreview..."
	pipx install nbpreview
	echo "nbpreview installed successfully."
else
	echo "nbpreview is already installed."
fi

if ! command -v tte &>/dev/null; then
	echo "terminaltexteffects is not installed. Installing terminaltexteffects..."
	pipx install terminaltexteffects
	echo "terminaltexteffects installed successfully."
else
	echo "terminaltexteffects is already installed."
fi

# fzf
if ! command -v fzf &>/dev/null; then
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
	[pq]="https://raw.githubusercontent.com/kouta-kun/pq/main/bin/pq"
)

for bin in "${!binaries[@]}"; do
	if [ ! -f "$HOME/bin/$bin" ]; then
		wget -O "$HOME/bin/$bin" "${binaries[$bin]}" && chmod +x "$HOME/bin/$bin"
		echo "$bin installed successfully."
	else
		echo "$bin is already installed."
	fi
done

declare -A executables

executables["bat"]="https://github.com/sharkdp/bat/releases/download/v0.18.3/bat-v0.18.3-x86_64-unknown-linux-musl.tar.gz"
executables["eza"]="https://github.com/eza-community/eza/releases/download/v0.18.2/eza_x86_64-unknown-linux-musl.tar.gz"

for command in "${!executables[@]}"; do
	if ! command -v $command &>/dev/null; then
		echo "$command is not installed. Installing $command..."
		bash install_tar.sh ${executables[$command]}
		echo "$command installed successfully."
	else
		echo "$command is already installed."
	fi
done

if [ -f "$HOME/bin/parquet-tools" ]; then
	echo "parquet-tools is already installed."
else
	bash install-parquet-tools.sh
fi

declare -A git_repos

git_repos[".zprezto/contrib/fzf-tab-completion"]="https://github.com/lincheney/fzf-tab-completion"
git_repos[".python"]="https://github.com/vmasrani/machine_learning_helpers.git"
git_repos["hypers"]="https://github.com/vmasrani/hypers.git"
git_repos[".tmux/plugins/tpm"]="https://github.com/tmux-plugins/tpm"
# git_repos[".roma-scripts"]="https://rnd-gitlab-ca-g.huawei.com/EI/roma-scripts.git"

for repo in "${!git_repos[@]}"; do
	if [ ! -d ~/$repo ]; then
		if ! git clone ${git_repos[$repo]} ~/$repo; then
			echo "Error: Could not clone the repository ${git_repos[$repo]}."
			continue
		fi
	else
		echo "~/$repo is already installed."
	fi
done

# helix
if [ ! -f "$HOME/bin/hx" ]; then
    brew install helix
else
    echo "helix is already installed."
fi

# glow

if ! command -v glow &>/dev/null; then
	echo "glow is not installed. Installing glow..."
	brew install glow
	echo "glow installed successfully."
else
	echo "glow is already installed."
fi


if ! command -v lazygit &>/dev/null; then
	echo "lazygit is not installed. Installing lazygit..."
	brew install lazygit
	echo "lazygit installed successfully."
else
	echo "lazygit is already installed."
fi

if [ ! -d "$HOME/bin/_diff-so-fancy" ]; then
    echo "Cloning diff-so-fancy..."
    git clone https://github.com/so-fancy/diff-so-fancy.git ~/bin/_diff-so-fancy
    echo "Creating symbolic link for diff-so-fancy..."
    ln -s ~/bin/_diff-so-fancy/diff-so-fancy ~/bin/diff-so-fancy
    echo "Configuring diff-so-fancy..."
    git config --global core.pager "diff-so-fancy | less --tabs=4 -RF"
    git config --global interactive.diffFilter "diff-so-fancy --patch"
    echo "diff-so-fancy setup completed."
else
    echo "diff-so-fancy is already installed."
fi


echo "Copying find_files.sh to .cursor extensions..."
cp ~/dotfiles/find_files.sh $(find ~/.cursor/extensions  -type d -name 'tomrijndorp*')
echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."



