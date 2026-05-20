source ~/.fzf-env.zsh

fasd_fzf-preview() {
    fasd -d -R | \
        awk '{print $2}' | \
        fzf --tmux 95% \
            --bind 'focus:+transform-header:' \
            --bind "$FZF_PREVIEW_WINDOW_BINDING"
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

#export FZF_COMPLETION_TRIGGER=''
source $HOME/.zprezto/contrib/fzf-tab-completion/zsh/fzf-zsh-completion.sh
bindkey '^I' fzf-completion

# rfz to ctrl-X
rfz-command() {
  rfz
}

zle     -N   rfz-command
bindkey '^X' 'rfz-command'

keys=(
    ctrl-r:'repeat-fzf-completion'
    right:accept:'repeat-fzf-completion'
    alt-enter:accept:'zle accept-line'
)

export FZF_COMPLETION_OPTS="--border \
--info=inline \
--bind '$FZF_PREVIEW_WINDOW_BINDING' \
--preview='eval fzf-preview {1}' \
--bind 'result:' \
--bind 'focus:' \
--bind 'focus:+transform-preview-label:' \
--bind 'focus:+transform-header:' \
"

zstyle ':completion:*' fzf-completion-keybindings "${keys[@]}"
zstyle ':completion::*:cd:*' fzf-completion-keybindings "${keys[@]}" /:accept:'repeat-fzf-completion'
zstyle ':completion:*' fzf-search-display true
zstyle ':completion::*:cd::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:ls::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:eza::*' fzf-completion-opts --bind tab:down
zstyle ':completion::*:kill::*' fzf-completion-opts --preview-window=down,3,wrap --preview='eval ps -f -p {1}'
zstyle ':completion::*:(-command-|-parameter-|-brace-parameter-|export|unset|expand):*' fzf-completion-opts --preview='eval eval echo {1}'
zstyle ':completion::*:git::git,add,*' fzf-completion-opts --preview='git -c color.status=always status --short'
zstyle ':completion::*:git::*,[a-z]*' fzf-completion-opts --preview='
eval set -- {+1}
for arg in "$@"; do
    { git diff --color=always -- "$arg" | git log --color=always "$arg" } 2>/dev/null
done'


#!/usr/bin/env bash
# Author: James Cherti
# License: MIT
# URL: https://www.jamescherti.com/tmux-autocomplete-fzf-fuzzy-insertion-scrollback/

tmux_fzf_autocomplete() {
  # Capture the last 100,000 lines from the tmux scrollback buffer, reverse
  # order, and extract strings
  tmux capture-pane -pS -100000 \
    |
    # Split input on spaces and newlines, remove duplicates while preserving
    # order, and keep only strings longer than 4 characters
    awk 'BEGIN { RS = "[ \t\n]" } length($0) > 4 && !seen[$0]++' \
    |
    # Invoke fzf for case-insensitive exact fuzzy matching, with results shown
    # in reverse order
    fzf --no-sort --exact +i --tac
}

fzf-tmux-widget(){
    LBUFFER="${LBUFFER}$(tmux_fzf_autocomplete)"
    local ret=$?
    zle reset-prompt
    return $ret
}

# Pressing Ctrl-n autocompletes from the Tmux scrollback buffer
zle     -N   fzf-tmux-widget
bindkey '^N' fzf-tmux-widget
