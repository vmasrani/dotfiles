export LANG='en_US.UTF-8'
#
# Defines environment variables.
#
# Authors:
#   Sorin Ionescu <sorin.ionescu@gmail.com>
#

# Ensure that a non-login, non-interactive shell has a defined environment.
if [[ ( "$SHLVL" -eq 1 && ! -o LOGIN ) && -s "${ZDOTDIR:-$HOME}/.zprofile" ]]; then
  source "${ZDOTDIR:-$HOME}/.zprofile"
fi
. "$HOME/.cargo/env"

# Begin added by argcomplete
fpath=( /Users/vmasrani/dev/git_repos_to_maintain/hypers_new/.venv/lib/python3.12/site-packages/argcomplete/bash_completion.d "${fpath[@]}" )
# End added by argcomplete

# Begin added by argcomplete
fpath=( /opt/homebrew/share/zsh/site-functions "${fpath[@]}" )
# End added by argcomplete
