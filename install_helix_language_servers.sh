#!/bin/bash

source ~/dotfiles/helper_functions.sh

# Function to check and install packages
check_and_install_packages() {
    if ! command_exists $1; then
        echo "$1 is not installed"
        eval $2
    fi
}

 # Function to install packages in a given environment
 install_packages() {
     # Activate the environment
     conda activate $1
     # Install packages

     check_and_install_packages "ruff-lsp" "pip install ruff-lsp"
     check_and_install_packages "pylsp" "pip install pylsp-mypy"
     check_and_install_packages "pylsp" "pip install -U python-lsp-server[all]"
     check_and_install_packages "shellcheck" "conda install -c conda-forge shellcheck"

     # Deactivate the environment
     conda deactivate
 }
# Function to install packages in a given environment
install_packages() {
    echo "Installing packages in $1 environment"
    # Activate the environment
    conda activate $1
    # Install packages
    uv pip install ruff-lsp pylsp-mypy python-lsp-server[all]
    conda install -c conda-forge shellcheck -y
    # Deactivate the environment
    conda deactivate
}

# Install conda packages
# echo "Installing conda packages..."
# source ~/miniconda/etc/profile.d/conda.sh
# install_packages base
# install_packages ml3
# install_packages llava

# Install npm packages
echo "Installing npm packages..."
npm install -g yaml-language-server vscode-langservers-extracted bash-language-server pyright

# Install cargo packages
echo "Installing cargo packages..."
cargo install --locked --git https://github.com/Feel-ix-343/markdown-oxide.git markdown-oxide
cargo install --git https://github.com/estin/simple-completion-language-server.git
cargo install taplo-cli --locked --features lsp

# Helix grammar operations
echo "Performing Helix grammar operations..."
hx --grammar build
hx --grammar fetch

echo "Installation complete!"
