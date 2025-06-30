#!/bin/zsh
# shellcheck shell=zsh
# ===================================================================
# Helper Functions for Dotfiles
# ===================================================================

# Helper function to check if a command exists
command_exists() {
    command -v "$1" > /dev/null
}



move_and_symlink() {
    local source="$1"
    local dest="$2"

    if [ -e "$source" ]; then
        local source_dir="$(dirname "$source")"
        local source_name="$(basename "$source")"

        mkdir -p "$dest"
        mv "$source" "$dest/"
        ln -si "$dest/$source_name" "$source_dir"
    else
        echo "Error: $source does not exist"
        return 1
    fi
}

file_count() {

    # Calculate the maximum width for directory names
    max_dir_length=$(find . -mindepth 1 -maxdepth 1 -type d 2>/dev/null | awk '{print length}' | sort -nr | head -1)

    # Print the header
    printf "\033[1;34m%-*s\033[0m  \033[1;32m%10s\033[0m  \033[1;33m%10s\033[0m\n" "$max_dir_length" "Directory" "Files" "Size"

    # Iterate over directories and print their details
    find . -mindepth 1 -maxdepth 1 -type d 2>/dev/null | while read -r dir; do
        file_count=$(find -L "$dir" -type f 2>/dev/null | wc -l)
        total_size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        printf "\033[1;34m%-*s\033[0m  \033[1;32m%10s\033[0m  \033[1;33m%10s\033[0m\n" "$max_dir_length" "$dir" "$file_count" "$total_size"
    done



}

remove_broken_symlinks() {
    local dir="${1:-.}"  # Default to the current directory if no argument is provided
    local broken_links=()

    # Find all broken symbolic links in the directory
    while IFS= read -r -d '' link; do
        broken_links+=("$link")
    done < <(find "$dir"  -maxdepth 1 -xtype l -print0)

    # Check if there are any broken symbolic links
    if [ "${#broken_links[@]}" -gt 0 ]; then
        echo "The following broken symbolic links were found in $dir:"
        for link in "${broken_links[@]}"; do
            echo "- $link"
        done

        # Prompt the user for confirmation
        echo -n "Do you want to delete these broken symbolic links? (y/n) "
        read -r answer
        if [[ $answer =~ ^[Yy]$ ]]; then
            echo "Deleting broken symbolic links..."
            for link in "${broken_links[@]}"; do
                echo "Removing $link"
                rm "$link"
            done
        else
            echo "Skipping deletion of broken symbolic links."
        fi
    else
        echo "No broken symbolic links found in $dir."
    fi
}
