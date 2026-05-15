export LANG='en_US.UTF-8'

# Add Homebrew completions to fpath before compinit
if [[ -d /opt/homebrew/share/zsh/site-functions ]]; then
  fpath=(/opt/homebrew/share/zsh/site-functions $fpath)
fi
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

# gog CLI: pull keyring passphrase from macOS keychain so file backend can decrypt non-interactively.
# Stash with: security add-generic-password -s gog-keyring -a "$USER" -w
export GOG_KEYRING_PASSWORD="$(security find-generic-password -s gog-keyring -a "$USER" -w 2>/dev/null)"
