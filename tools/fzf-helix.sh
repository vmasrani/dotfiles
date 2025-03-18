#!/bin/bash

eval "$FZF_CTRL_T_COMMAND . ~ | \
    fzf-tmux -p80%,80% \
        --preview \"fzf-preview {}\" \
        --preview-window=right:50%:wrap \
        --bind 'ctrl-/:change-preview-window(right|down|hidden|)'"
