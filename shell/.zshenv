export LANG='en_US.UTF-8'

# Add Homebrew completions to fpath before compinit
if [[ -d /opt/homebrew/share/zsh/site-functions ]]; then
  fpath=(/opt/homebrew/share/zsh/site-functions $fpath)
fi

# Prezto's utility module autoloads wrappers (diff, make, ...) from here. Tools
# that snapshot the interactive shell's functions -- Claude Code does -- capture
# the autoload STUB without this fpath entry, so in a non-interactive shell the
# call dies with "function definition file not found" and exits 1. For `diff`
# that is silently corrupting: exit 1 means "files differ", so a byte-identical
# check reports a difference that was never computed. Pin the path here, in
# .zshenv, so non-interactive shells resolve the real function.
# NOTE: if you ever `brew install colordiff`, the prezto diff wrapper becomes
# `command diff "$@" | colordiff` -- and without pipefail that returns
# colordiff's status, i.e. ALWAYS 0 ("identical"). Use `command diff` in scripts.
if [[ -d ${ZDOTDIR:-$HOME}/.zprezto/modules/utility/functions ]]; then
  fpath=(${ZDOTDIR:-$HOME}/.zprezto/modules/utility/functions $fpath)
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

# Global build/test queue (see ~/dotfiles/tools/testq). Pinned in .zshenv, not
# .zshrc, so NON-INTERACTIVE shells -- which is how agents run commands -- see
# it too. One socket machine-wide is the whole point: it is what makes agents
# in different repos share a single queue instead of one queue each.
export TS_SOCKET="/tmp/testq-${UID}.sock"
export TESTQ_SLOTS=1
