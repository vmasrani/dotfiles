#!/bin/zsh
# rename_file.sh - Rename a single file using Claude AI
# Usage: ./rename_file.sh filename.pdf

file="$1"

# Check if file argument provided
if [[ -z "$file" ]]; then
    echo -e "\033[31mUsage: $0 filename\033[0m"
    exit 1
fi

# Check if file exists
if [[ ! -f "$file" ]]; then
    echo -e "\033[31mError: File '$file' not found\033[0m"
    exit 1
fi

# Get file extension
extension="${file##*.}"

# Create prompt for Claude
prompt="$(cat $HOME/.claude/commands/file-renamer.md)
The original filename is: $file."

new_name=$(cat "$file" | pdf_extract_pages | markitdown | claude -p "$prompt" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

# Show truncated name for display
truncated_name=$(echo "$new_name" | awk '{ if (length($0) > 50) print substr($0, 1, 47) "..."; else print $0 }')

echo -e "\033[32mClaude: $file -> $truncated_name\033[0m"

# Check if we got a valid response
if [[ -z "$new_name" ]]; then
    echo -e "\033[31mError: Could not generate new filename for $file\033[0m"
    exit 1
fi

if [[ ${#new_name} -gt 100 ]]; then
    echo -e "\033[31mError: Generated filename is longer than 100 characters\033[0m"
    exit 1
fi

# Rename the file
new_filename="${new_name}.${extension}"
mv -if "$file" "$new_filename"
