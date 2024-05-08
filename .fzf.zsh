# Setup fzf
# ---------
if [[ ! "$PATH" == *$HOME/.fzf/bin* ]]; then
  PATH="${PATH:+${PATH}:}$HOME/.fzf/bin"
fi

# Auto-completion
# ---------------
source "$HOME/.fzf/shell/completion.zsh"

# Key bindings
# ------------
source "$HOME/.fzf/shell/key-bindings.zsh"

# update history w/ color

# fzf-history-widget () {
#     local selected num
#     setopt localoptions noglobsubst noposixbuiltins pipefail no_aliases 2> /dev/null

#     # awk '{first=$1; $1=""; print $0}' | bat -l zsh | awk -v var1="$first" '{print var1, $0}'

#     selected="$(fc -rl 1  | awk '{ cmd=$0; sub(/^[ \t]*[0-9]+\**[ \t]+/, "", cmd); if (!seen[cmd]++) print $0 }'  | awk '{first=$1; $1=""; print $0}' | bat -l zsh | awk -v var1="$first" '{print var1, $0}' | FZF_DEFAULT_OPTS="--height ${FZF_TMUX_HEIGHT:-40%} ${FZF_DEFAULT_OPTS-} -n2..,.. --scheme=history --bind=ctrl-r:toggle-sort,ctrl-z:ignore ${FZF_CTRL_R_OPTS-} --query=${(qqq)LBUFFER} +m" $(__fzfcmd))"

#     # | awk '{first=$1; $1=""; print $0}' | bat -l zsh | awk -v var1="$first" '{print var1, $0}' |

#     selected="$(fc -rl 1  | awk '{ cmd=$0; sub(/^[ \t]*[0-9]+\**[ \t]+/, "", cmd); if (!seen[cmd]++) print $0 }' | FZF_DEFAULT_OPTS="--height ${FZF_TMUX_HEIGHT:-40%} ${FZF_DEFAULT_OPTS-} -n2..,.. --scheme=history --bind=ctrl-r:toggle-sort,ctrl-z:ignore ${FZF_CTRL_R_OPTS-} --query=${(qqq)LBUFFER} +m" $(__fzfcmd))"

#     local ret=$?
#     if [ -n "$selected" ]
#     then
#             num=$(awk '{print $1}' <<< "$selected")
#             if [[ "$num" =~ '^[1-9][0-9]*\*?$' ]]
#             then
#                     zle vi-fetch-history -n ${num%\*}
#             else
#                     LBUFFER="$selected"
#             fi
#     fi
#     zle reset-prompt
#     return $ret
# }

# echo 'heloo'


