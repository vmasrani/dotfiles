#!/bin/bash

API_KEY="bdd65b74d62f60d28e715b471cadcf6a"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check and install Homebrew if not present
if ! command_exists brew; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
else
    echo "Homebrew is already installed."
fi

# Install curl if not present
if ! command_exists curl; then
    echo "Installing curl..."
    brew install curl
else
    echo "curl is already installed."
fi

# Create a directory for Convertio CLI
mkdir -p ~/convertio-cli
cd ~/convertio-cli

# Download Convertio CLI
echo "Downloading Convertio CLI..."
curl -O https://api.convertio.co/convertio
chmod +x convertio

# Add Convertio CLI to PATH
echo 'export PATH=$PATH:~/convertio-cli' >> ~/.zshrc
source ~/.zshrc

# Create a configuration file with the API key
echo "$API_KEY" > ~/.convertio_api_key

echo "Convertio CLI setup complete!"
echo "Your API key has been saved to ~/.convertio_api_key"
echo "You can now use Convertio CLI like this:"
echo "convertio -k \$(cat ~/.convertio_api_key) input_file output_file"
