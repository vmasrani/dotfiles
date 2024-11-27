#!/bin/bash

#!/bin/bash

if [[ -f $1 ]]; then
  case "$1" in
    *.parquet)
      parquet-tools csv "$1"
      # parquet-tools cat --limit 1000 --format jsonl "$1" | jq -C
      ;;
    *.json)
      jq -C . "$1" 2>/dev/null || bat -n --color=always "$1"
      ;;
    *.pkl|*.pickle)
      pq '' "$1"
      ;;
    *.pt)
      torch-preview "$1"
      ;;
    *.sh)
      bat -n --color=always "$1"
      ;;
    *.npy)
      npy-preview "$1"
      ;;
    *.jpg|*.jpeg|*.png|*.gif)
      chafa --size=80x80 "$1"
      ;;
    *.zip)
      less "$1" | colorize-columns
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
      nbp -c --color-system truecolor -n -w 60 "$1"
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
  eza -aHl --icons --tree --no-user --no-permissions -L 3 -I .git --color=always "$1"
else
  echo "$1"
fi

# if [[ -f $1 ]]; then
#   if [[ $1 == *.parquet ]]; then
#     parquet-tools cat --limit 1000  --format jsonl "$1" | jq -C
#   elif [[ $1 == *.json ]]; then
#     jq -C . "$1" 2>/dev/null || bat -n --color=always "$1"
#   elif [[ $1 == *.pkl || $1 == *.pickle ]]; then
#     pq '' "$1"
#   elif [[ $1 == *.pt ]]; then
#     torch-preview "$1"
#   elif [[ $1 == *.sh ]]; then
#     bat -n --color=always "$1"
#   elif [[ $1 == *.npy ]]; then
#     npy-preview "$1"
#   elif [[ $1 == *.jpg || $1 == *.jpeg || $1 == *.png || $1 == *.gif ]]; then
#     chafa --size=80x80 "$1"
#   elif [[ $1 == *.zip ]]; then
#     less "$1" | colorize-columns
#   elif [[ $1 == *.pdf ]]; then
#     pdftotext "$1" -
#   elif [[ $1 == *.md ]]; then
#     glow -p -w 80 -s dark "$1"
#   elif [[ $1 == *.ipynb ]]; then
#     nbp -c --color-system truecolor -n -w 60 "$1"
#   elif tldr "$1" &> /dev/null; then
#     tldr  --color=always "$1"
#   else
#     bat -n --color=always "$1"
#   fi
# elif [[ -d $1 ]]; then
#   eza -aHl --icons --tree --no-user --no-permissions -L 3 -I .git --color=always "$1"
# else
#   echo "$1"
# fi

