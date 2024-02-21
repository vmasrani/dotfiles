#!/bin/bash

url="https://github.com/hangxie/parquet-tools/releases/download/v1.20.4/parquet-tools-v1.20.4-darwin-amd64.gz"

# Determine the file name from the URL
file_name=$(basename "$url")

wget "$url"
# Download the tar file
gunzip "$file_name"

mv parquet-tools-v1.20.4-darwin-amd64 ~/bin/parquet-tools

chmod +x ~/bin/parquet-tools

