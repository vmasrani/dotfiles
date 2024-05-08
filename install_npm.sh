#!/bin/bash

sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.1/install.sh | bash

sudo apt-get update
sudo apt-get install nodejs -y
sudo apt-get install npm -y
npm config set prefix '~/.npm-global'


# npm config set registry http://registry.npmjs.org/


# npm set strict-ssl false
# sudo npm cache clean -f
# sudo npm install -g n
# sudo n stable


# NODE_DIR="$HOME/.local/lib/nodejs"

# VERSION=v16.0.0


# # Automatically determine the distribution
# ARCH=$(uname -m)
# case "$ARCH" in
#     x86_64) DISTRO=linux-x64 ;;
#     aarch64) DISTRO=linux-arm64 ;;
#     *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
# esac

# mkdir -p "$NODE_DIR"

# wget "https://nodejs.org/dist/$VERSION/node-$VERSION-$DISTRO.tar.xz" -O "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz"

# tar -xJf "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz" -C "$NODE_DIR"
# rm "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz"

# ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/node" "$HOME/bin/node"
# ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/npm" "$HOME/bin/npm"
# ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/npx" "$HOME/bin/npx"




