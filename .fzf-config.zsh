source ~/.fzf-env.zsh

fasd_fzf-preview() {
    fasd -d -R | \
        awk '{print $2}' | \
        fzf-tmux -p80%,80% \
            --preview "fzf-preview {}" \
            --preview-window=right:50%:wrap \
            --bind 'ctrl-/:change-preview-window(right|down|hidden|)'
}

fzf-fasd-widget(){
 LBUFFER="${LBUFFER}$(fasd_fzf-preview)"
 local ret=$?
 zle reset-prompt
 return $ret
}


zle     -N   fzf-fasd-widget
bindkey '^G' fzf-fasd-widget

# Use fd (https://github.com/sharkdp/fd) instead of the default find
# command for listing path candidates.
# - The first argument to the function ($1) is the base path to start traversal
# - See the source code (completion.{bash,zsh}) for the details.

_fzf_compgen_path() {
  fd --hidden --follow --no-ignore -c always --exclude ".git" . "$1"
}
# Use fd to generate the list for directory completion
_fzf_compgen_dir() {
  fd --type d --hidden --follow --no-ignore -c always --exclude ".git" . "$1"
}


# bfs_fzf-preview() {
#     eval $FZF_CTRL_T_COMMAND . | \
#         fzf-tmux -p80%,80% \
#             --preview "fzf-preview {}" \
#             --preview-window=right:50%:wrap \
#             --bind 'ctrl-/:change-preview-window(right|down|hidden|)'
# }



# bfs_fzf-preview2() {
#     eval $FZF_CTRL_T_COMMAND . | \
#         fzf-tmux -p80%,80% \
#             $FZF_CTRL_T_OPTS
# }


bfs_fzf-preview() {
    hx $(eval $FZF_CTRL_T_COMMAND . ~ | \
        fzf-tmux -p80%,80% \
            --preview "fzf-preview {}" \
            --preview-window=right:50%:wrap \
            --bind 'ctrl-/:change-preview-window(right|down|hidden|)')

}



#export FZF_COMPLETION_TRIGGER=''
source $HOME/.zprezto/contrib/fzf-tab-completion/zsh/fzf-zsh-completion.sh
bindkey '^I' fzf-completion

# rfz to ctrl-X
rfz-command() {
  rfz
}

zle     -N   rfz-command
bindkey '^X' 'rfz-command'



# export FD_OPTIONS="--hidden --follow --no-ignore -c always"

# press ctrl-r to repeat completion *without* accepting i.e. reload the completion
# press right to accept the completion and retrigger it
# press alt-enter to accept the completion and run it
keys=(
    ctrl-r:'repeat-fzf-completion'
    right:accept:'repeat-fzf-completion'
    alt-enter:accept:'zle accept-line'
)
zstyle ':completion:*' fzf-completion-keybindings "${keys[@]}"
# also accept and retrigger completion when pressing / when completing cd

zstyle ':completion::*:cd:*' fzf-completion-keybindings "${keys[@]}" /:accept:'repeat-fzf-completion'

zstyle ':completion:*' fzf-search-display true

export FZF_COMPLETION_OPTS="--border --info=inline --bind 'ctrl-/:change-preview-window(down|hidden|)'  --preview='eval fzf-preview {1}'"

zstyle ':completion::*:cd::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:ls::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:eza::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:kill::*' fzf-completion-opts --preview-window=down,3,wrap --preview='eval ps -f -p {1}'

# preview when completing env vars (note: only works for exported variables)
# eval twice, first to unescape the string, second to expand the $variable
zstyle ':completion::*:(-command-|-parameter-|-brace-parameter-|export|unset|expand):*' fzf-completion-opts --preview='eval eval echo {1}'
# preview a `git status` when completing git add
zstyle ':completion::*:git::git,add,*' fzf-completion-opts --preview='git -c color.status=always status --short'
# if other subcommand to git is given, show a git diff or git log
zstyle ':completion::*:git::*,[a-z]*' fzf-completion-opts --preview='
eval set -- {+1}
for arg in "$@"; do
    { git diff --color=always -- "$arg" | git log --color=always "$arg" } 2>/dev/null
done'





