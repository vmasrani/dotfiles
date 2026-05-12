# Setup fzf
# ---------
if [[ ! "$PATH" == */home/vmasrani/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/vmasrani/.fzf/bin"
fi

eval "$(fzf --bash)"
