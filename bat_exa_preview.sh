#!/bin/bash

if [[ -f $1 ]]; then
  bat -n --color=always "$1"
elif [[ -d $1 ]]; then
  eza -aHl --icons --tree --no-user --no-permissions -L 2 --color=always "$1"
else
  echo "$1"
fi
