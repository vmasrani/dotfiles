# Setup fzf
# ---------
if [[ ! "$PATH" == */root/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/root/.fzf/bin"
fi

eval "$(fzf --bash)"
