#!/bin/bash

set -e

# sudo chsh -s $(which zsh) $USER

mkdir -p "$HOME"/bin
mkdir -p "$HOME/dev/projects"

# chmod bash files
chmod +x $HOME/dotfiles/*.sh

# update submodules
git submodule update --init --recursive

# remember my login for 1 yr
git config --global credential.helper 'cache --timeout=31536000'


echo "Creating symbolic links for custom scripts in $HOME/bin..."

scripts=("fzf_preview.sh" "rfz.sh" "copy.sh" "sshget" "show-tmux-popup.sh" "fzf-helix.sh" "torch-preview.sh" "npy-preview.py" "rsync-all.sh")

for script in "${scripts[@]}"; do
	source="$HOME/dotfiles/$script"
	target="$HOME/bin/${script%.*}"
	ln -sf "$source" "$target"
	echo "Linked $(basename "$source") to $target"
	chmod +x "$source"
done

# symlink dots
# this is dangerous!! broken dotfiles can lead to not being able to regain SSH access, make sure to test before exiting
files=(.aliases-and-envs.zsh .bash_logout .bash_profile .bashrc .fzf-config.zsh .fzf.bash .fzf.zsh .fzf-env.zsh .gitconfig .p10k.zsh .profile .pylintrc .tmux.conf .vimrc .zlogin .zlogout .zpreztorc .zprofile .zshenv .zshrc .curlrc)
for file in "${files[@]}"; do
	echo "Linking $file from dotfiles to home directory."
	ln -sf "$HOME"/dotfiles/"$file" "$HOME"/"$file"
done


echo "Linking helix from dotfile to ~/.config/helix"
mkdir -p ~/.config/helix/
ln -sf ~/dotfiles/hx_config.toml ~/.config/helix/config.toml
ln -sf ~/dotfiles/hx_languages.toml  ~/.config/helix/languages.toml

# zprezto
if [ ! -d "$HOME/.zprezto" ]; then
	echo "zprezto is not installed. Installing zprezto..."
	git clone --recursive https://github.com/sorin-ionescu/prezto.git "$HOME/.zprezto"
	echo "zprezto installed successfully."
else
	echo "zprezto is already installed."
fi

# Source the installation functions
source "$(dirname "$0")/install_functions.sh"
install_if_missing fzf install_fzf
install_if_missing conda install_miniconda
install_if_missing cargo install_cargo
install_if_missing tldr install_tealdeer
install_if_missing npm install_npm
install_if_missing go install_go
install_if_missing hx install_helix
install_if_missing glow install_glow
install_if_missing lazygit install_lazygit
install_if_missing pipx install_pipx
install_if_missing nbpreview install_nbpreview
install_if_missing tte install_terminaltexteffects

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
	if ! command -v "$command" &>/dev/null; then
		echo "$command is not installed. Installing $command..."
		bash install_tar.sh "${executables[$command]}"
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
	if [ ! -d ~/"$repo" ]; then
		if ! git clone "${git_repos[$repo]}" ~/"$repo"; then
			echo "Error: Could not clone the repository ${git_repos[$repo]}."
			continue
		fi
	else
		echo "$HOME/$repo is already installed."
	fi
done


# other
# git fuzzy
if [ ! -d "$HOME/bin/_git-fuzzy" ]; then
    echo "Cloning git-fuzzy..."
    git clone https://github.com/bigH/git-fuzzy.git ~/bin/_git-fuzzy
    echo "Creating symbolic link for git-fuzzy..."
    ln -s ~/bin/_git-fuzzy/bin/git-fuzzy ~/bin/git-fuzzy
    echo "git-fuzzy setup completed."
else
    echo "git-fuzzy is already installed."
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



if [ -d "$HOME/.cursor-server/extensions/*tomrijndorp*" ]; then
		echo "Copying find_files.sh to .cursor-server extensions..."
		cp ~/dotfiles/find_files.sh "$(find ~/.cursor-server/extensions  -type d -name 'tomrijndorp*')"
fi

echo "Setup completed successfully. All necessary tools and configurations have been installed and set up."



