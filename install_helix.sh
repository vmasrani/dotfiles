#!/bin/bash

set -e

if ! command -v hx &> /dev/null; then
    case $(lsb_release -rs) in
        "16.04")
            echo "Detected Ubuntu 16.04, downloading specific Helix version..."
            tar_path="https://github.com/zydou/helix/releases/download/v24.03/helix-v24.03-x86_64-unknown-linux-gnu.tar.xz"
            bash install_tar.sh $tar_path
            ;;
        "22.04")
            echo "Detected Ubuntu 22.04, installing Helix using package manager..."
            if [ "$(id -u)" -eq 0 ]; then
                add-apt-repository ppa:maveonair/helix-editor
                apt update
                apt install helix
            else
                sudo add-apt-repository ppa:maveonair/helix-editor
                sudo apt update
                sudo apt install helix
            fi
            ;;
        "24.10")
            echo "Detected Ubuntu 24.10, installing Helix via snap..."
            sudo snap install helix --classic
            ;;
        *)
            wget https://github.com/helix-editor/helix/releases/download/24.03/helix-24.03-x86_64.AppImage -O ~/bin/hx
            chmod +x ~/bin/hx
            ;;
    esac
fi
