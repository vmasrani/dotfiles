# Setup fzf
# ---------
if [[ ! "$PATH" == */home/vaden/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/vaden/.fzf/bin"
fi

eval "$(fzf --bash)"
