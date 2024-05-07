#!/bin/bash
pip install ruff-lsp
pip install pylsp-mypy
pip install -U 'python-lsp-server[all]'
npm install --location=global pyright --prefix ~/.npm-global
npm i -g yaml-language-server@next --prefix ~/.npm-global
npm i -g vscode-langservers-extracted --prefix ~/.npm-global
npm i -g bash-language-server --prefix ~/.npm-global
cargo install --locked --git https://github.com/Feel-ix-343/markdown-oxide.git markdown-oxide
