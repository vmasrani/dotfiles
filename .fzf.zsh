# Setup fzf
# ---------
if [[ ! "$PATH" == */Users/vmasrani/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/Users/vmasrani/.fzf/bin"
fi

# Auto-completion
# ---------------
source "/Users/vmasrani/.fzf/shell/completion.zsh"

# Key bindings
# ------------
source "/Users/vmasrani/.fzf/shell/key-bindings.zsh"
