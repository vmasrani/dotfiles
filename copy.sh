#!/bin/bash

if [[ "$OSTYPE" == "linux-gnu"* ]]; then
  xclip -in -selection clipboard
elif [[ "$OSTYPE" == "darwin"* ]]; then
  pbcopy
fi
