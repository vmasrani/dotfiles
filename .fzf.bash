# Setup fzf
# ---------
if [[ ! "$PATH" == */home/vadmas/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/vadmas/.fzf/bin"
fi

eval "$(fzf --bash)"
