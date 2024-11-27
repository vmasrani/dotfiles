# shellcheck shell=bash
# shellcheck source=.aliases-and-envs.zsh
# shellcheck source=dotfiles/lscolors.sh
# shellcheck source=.fzf-config.zsh
# shellcheck source=.fzf.zsh


source ~/dotfiles/helper_functions.sh
# Check if both tldr and tte are installed
if command_exists tldr && command_exists /home/vaden/.local/bin/tte; then
    tldr --quiet $(tldr --quiet --list | shuf -n1) | /home/vaden/.local/bin/tte expand
fi

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

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# source custom alias
export ZSH_DISABLE_COMPFIX="true"


source ~/.aliases-and-envs.zsh
source ~/dotfiles/lscolors.sh
source ~/dotfiles/helper_functions.sh
source ~/dotfiles/mount_remotes.sh
. "$HOME/.cargo/env"


# Check if Node.js version 16 is active
if [[ $(node -v) != "v16.0.0" ]]; then
    nvm use 16.0.0 --silent
fi
# conda init
# conda activate base


# Function to check if a proxy is required
function check_proxy() {
    # Attempt to connect to a known external URL
    if curl --max-time 5 --output /dev/null --silent --head --fail http://example.com; then
        # No proxy required
        return 1
    else
        # Proxy required
        return 0
    fi
}

# Check if a proxy is required and set the environment variables accordingly
if check_proxy; then
    export ftp_proxy=http://127.0.0.1:3128
    export http_proxy=http://127.0.0.1:3128
    export https_proxy=http://127.0.0.1:3128
fi


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
# setopt INC_APPEND_HISTORY  # Write to the history file immediately, not when the shell exits.
setopt SHARE_HISTORY  # Share history between all sessions.

# Better vim mode

# Better searching in command mode
bindkey -M vicmd '?' history-incremental-search-backward
bindkey -M vicmd '/' history-incremental-search-forward

# Make Vi mode transitions faster (KEYTIMEOUT is in hundredths of a second)
export KEYTIMEOUT=1

# Enable Ctrl-x-e to edit command line
autoload -U edit-command-line

# Emacs style
zle -N edit-command-line
bindkey '^f' edit-command-line

# hack to fix mac keyboard issues
## note! can use cat -> enter -> keypress to find the key sequence
bindkey '^[[1;3D' backward-word
bindkey '^[[1;3C' forward-word

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize

