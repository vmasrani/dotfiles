# shellcheck shell=zsh
# shellcheck source=.aliases-and-envs.zsh
# shellcheck source=lscolors.sh
# shellcheck source=.fzf-config.zsh
# shellcheck source=.fzf.zsh

# Enable Powerlevel10k instant prompt. Should stay close to the top of ~/.zshrc.
# Initialization code that may require console input (password prompts, [y/n]
# confirmations, etc.) must go above this block; everything else may go below.

# Fix for Cursor Agent terminal hangs - skip loading rest of config in Agent mode
# if [[ "$CURSOR_AGENT" == "1" || "$COMPOSER_NO_INTERACTION" == "1" || "$PIP_NO_INPUT" == "true" ]]; then
#   return
# fi

if [[ -r "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh" ]]; then
  source "${XDG_CACHE_HOME:-$HOME/.cache}/p10k-instant-prompt-${(%):-%n}.zsh"
fi
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

# Core Environment Setup
export EDITOR=hx
export VISUAL=hx
export PAGER='less -r'
export DIRSTACKSIZE=20
export KEYTIMEOUT=1
export ZSH_DISABLE_COMPFIX="true"

# Source Core Configuration Files
source ~/helper_functions.sh
source ~/gum_utils.sh
source ~/lscolors.sh
source ~/.aliases-and-envs.zsh
source ~/.local_env.sh  # Should contain API keys and local-specific settings
source ~/.paths.zsh

# export NVM_DIR="$HOME/.nvm"
# [ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
# [ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"
# nvm use --lts > /dev/null

# fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
source ~/.fzf-config.zsh

# Numeric sort
setopt numeric_glob_sort

# History tweaks beyond prezto defaults
setopt APPEND_HISTORY
setopt HIST_REDUCE_BLANKS

# Better vim mode

# Better searching in command mode
bindkey -M vicmd '?' history-incremental-search-backward
bindkey -M vicmd '/' history-incremental-search-forward

# Make Vi mode transitions faster (KEYTIMEOUT already set above)

# Enable Ctrl-x-e to edit command line
autoload -U edit-command-line
zle -N edit-command-line
bindkey '^f' edit-command-line
bindkey '^[[1;3D' backward-word
bindkey '^[[1;3C' forward-word


# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
. "$HOME/.cargo/env"


# bun completions
[ -s "/Users/vmasrani/.bun/_bun" ] && source "/Users/vmasrani/.bun/_bun"

# bun
export BUN_INSTALL="$HOME/.bun"
# PATH is already configured in .paths.zsh with proper ordering

export OLLAMA_CONTEXT_LENGTH=40000

# HACK
export OLLAMA_CONTEXT_LENGTH=40000

alias claude-mem='bun "/Users/vmasrani/.claude/plugins/marketplaces/thedotmack/plugin/scripts/worker-service.cjs"'
