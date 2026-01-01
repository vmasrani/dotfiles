#!/bin/zsh

FSWATCH="/opt/homebrew/bin/fswatch"  # adjust if different
DIR="$HOME/Downloads"
SCRIPT="$HOME/dotfiles/tools/convert_ebook"

# Only watch for new files ("Created"), and pass paths NUL-separated for safety
"$FSWATCH" -0 --event Created "$DIR" | while IFS= read -r -d "" file; do
  # Only care about ebooks (epub/mobi)
  [[ "${file:l}" == *.epub || "${file:l}" == *.mobi ]] || continue

  # Skip events where the file is already gone (Removed/Renamed etc.)
  [[ -f "$file" ]] || continue

  # Optionally: wait a moment so the download fully finishes
  # sleep 1

  "$SCRIPT" "$file" </dev/null
done
