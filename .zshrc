
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



export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# source custom alias
export ZSH_DISABLE_COMPFIX="true"


source ~/.aliases-and-envs.zsh
source ~/dotfiles/lscolors.sh
source ~/dotfiles/helper_functions.sh


. "$HOME/.cargo/env"


# Check if Node.js version 16 is active
if [[ $(node -v) != "v16.0.0" ]]; then
    nvm use 16.0.0 --silent
fi
# conda init
# conda activate base

# fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
source ~/.fzf-config.zsh

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

# Better searching in command mode
bindkey -M vicmd '?' history-incremental-search-backward
bindkey -M vicmd '/' history-incremental-search-forward

# Make Vi mode transitions faster (KEYTIMEOUT is in hundredths of a second)
export KEYTIMEOUT=1


# required for anything to work at all
# https://medium.com/codex/using-wsl-2-in-enterprises-d9cef1f60c73
# NOTE: https_proxy env variable should link to a url WITHOUT THE S!!! i.e
# export https_proxy='http://v00838380:mwg1uhz3YHP!wqa5ekz@proxy.huawei.com:8080'
# DOESN"T WORK WITH THE S, SUPER SUBTLE AND ANNOYING AND COUNTERINTUITIVE BUG

export http_proxy='http://v00838380:mwg1uhz3YHP!wqa5ekz@proxy.huawei.com:8080'
export https_proxy='http://v00838380:mwg1uhz3YHP!wqa5ekz@proxy.huawei.com:8080'
export SSL_CERT_DIR=/etc/ssl/certs
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export no_proxy="localhost,127.0.0.1,172.20.176.0/20,127.0.0.1/23119"

function toggle_proxy() {
    if [[ -z "$http_proxy" ]]; then
        export http_proxy='http://v00838380:mwg1uhz3YHP!wqa5ekz@proxy.huawei.com:8080'
        export https_proxy='http://v00838380:mwg1uhz3YHP!wqa5ekz@proxy.huawei.com:8080'
        export SSL_CERT_DIR=/etc/ssl/certs
        export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
        export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
        export no_proxy="localhost,127.0.0.1,172.20.176.0/20,127.0.0.1/23119"
        echo "Proxy enabled"
    else
        unset http_proxy
        unset https_proxy
        unset SSL_CERT_DIR
        unset SSL_CERT_FILE
        unset REQUESTS_CA_BUNDLE
        unset no_proxy
        echo "Proxy disabled"
    fi
}

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

# Automatically attach to an existing tmux session or create a new one
if command -v tmux &> /dev/null; then
  if [[ -z "$TMUX" ]]; then
    tmux attach-session -t default || tmux new-session -s default
  fi
fi

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize


[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/vmasrani/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc'; fi

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
__conda_setup="$('/home/vadmas/miniconda/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "/home/vadmas/miniconda/etc/profile.d/conda.sh" ]; then
        . "/home/vadmas/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="/home/vadmas/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

