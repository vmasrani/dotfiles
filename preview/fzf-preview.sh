#!/bin/bash

MAX_LINES=500
TIMEOUT=5

preview() { timeout "$TIMEOUT" "$@" 2>/dev/null; }

# Resolve symlinks
[[ -L "$1" ]] && set -- "$(readlink -f "$1")"

if [[ -f "$1" ]]; then
  # Empty file check
  [[ ! -s "$1" ]] && echo "[empty file]" && exit 0

  case "$1" in
    # Data
    *.db)
      preview sqlite3 -header -csv "$1" "SELECT * FROM $(sqlite3 "$1" '.tables' | awk '{print $1}')" | head -n $MAX_LINES | print_csv
      ;;
    *.csv)
      preview print_csv "$1"
      ;;
    *.tsv)
      preview column -t -s $'\t' "$1" | head -n $MAX_LINES | bat --color=always -l tsv
      ;;
    *.parquet)
      preview parquet-tools cat --limit 1000 --format jsonl "$1" | jq -C
      ;;
    *.json)
      preview jq -C . "$1" | head -n $MAX_LINES || preview bat -n --color=always --line-range :$MAX_LINES "$1"
      ;;
    *.jsonl|*.ndjson)
      preview head -n $MAX_LINES "$1" | jq -C .
      ;;
    *.feather)
      preview feather-preview "$1"
      ;;

    # ML
    *.pkl|*.pickle)
      preview pkl-preview "$1"
      ;;
    *.pt|*.pth)
      preview torch-preview "$1"
      ;;
    *.onnx)
      preview onnx-preview "$1"
      ;;
    *.npy)
      preview npy-preview "$1"
      ;;

    # Docs
    *.pdf)
      preview pdftotext "$1" - | head -n $MAX_LINES
      ;;
    *.md)
      preview glow -p -w 80 -s dark "$1"
      ;;
    *.docx|*.pptx|*.xlsx|*.epub)
      preview markitdown "$1" | head -n $MAX_LINES | glow -p -w 80 -s dark
      ;;
    *.html|*.htm)
      preview markitdown "$1" | head -n $MAX_LINES | glow -p -w 80 -s dark
      ;;
    *.ipynb)
      preview rich --ipynb "$1"
      ;;

    # Images
    *.jpg|*.jpeg|*.png|*.webp|*.bmp|*.tiff|*.ico|*.heic|*.svg)
      preview chafa --size=80x80 "$1"
      ;;

    # Audio
    *.wav|*.mp3|*.flac|*.ogg|*.m4a|*.aac|*.wma)
      preview mediainfo "$1" || file --brief "$1"
      ;;

    # Video
    *.avi|*.gif|*.mp4|*.mkv|*.webm|*.mov|*.flv|*.wmv|*.m4v)
      preview ffmpegthumbnailer -i "$1" -s 0 -q 10 -o "/tmp/thumbnail.png" -c png -f
      preview chafa --size=60x60 "/tmp/thumbnail.png"
      ;;

    # Archives
    *.tar|*.tar.gz|*.tgz|*.tar.bz2|*.tbz2|*.tar.xz|*.txz|*.tar.zst)
      preview tar tf "$1" | head -n $MAX_LINES
      ;;
    *.zip)
      preview vd -b "$1" -o - | colorize-columns
      ;;
    *.gz)
      preview gzip -l "$1"
      ;;
    *.rar)
      preview unrar l "$1" | head -n $MAX_LINES
      ;;
    *.7z)
      preview 7z l "$1" | head -n $MAX_LINES
      ;;

    # Log files (tail — recent entries most useful)
    *.log)
      preview tail -n $MAX_LINES "$1" | bat --color=always -l log
      ;;

    # Catch-all with binary detection
    *)
      if file --brief --mime-type "$1" | grep -q '^text/'; then
        preview bat -n --color=always --line-range :$MAX_LINES "$1"
      else
        file --brief "$1"
      fi
      ;;
  esac
elif [[ -d "$1" ]]; then
  eza -aHl --icons --tree --no-user --no-permissions -L 3 -I "$EZA_TREE_IGNORE" --color=always "$1"
else
  echo "$1"
fi
