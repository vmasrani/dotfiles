# Setup fzf
# ---------
if [[ ! "$PATH" == */home/vaden/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}/home/vaden/.fzf/bin"
fi

# Auto-completion
# ---------------
[[ $- == *i* ]] && source "/home/vaden/.fzf/shell/completion.zsh" 2> /dev/null

# Key bindings
# ------------
source "/home/vaden/.fzf/shell/key-bindings.zsh"
