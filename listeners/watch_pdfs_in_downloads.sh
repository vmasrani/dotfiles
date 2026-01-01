#!/bin/zsh

FSWATCH="/opt/homebrew/bin/fswatch"  # adjust if different
DIR="$HOME/Downloads"
SCRIPT="$HOME/dotfiles/tools/rename_pdf"        # <- full path to your tool (no .sh if not needed)

# Only watch for new files ("Created"), and pass paths NUL-separated for safety
"$FSWATCH" -0 --event Created "$DIR" | while IFS= read -r -d "" file; do
  # Only care about PDFs
  [[ "${file:l}" == *.pdf ]] || continue

  # Skip events where the file is already gone (Removed/Renamed etc.)
  [[ -f "$file" ]] || continue

  # Optionally: wait a moment so the download fully finishes
  # sleep 1

  "$SCRIPT" "$file" </dev/null
done
