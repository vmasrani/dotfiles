# shellcheck shell=bash
# shellcheck source=.aliases-and-envs.zsh
# shellcheck source=dotfiles/lscolors.sh
# shellcheck source=.fzf-config.zsh
# shellcheck source=.fzf.zsh


source ~/dotfiles/helper_functions.sh
# # Check if both tldr and tte are installed
# if command_exists tldr && command_exists $HOME/.local/bin/tte; then
#     tldr --quiet $(tldr --quiet --list | shuf -n1) | $HOME/.local/bin/tte expand
# fi

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


export OPENAI_API_KEY='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'
export ANTHROPIC_API_KEY='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'

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

# Enable Ctrl-x-e to edit command line
autoload -U edit-command-line

# Emacs style
zle -N edit-command-line
bindkey '^f' edit-command-line

# hack to fix mac keyboard issues
## note! can use cat -> enter -> keypress to find the key sequence
bindkey '^[[1;3D' backward-word
bindkey '^[[1;3C' forward-word

source $HOME/ml3/bin/activate


# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize

