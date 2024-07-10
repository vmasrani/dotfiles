
# shellcheck shell=bash
# shellcheck source=.aliases-and-envs.zsh
# shellcheck source=dotfiles/lscolors.sh
# shellcheck source=.fzf-config.zsh
# shellcheck source=.fzf.zsh


tldr --quiet $(tldr --quiet --list | shuf -n1)

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

# source custom alias
export ZSH_DISABLE_COMPFIX="true"


source ~/.aliases-and-envs.zsh
source ~/dotfiles/lscolors.sh
. "$HOME/.cargo/env"

# conda init
# conda activate base

# fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
source ~/.fzf-config.zsh

  # ruby
source $(brew --prefix)/opt/chruby/share/chruby/chruby.sh
source $(brew --prefix)/opt/chruby/share/chruby/auto.sh
source /opt/homebrew/opt/chruby/share/chruby/chruby.sh
chruby ruby-3.3.4
source ~/.iterm2_shell_integration.zsh

# Customize to your needs...
export DIRSTACKSIZE=20
export EDITOR=hx
export VISUAL=hx
export PAGER='less -r'
#Allow group rename
autoload -U zmv

#Numeric sort
setopt numeric_glob_sort

# Better vim mode
eval "$(/usr/local/bin/brew shellenv)"

# Better searching in command mode
bindkey -M vicmd '?' history-incremental-search-backward
bindkey -M vicmd '/' history-incremental-search-forward

# Make Vi mode transitions faster (KEYTIMEOUT is in hundredths of a second)
export KEYTIMEOUT=1

# Better vim mode


# Enable Ctrl-x-e to edit command line
autoload -U edit-command-line

# Emacs style
zle -N edit-command-line
bindkey '^f' edit-command-line

# hack to fix mac keyboard issues
## note! can use cat -> enter -> keypress to find the key sequence
bindkey '^[[1;3D' backward-word
bindkey '^[[1;3C' forward-word


_aichat_zsh() {
    if [[ -n "$BUFFER" ]]; then
        local _old=$BUFFER
        BUFFER+="⌛"
        zle -I && zle redisplay
        BUFFER=$(aichat -e "$_old")
        zle end-of-line
    fi
}
zle -N _aichat_zsh
bindkey '\ee' _aichat_zsh


# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize


[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/vmasrani/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc'; fi

# Created by `pipx` on 2024-07-10 03:49:22
export PATH="$PATH:/Users/vmasrani/Library/Python/3.11/bin"
