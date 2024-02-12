#!/bin/bash

if [ -z "$1" ]; then
    echo "Usage: $0 <url>"
    exit 1
fi

url="$1"

# Determine the file name from the URL
file_name=$(basename "$url")
dir_name=$(basename -s .tar.gz "$url")

# Download the tar file
wget "$url" -O ~/$file_name

# Extract the tar file
tar -xvf ~/$file_name -C ~/bin

# Symlink the executables
find ~/bin/$dir_name -type f -executable -exec ln -s {} ~/bin \;

# Remove the downloaded file
rm ~/$file_name

echo "The tar file from $url has been successfully installed to ~/bin"
