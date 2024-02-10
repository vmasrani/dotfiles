# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.
if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi


# [[ "$TERM_PROGRAM" == "vscode" ]] && . "$(code --locate-shell-integration-path zsh)"

#
# Executes commands at the start of an interactive session.
#
# Authors:
#   Sorin Ionescu <sorin.ionescu@gmail.com>
#
# Source Prezto.
if [[ -s "${ZDOTDIR:-$HOME}/.zprezto/init.zsh" ]]; then
  source "${ZDOTDIR:-$HOME}/.zprezto/init.zsh"
fi

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/vaden/miniconda/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/vaden/miniconda/etc/profile.d/conda.sh" ]; then
        . "/home/vaden/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="/home/vaden/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<


export WANDB_API_KEY="local-1cb84cdb8818ab552fb57da6b591af732d4ba09d"
export WANDB_BASE_URL="http://localhost:8080"
export PYTHONPATH=~/.python:~/.roma-scripts:$PYTHONPATH
export PATH=~/.local/bin:$PATH
#
#
export NODE_EXTRA_CA_CERTS=$(ls /home/vaden/certs/*pem | tr '\n' ':')
conda activate ml3

alias zshrc='vim ~/.zshrc'
alias zpreztorc='vim ~/.zpreztorc'

alias l='eza -aHl --icons --git'
alias lt='eza -aHl --icons --git --sort=modified'
alias lf='eza -aHl --icons --git --sort=size'
alias ld='eza -aHlD --icons --git'


alias cd..='cd ../'                         # Go back 1 directory level (for fast typers)
alias ..='cd ../'                           # Go back 1 directory level
alias .1='cd ../'                           # Go back 1 directory level
alias .2='cd ../../'                        # Go back 2 directory levels
alias .3='cd ../../../'                     # Go back 3 directory levels
alias .4='cd ../../../../'                  # Go back 4 directory levels
alias .5='cd ../../../../../'               # Go back 5 directory levels
alias .6='cd ../../../../../../'            # Go back 6 directory levels
alias .7='cd ../../../../../../../'            # Go back 6 directory levels
cdd() { builtin cd "$@"; ll; }               # Always list directory contents upon 'cd'


#tree alias's"
#   -L 1
alias tree="eza --long --tree --no-user --no-time --total-size --icons --changed"
alias t1='tree -L 1'
alias t2='tree -L 2'
alias t3='tree -L 3'
alias t4='tree -L 4'


#Preferred implementations
alias mv='mv -iv'                           # Preferred 'mv' implementation
alias mkdir='mkdir -pv'                     # Preferred 'mkdir' implementation
alias ll='ls -FGlAhp'                       # Preferred 'ls' implementation
alias less='less -FSRXc'                    # Preferred 'less' implementation
alias rm='rm -v'                            # Show what has been removed
alias cp='cp -v'                            # Show what has been copied
# alias fr='open -a Finder ./'                # fr:            Opens current directory in MacOS Finder
# alias open='explorer.exe'
alias ~="cd ~"                              # ~:            Go Home
alias h="history"                           # h:            History
alias path='echo -e ${PATH//:/\\n}'         # path:         Echo all executable Paths
# alias fix_stty='stty sane'                  # fix_stty:     Restore terminal settings when screwed up
# alias cic='set completion-ignore-case On'   # cic:          Make tab-completion case-insensitive
alias du='du -sh'                           # Show usage in human readable format and sum content of subdirectories
alias fd='fd -HI'                           # fd all
alias rg='rg --no-ignore'
alias bat='bat -n --color=always'
alias refresh='source ~/.zshrc'

[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

EDITOR=vim
VISUAL=vim

#Allow group rename
autoload -U zmv

# Enable Ctrl-x-e to edit command line
autoload -U edit-command-line
# Emacs style
zle -N edit-command-line
bindkey '^F' edit-command-line

# FZF-
export FZF_TMUX_OPTS='-p80%,80%'
export FZFZ_SUBDIR_LIMIT="1000"
export FZFZ_EXTRA_DIRS="'../../..'"
export FZFZ_EXCLUDE_PATTERN='\.git|venv|.arrow'

export FZF_DEFAULT_COMMAND='fd --type f --hidden --follow --no-ignore --exclude .git'


# here we turn multi on, but then deactive it by rebinding tab to 'down'. then we can reactivate it again by binding tab --bind tab:toggle+down, or binding it to anything else
export FZF_DEFAULT_OPTS="--layout=reverse --pointer '=>' --inline-info --cycle --keep-right --bind tab:down -m --preview-window=right:50%:wrap --bind 'ctrl-/:change-preview-window(down|hidden|)'"
export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND ."
# export FZF_CTRL_T_COMMAND="$FZF_DEFAULT_COMMAND . '.' '/home/vaden/dev'"
# export FZF_ALT_C_COMMAND="fd -t d . --no-ignore  '.' '/home/vaden/dev'"


# IDEA: Add toggles to file selector
# - full path at top
# - switch to global directory
# - toggle files or directories
# - free up bad global search 
export FZF_CTRL_T_OPTS="--bind tab:toggle+down --preview 'bat -n --color=always {}'"
export FZF_CTRL_R_OPTS="
  --preview 'echo {}' --preview-window up:3:hidden:wrap
  --algo=v1
  --bind 'ctrl-/:toggle-preview'
  --color header:italic"



# export FZF_CTRL_T_OPTS="--preview 'bat -n --color=always {}' --preview-window=right:50%:wrap --bind 'ctrl-/:change-preview-window(down|hidden|)'"
source /home/vaden/.zprezto/contrib/fzf-tab-completion/zsh/fzf-zsh-completion.sh
bindkey '^I' fzf_completion

# press ctrl-r to repeat completion *without* accepting i.e. reload the completion
# press right to accept the completion and retrigger it
# press alt-enter to accept the completion and run it
keys=(
    ctrl-r:'repeat-fzf-completion'
    right:accept:'repeat-fzf-completion'
    alt-enter:accept:'zle accept-line'
)

export tree_cmd="eza --long --tree --no-user --no-time --total-size --icons --changed"

zstyle ':completion:*' fzf-completion-keybindings "${keys[@]}"
# also accept and retrigger completion when pressing / when completing cd
zstyle ':completion::*:cd:*' fzf-completion-keybindings "${keys[@]}" /:accept:'repeat-fzf-completion'

# basic file preview for ls (you can replace with something more sophisticated than head)
zstyle ':completion::*:cd::*' fzf-completion-opts --preview 'eval /home/vaden/deb/usr/bin/tree -C {1} | head -200'

zstyle ':completion::*:cp::*' fzf-completion-opts --bind tab:toggle+down
zstyle ':completion::*:mv::*' fzf-completion-opts --bind tab:toggle+down

zstyle ':completion::*:kill::*' fzf-completion-opts --bind tab:toggle+down

# basic file preview for ls (you can replace with something more sophisticated than head)
zstyle ':completion::*:ls::*' fzf-completion-opts --preview='eval bat -n --color=always {1}'

# zstyle ':completion::*:eza::*' fzf-completion-opts --preview='eval [ -f {1} ] && eval bat -n --color=always {1} || eval eval eza --long --tree --no-user --no-time --total-size --icons --changed -L 1 {1} | head -200'
zstyle ':completion::*:eza::*' fzf-completion-opts --preview='eval [ -f {1} ] && eval bat -n --color=always {1} || eval /home/vaden/deb/usr/bin/tree -C {1} | head -200'

# zstyle ':completion::*:eza::*' fzf-completion-opts --preview='eval bat -n --color=always {1}'


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

zstyle ':completion:*' fzf-search-display true

# Use fd (https://github.com/sharkdp/fd) instead of the default find
# command for listing path candidates.
# - The first argument to the function ($1) is the base path to start traversal
# - See the source code (completion.{bash,zsh}) for the details.
_fzf_compgen_path() {
  fd --hidden --follow --no-ignore --exclude ".git" . "$1"
}

# Use fd to generate the list for directory completion
_fzf_compgen_dir() {
  fd --type d --hidden --follow --no-ignore --exclude ".git" . "$1"
}

# Advanced customization of fzf options via _fzf_comprun function
# - The first argument to the function is the name of the command.
# - You should make sure to pass the rest of the arguments to fzf.
_fzf_comprun() {
  local command=$1
  shift

  case "$command" in
    cd)           fzf --preview '/home/vaden/deb/usr/bin/tree -C {} | head -200'   "$@" ;;
    export|unset) fzf --preview "eval 'echo \$'{}"         "$@" ;;
    ssh)          fzf --preview 'dig {}'                   "$@" ;;
    *)            fzf --preview 'bat -n --color=always {}' "$@" ;;
  esac
}

fzf-fasd-widget(){
 LBUFFER="${LBUFFER}$(fasd -d -R | awk '{print $2}' | fzf-tmux -p80%,80% --preview '/home/vaden/deb/usr/bin/tree -C {}' --preview-window=down:50%:wrap --bind 'ctrl-/:change-preview-window(right|hidden|)')"
 local ret=$?
 zle reset-prompt
 return $ret
}

zle     -N   fzf-fasd-widget
bindkey '^G' fzf-fasd-widget





fzf-global-file-search-widget(){
 LBUFFER="${LBUFFER}$(fd --type f --hidden --follow --no-ignore --exclude .git '.'  /home/vaden/dev | fzf-tmux -p80%,80% --preview '/home/vaden/.local/bin/bat -n --color=always {}' --preview-window=right:50%:wrap --bind 'ctrl-/:change-preview-window(down|hidden|)')"
 local ret=$?
 zle reset-prompt
 return $ret
}




zle     -N   fzf-global-file-search-widget
bindkey '^Xg' fzf-global-file-search-widget
bindkey '^H' backward-kill-word

run-rg-fzf(){
 /home/vaden/bin/rfv
}

zle     -N   run-rg-fzf
bindkey '^Xl' run-rg-fzf




# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
