#!/bin/bash

if [[ -f $1 ]]; then
  case "$1" in
    *.db)
      sqlite3 -header -csv "$1" "SELECT * FROM $(sqlite3 "$1" '.tables' | awk '{print $1}')" | print_csv
      ;;
    *.csv)
      print_csv "$1"
      ;;
    *.parquet)
      parquet-tools cat --limit 1000 --format jsonl "$1" | jq -C
      ;;
    *.json)
      jq -C . "$1" 2>/dev/null || bat -n --color=always "$1"
      ;;
    *.pkl|*.pickle)
      pkl-preview "$1"
      ;;
    *.pt)
      torch-preview "$1"
      ;;
    *.epub)
      markitdown "$1" | glow -p -w 80 -s dark
      ;;
    *.sh)
      bat -n --color=always "$1"
      ;;
    *.npy)
      npy-preview "$1"
      ;;
    *.feather)
      feather-preview "$1"
      ;;
    *.jpg|*.jpeg|*.png)
      chafa --size=80x80 "$1"
      ;;
    *.zip)
      vd -b "$1" -o - 2>/dev/null | colorize-columns
      ;;
    *.pdf)
      pdftotext "$1" -
      ;;
    *.md)
      glow -p -w 80 -s dark "$1"
      ;;
    *.avi|*.gif|*.mp4|*.mkv|*.webm)
      ffmpegthumbnailer -i "$1" -s 0 -q 10 -o "/tmp/thumbnail.png" -c png -f
      chafa --size=60x60 "/tmp/thumbnail.png"
      ;;
    *.ipynb)
      rich --ipynb "$1"
      ;;
    *)
      if tldr "$1" &> /dev/null; then
        tldr --color=always "$1"
      else
        bat -n --color=always "$1"
      fi
      ;;
  esac
elif [[ -d $1 ]]; then
  eza -aHl --icons --tree --no-user --no-permissions -L 3 -I "$EZA_TREE_IGNORE" --color=always "$1"
else
  echo "$1"
fi
