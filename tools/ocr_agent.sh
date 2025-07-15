#!/bin/zsh
# ocr_file.sh - OCR a PNG file using Claude AI
# Usage: ./ocr_file.sh filename.png

dir_path="$1"

[[ -z "$dir_path" ]] && { gum style --foreground 1 "Usage: $0 directory_path"; exit 1; }
[[ ! -d "$dir_path" ]] && { gum style --foreground 1 "Error: Directory '$dir_path' not found"; exit 1; }

img_file="$dir_path/img.png"
ocr_file="$dir_path/ocr.txt"

[[ ! -f "$img_file" ]] && { gum style --foreground 1 "Error: Image file 'img.png' not found in directory '$dir_path'"; exit 1; }
[[ ! -f "$ocr_file" ]] && { gum style --foreground 1 "Error: OCR text file 'ocr.txt' not found in directory '$dir_path'"; exit 1; }

prompt="$(cat $HOME/.claude/commands/ocr.md) ---
The file to OCR is: $img_file
A preliminary OCR text file is available at: $ocr_file
"

gum style --foreground 2 "Running OCR on $dir_path..."
claude -p "$prompt" >| "$dir_path/ocr_output.md"

gum style --foreground 2 "OCR completed: $img_file -> $dir_path/ocr_output.md"
