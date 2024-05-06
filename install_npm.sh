#!/bin/bash
NODE_DIR="$HOME/.local/lib/nodejs"

VERSION=v16.0.0

# Automatically determine the distribution
ARCH=$(uname -m)
case "$ARCH" in
    x86_64) DISTRO=linux-x64 ;;
    aarch64) DISTRO=linux-arm64 ;;
    *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;;
esac

mkdir -p "$NODE_DIR"

wget "https://nodejs.org/dist/$VERSION/node-$VERSION-$DISTRO.tar.xz" -O "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz"

tar -xJf "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz" -C "$NODE_DIR"
rm "$NODE_DIR/node-$VERSION-$DISTRO.tar.xz"

ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/node" "$HOME/bin/node"
ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/npm" "$HOME/bin/npm"
ln -sf "$NODE_DIR/node-$VERSION-$DISTRO/bin/npx" "$HOME/bin/npx"

npm config set registry http://registry.npmjs.org/
npm set strict-ssl false


