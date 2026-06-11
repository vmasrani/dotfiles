# Setup fzf
# ---------
if [[ ! "$PATH" == */Users/vmasrani/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/Users/vmasrani/.fzf/bin"
fi

eval "$(fzf --bash)"
