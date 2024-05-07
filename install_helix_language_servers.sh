#!/bin/bash
pip install ruff-lsp
pip install pylsp-mypy
pip install -U 'python-lsp-server[all]'
npm config set prefix '~/.npm-global'
npm install --location=global pyright 
npm i -g yaml-language-server@next 
npm i -g vscode-langservers-extracted 
npm i -g bash-language-server 
cargo install --locked --git https://github.com/Feel-ix-343/markdown-oxide.git markdown-oxide
cargo install --git https://github.com/estin/simple-completion-language-server.git
cargo install taplo-cli --locked --features lsp
