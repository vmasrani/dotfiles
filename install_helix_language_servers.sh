#!/bin/bash



check_and_install_packages() {
    if ! command -v $1 &> /dev/null
    then
        echo "$1 is not installed"
        pip install $2
    fi
}


# Function to install packages in a given environment
install_packages() {
    # Activate the environment
    conda init
    if [ "$1" = "default_python_env" ]; then
        conda deactivate
    else
        conda activate $1
    fi

    # Install packages

    check_and_install_packages "ruff-lsp" "ruff-lsp"
    check_and_install_packages "pylsp" "pylsp-mypy"
    check_and_install_packages "pylsp" "-U python-lsp-server[all]"
    check_and_install_packages "shellcheck" "shellcheck"
    
    
    # Deactivate the environment
    conda deactivate
}

# Install packages in the default Python environment
install_packages default_python_env

# Install packages in the ml3 environment
install_packages ml3_env


npm list -g yaml-language-server@next || npm i -g yaml-language-server@next
npm list -g vscode-langservers-extracted || npm i -g vscode-langservers-extracted
npm list -g bash-language-server || npm i -g bash-language-server
npm list -g pyright || npm i -g pyright

cargo install --locked --git https://github.com/Feel-ix-343/markdown-oxide.git markdown-oxide
cargo install --git https://github.com/estin/simple-completion-language-server.git
cargo install taplo-cli --locked --features lsp
hx --grammar build
hx --grammar fetch
