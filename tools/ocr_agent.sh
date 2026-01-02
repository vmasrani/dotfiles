#!/bin/zsh
# ocr_file.sh - OCR a PNG file using Claude AI
# Usage: ./ocr_file.sh filename.png

# Source gum utilities
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
source "$SCRIPT_DIR/../shell/gum_utils.sh"

dir_path="$1"

[[ -z "$dir_path" ]] && { gum_error "Usage: $0 directory_path"; exit 1; }
[[ ! -d "$dir_path" ]] && { gum_error "Error: Directory '$dir_path' not found"; exit 1; }

img_file="$dir_path/img.png"
ocr_file="$dir_path/ocr.txt"

[[ ! -f "$img_file" ]] && { gum_error "Error: Image file 'img.png' not found in directory '$dir_path'"; exit 1; }
[[ ! -f "$ocr_file" ]] && { gum_error "Error: OCR text file 'ocr.txt' not found in directory '$dir_path'"; exit 1; }

prompt="$(cat $HOME/.claude/commands/ocr.md) ---
The file to OCR is: $img_file
A preliminary OCR text file is available at: $ocr_file
"

gum_success "Running OCR on $dir_path..."
claude -p "$prompt" >| "$dir_path/ocr_output.md"

gum_success "OCR completed: $img_file -> $dir_path/ocr_output.md"
