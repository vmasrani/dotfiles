#!/bin/bash
NODE_DIR="$HOME/.local/lib/nodejs"

VERSION=$(curl -s https://nodejs.org/dist/latest/ | grep -o 'v[0-9]*\.[0-9]*\.[0-9]*' | head -n 1)


# Automatically determine the distribution
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) DISTRO=linux-x64 ;;
    aarch64) DISTRO=linux-arm64 ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$NODE_DIR"
tar -xJvf "node-$VERSION-$DISTRO.tar.xz" -C "$NODE_DIR"

ln -sf /usr/local/lib/nodejs/node-$VERSION-$DISTRO/bin/node $HOME/bin/node
ln -sf /usr/local/lib/nodejs/node-$VERSION-$DISTRO/bin/npm $HOME/bin/npm
ln -sf /usr/local/lib/nodejs/node-$VERSION-$DISTRO/bin/npx $HOME/bin/npx
