#!/bin/bash

if [ -n "$WSL_DISTRO_NAME" ]; then
    clip.exe
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    xclip -in -selection clipboard
elif [[ "$OSTYPE" == "darwin"* ]]; then
    pbcopy
fi


