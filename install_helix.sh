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

bash install_helix_language_servers.sh
