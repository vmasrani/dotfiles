#!/bin/bash

## FZF-Z
export FZF_TMUX_OPTS='-p95%,95%'

# https://erees.dev/terminal-tricks/
export FZF_DEFAULT_OPTS="--reverse --ansi \
--color border:41 --border=sharp \
--prompt='➤  ' --pointer='➤ ' --marker='➤ ' \
--inline-info \
--cycle -m  \
--preview-window=right:50%:wrap \
--bind 'ctrl-/:change-preview-window(down|hidden|)' \
--bind 'ctrl-d:preview-half-page-down' \
--bind 'ctrl-u:preview-half-page-up' \
--bind 'ctrl-s:toggle-sort' \
--bind 'ctrl-j:preview-down' \
--bind 'ctrl-k:preview-up' \
--bind 'ctrl-b:preview-bottom' \
--bind 'ctrl-n:preview-top'"
# --bind 'ctrl-r:repeat-fzf-completion' \
# --bind 'right:accept:repeat-fzf-completion'"



#     ctrl-r:'repeat-fzf-completion'
#     right:accept:'repeat-fzf-completion'
#     alt-enter:accept:'zle accept-line'
# )

# --bind 'ctrl-y:execute-silent(echo -n {2..} | copy)+abort'

# export BFS_EXCLUDE="-exclude -name .git -exclude -name __pycache__"
export FD_EXCLUDE="-E __pycache__ -E .git" # ignore more
export BFS_EXCLUDE='! \( -name .git -prune \) ! \( -name  __pycache__ -prune \)'


if type -p bfs >/dev/null; then
    export FZF_DEFAULT_FILES_COMMAND="bfs -x -color $BFS_EXCLUDE -type f"
    export FZF_DEFAULT_DIR_COMMAND="bfs -x -color $BFS_EXCLUDE -type d"
else
    export FZF_DEFAULT_FILES_COMMAND="fd --color='always' --type f --hidden --follow --no-ignore $FD_EXCLUDE"
    export FZF_DEFAULT_DIR_COMMAND="fd --color='always' --type d --hidden --follow --no-ignore $FD_EXCLUDE"
fi


export FZF_DEFAULT_GLOBAL_DIRS="$HOME"


FZF_CTRL_T_LOCAL_GLOBAL_TOGGLE="
  if [[ {fzf:prompt} =~ \"Files\(~\)\" ]]; then
    echo \"change-prompt(Files(.)> )+reload($FZF_DEFAULT_FILES_COMMAND .)\"
  elif [[ {fzf:prompt} =~ \"Files\(.\)\" ]]; then
    echo \"change-prompt(Files(~)> )+reload($FZF_DEFAULT_FILES_COMMAND . $FZF_DEFAULT_GLOBAL_DIRS)\"
  elif [[ {fzf:prompt} =~ \"Dirs\(~\)\" ]]; then
    echo \"change-prompt(Dirs(.)> )+reload($FZF_DEFAULT_DIR_COMMAND .)\"
  elif [[ {fzf:prompt} =~ \"Dirs\(.\)\" ]]; then
    echo \"change-prompt(Dirs(~)> )+reload($FZF_DEFAULT_DIR_COMMAND . $FZF_DEFAULT_GLOBAL_DIRS)\"
  fi
"

FZF_CTRL_T_FILES_DIRS_TOGGLE="
  if [[ {fzf:prompt} =~ \"Files\(~\)\" ]]; then
    echo \"change-prompt(Dirs(~)> )+reload($FZF_DEFAULT_DIR_COMMAND . $FZF_DEFAULT_GLOBAL_DIRS)\"
  elif [[ {fzf:prompt} =~ \"Files\(.\)\" ]]; then
    echo \"change-prompt(Dirs(.)> )+reload($FZF_DEFAULT_DIR_COMMAND .)\"
  elif [[ {fzf:prompt} =~ \"Dirs\(~\)\" ]]; then
    echo \"change-prompt(Files(~)> )+reload($FZF_DEFAULT_FILES_COMMAND . $FZF_DEFAULT_GLOBAL_DIRS)\"
  elif [[ {fzf:prompt} =~ \"Dirs\(.\)\" ]]; then
    echo \"change-prompt(Files(.)> )+reload($FZF_DEFAULT_FILES_COMMAND .)\"
  fi
"


export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_FILES_COMMAND ."
export FZF_CTRL_T_OPTS="--preview 'fzf-preview {}' --prompt 'Files(.)> ' \
--bind 'ctrl-t:transform:$FZF_CTRL_T_LOCAL_GLOBAL_TOGGLE' \
--bind 'ctrl-r:transform:$FZF_CTRL_T_FILES_DIRS_TOGGLE' \
--bind 'ctrl-f:execute:hx {} >/dev/tty' \
--keep-right"


export FZF_CTRL_R_OPTS="
  --preview 'echo {}' --preview-window up:3:wrap
  --bind 'ctrl-/:toggle-preview'
  --bind 'ctrl-y:execute-silent(echo -n {2..} | copy)+abort'"
