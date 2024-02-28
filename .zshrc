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
__conda_setup="$('$HOME/miniconda/bin/conda' 'shell.zsh' 'hook' 2> /dev/null)"
if [ $? -eq 0 ]; then
    eval "$__conda_setup"
else
    if [ -f "$HOME/miniconda/etc/profile.d/conda.sh" ]; then
        . "$HOME/miniconda/etc/profile.d/conda.sh"
    else
        export PATH="$HOME/miniconda/bin:$PATH"
    fi
fi
unset __conda_setup
# <<< conda initialize <<<

# source custom alias
export ZSH_DISABLE_COMPFIX="true"


source ~/.aliases-and-envs
source ~/dotfiles/lscolors.sh

# conda activate ml3

# fzf
[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh
source ~/.fzf-config.zsh

if [[ "$OSTYPE" == "darwin"* ]]; then
  # ruby
  source $(brew --prefix)/opt/chruby/share/chruby/chruby.sh
  source $(brew --prefix)/opt/chruby/share/chruby/auto.sh
  source /opt/homebrew/opt/chruby/share/chruby/chruby.sh
  chruby ruby-3.1.3
fi

# Customize to your needs...
export DIRSTACKSIZE=20
export EDITOR=vim
export VISUAL=vim

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

# To customize prompt, run `p10k configure` or edit ~/.p10k.zsh.
[[ ! -f ~/.p10k.zsh ]] || source ~/.p10k.zsh
# export PATH="$HOME/miniconda/bin:$PATH"  # commented out by conda initialize


[ -f ~/.fzf.zsh ] && source ~/.fzf.zsh

source ~/.iterm2_shell_integration.zsh

# The next line updates PATH for the Google Cloud SDK.
if [ -f '/Users/vmasrani/google-cloud-sdk/path.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/path.zsh.inc'; fi

# The next line enables shell command completion for gcloud.
if [ -f '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc' ]; then . '/Users/vmasrani/google-cloud-sdk/completion.zsh.inc'; fi
