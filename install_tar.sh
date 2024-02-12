#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <url>"
    exit 1
fi

url="$1"

# Determine the file name from the URL
file_name=$(basename "$url")

# Download the tar file
wget "$url" -O ~/$file_name

# Extract the tar file
tar -xvf ~/$file_name -C ~/bin

# Remove the downloaded file
rm ~/$file_name

echo "The tar file from $url has been installed successfully. You may need to restart your shell for the changes to take effect."
