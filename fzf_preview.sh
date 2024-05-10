#!/bin/bash

if [[ -f $1 ]]; then
  if [[ $1 == *.parquet ]]; then
    parquet-tools cat --limit 1000  --format jsonl "$1" | jq -c -C
  elif [[ $1 == *.json ]]; then
    jq -C . "$1"
  elif [[ $1 == *.pkl || $1 == *.pickle ]]; then
    pq '' "$1"
  elif [[ $1 == *.pt ]]; then
    torch-preview "$1"
  elif [[ $1 == *.jpg || $1 == *.jpeg || $1 == *.png || $1 == *.gif ]]; then
    chafa --size=80x80 "$1"
  elif [[ $1 == *.pdf ]]; then
    pdftotext "$1" -
  elif [[ $1 == *.md ]]; then
    glow -p -w 80 -s dark "$1"
  elif tldr "$1" &> /dev/null; then
     tldr  --color=always "$1"
  else
     bat -n --color=always "$1"
  fi
elif [[ -d $1 ]]; then
  eza -aHl --icons --tree --no-user --no-permissions -L 3 -I .git --color=always "$1"
else
  echo "$1"
fi




# if [[ -f $1 ]]; then
#   if [[ $1 == *.parquet ]]; then
#     parquet-tools cat --limit 1000  --format jsonl "$1" | jq -c -C
#   elif [[ $1 == *.json ]]; then
#     jq -C . "$1"
#   elif [[ $1 == *.pkl || $1 == *.pickle ]]; then
#     pq '' "$1"
#   elif [[ $1 == *.pt ]]; then
#     torch-preview "$1"
#   elif [[ $1 == *.jpg || $1 == *.jpeg || $1 == *.png || $1 == *.gif ]]; then
#     chafa --size=80x80 "$1"
#   elif [[ $1 == *.pdf ]]; then
#     pdftotext "$1" -
#   elif [[ $1 == *.md ]]; then
#     glow -p -w 80 -s dark "$1"
#   else
#     if command -v "$1" &> /dev/null; then
#       tldr "$1"
#     else
#       bat -n --color=always "$1"
#     fi
#   fi
# elif [[ -d $1 ]]; then
#   eza -aHl --icons --tree --no-user --no-permissions -L 3 -I .git --color=always "$1"
# else
#   echo "$1"
# fi
