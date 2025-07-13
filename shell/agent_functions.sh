# #!/bin/zsh
# # shellcheck shell=zsh
# # ===================================================================
# # Helper Functions for Dotfiles
# # ===================================================================

# # Helper function to check if a command exists
# command_exists() {
#     command -v "$1" > /dev/null
# }

# # Color codes
# RED="31"
# GREEN="32"
# BLUE="34"

# # Helper function to colorize text
# colorize() {
#     local color_code="$1"
#     local text="$2"
#     echo -e "\033[${color_code}m${text}\033[0m"
# }

# parallel_rename() {
#     local file="$1"
#     if [[ ! -f "$file" ]]; then
#         colorize "$RED" "Error: File '$file' not found"
#         return 1
#     fi
#     local extension="${file##*.}"
#     local prompt="rename this file into Author Name - Title:Subtitle format.
#     The original filename is: $file
#     If there's not enough information in the text, return the original filename or a cleaned-up version of it.
#     Return ONLY the new filename with no extension, no other commentary:"
#     colorize "$BLUE" "Sending $file to Claude"
#     local new_name=$(markitdown "$file" 2>/dev/null | head -n 100 | claude -p "$prompt" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
#     local truncated_name=$(echo "$new_name" | awk '{ if (length($0) > 50) print substr($0, 1, 47) "..."; else print $0 }')
#     colorize "$GREEN" "Claude: $file -> $truncated_name"
#     if [[ -z "$new_name" ]]; then
#         colorize "$RED" "Error: Could not generate new filename for $file"
#         return 1
#     fi
#     local new_filename="${new_name}.${extension}"
#     mv -iv "$file" "$new_filename"
# }

# export -f colorize
# export -f parallel_rename

# rename() {
#     parallel -j 60 --delay 0.2 zsh -c 'parallel_rename "$@"' _ ::: "$@"
# }
