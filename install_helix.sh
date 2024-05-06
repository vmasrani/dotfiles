#!/bin/bash

set -e

if ! command -v hx &> /dev/null; then
    if [[ $(lsb_release -rs) == "16.04" ]]; then
        echo "Detected Ubuntu 16.04, downloading specific Helix version..."
        tar_path="https://github.com/zydou/helix/releases/download/v24.03/helix-v24.03-x86_64-unknown-linux-gnu.tar.xz"
        bash install_tar.sh $tar_path
    else
        wget https://github.com/helix-editor/helix/releases/download/24.03/helix-24.03-x86_64.AppImage -O ~/bin/hx
        chmod +x ~/bin/hx
    fi
fi

ln -sf ~/dotfiles/hx_config.toml ~/.config/helix/config.toml

if ! command -v ruff-lsp &> /dev/null; then
    pip install ruff-lsp
fi

if ! command -v pylsp-mypy &> /dev/null; then
    pip install pylsp-mypy
fi

if ! command -v python-lsp-server &> /dev/null; then
    pip install -U 'python-lsp-server[all]'
fi

if ! command -v pyright &> /dev/null; then
    npm install --location=global pyright --prefix ~/.npm-global
fi

if ! command -v yaml-language-server &> /dev/null; then
    npm i -g yaml-language-server@next --prefix ~/.npm-global
fi

if ! command -v vscode-langservers-extracted &> /dev/null; then
    npm i -g vscode-langservers-extracted --prefix ~/.npm-global
fi

if ! command -v bash-language-server &> /dev/null; then
    npm i -g bash-language-server --prefix ~/.npm-global
fi
