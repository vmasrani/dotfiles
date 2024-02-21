#!/bin/bash

if [[ -f $1 ]]; then
  if [[ $1 == *.parquet ]]; then
    parquet-tools cat --limit 1000  --format jsonl "$1" | jq -c -C
  elif [[ $1 == *.json ]]; then
    jq -C . "$1"
  else
    if command -v "$1" &> /dev/null; then
      man "$1"
    else
      bat -n --color=always "$1"
    fi
  fi
elif [[ -d $1 ]]; then
  eza -aHl --icons --tree --no-user --no-permissions -L 2 --color=always "$1"
else
  echo "$1"
fi



