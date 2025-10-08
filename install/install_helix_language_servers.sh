#!/bin/bash

source ~/dotfiles/shell/helper_functions.sh


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
