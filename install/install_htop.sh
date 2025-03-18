#!/bin/bash

# Define installation paths
HTOP_DIR="$HOME/bin/htop_src"
BIN_DIR="$HOME"

# Create the directories if they don't exist
mkdir -p "$HTOP_DIR" "$BIN_DIR"

# Update package list and install necessary build tools and dependencies
sudo apt update
sudo apt install -y build-essential autotools-dev autoconf libncursesw5-dev git

# Clone or update the htop repository
if [ -d "$HTOP_DIR/.git" ]; then
  echo "Updating existing htop repository..."
  cd "$HTOP_DIR"
  git pull
else
  echo "Cloning htop repository..."
  git clone https://github.com/htop-dev/htop.git "$HTOP_DIR"
  cd "$HTOP_DIR"
fi

# Clean previous builds
make clean || true

# Generate the configuration script
./autogen.sh

# Configure the build environment
./configure --prefix="$BIN_DIR"

# Compile the source code
make

# Install the compiled program into the specified bin directory
make install prefix="$BIN_DIR"

# Add $HOME/bin to PATH if not already included
if [[ ":$PATH:" != *":$HOME/bin:"* ]]; then
  echo 'export PATH="$HOME/bin:$PATH"' >> "$HOME/.bashrc"
  export PATH="$HOME/bin:$PATH"
fi


# Verify the installation
htop --version 
