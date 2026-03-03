#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: $0 <url>"
    exit 1
fi

url="$1"

# Determine the file name from the URL
file_name=$(basename "$url")
if [[ $file_name == *".tar.gz" ]]; then
    dir_name=$(basename -s .tar.gz "$file_name")
elif [[ $file_name == *".tar.xz" ]]; then
    dir_name=$(basename -s .tar.xz "$file_name")
else
    echo "Unsupported file extension" >&2
    exit 1
fi

# Download the tar file
curl -fSL -o "$HOME/$file_name" "$url"

mkdir -p "$HOME/bin/$dir_name"
# Extract the tar file
tar -xvf "$HOME/$file_name" -C "$HOME/bin/$dir_name"

# Symlink the executables
find "$HOME/bin/$dir_name" -maxdepth 2 -type f -executable -exec ln -sf {} "$HOME/bin" \;

# Remove the downloaded file
rm "$HOME/$file_name"

echo "The tar file from $url has been successfully installed to ~/bin"
