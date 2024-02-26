# Setup fzf
# ---------
if [[ ! "$PATH" == */home/vmasrani/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/vmasrani/.fzf/bin"
fi

# Auto-completion
# ---------------
source "/home/vmasrani/.fzf/shell/completion.zsh"

# Key bindings
# ------------
source "/home/vmasrani/.fzf/shell/key-bindings.zsh"
