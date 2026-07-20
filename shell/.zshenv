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
# `:-` matters. .zshenv is sourced by EVERY zsh, including non-interactive
# `zsh -c`, so a bare `export TESTQ_SLOTS=2` runs AFTER a caller's assignment
# prefix and silently clobbers it -- `TESTQ_SLOTS=4 testq ...` was a no-op,
# and `testq --slots N`'s own "export to persist" advice was undone by the
# next shell. Defaulting instead of assigning lets an explicit value survive.
#
# Why 2 and not more (raised from 1, 2026-07-20): the -N weighting in testq
# makes HEAVY jobs (nextest/test/bench, just test*) request ALL slots, so a
# suite still runs exclusively at any slot count -- the two-suites-at-once RAM
# cliff (2x15GB > 13GB usable) simply cannot occur. The slot count only sets
# how many LIGHT jobs (check/clippy/build) overlap. On this 16 GB box two
# concurrent light builds are safe; three can approach the ceiling if they all
# peak together. So 2 buys agent-parallel light work at no suite-RAM risk.
# Bump to 3 here if light-job parallelism matters more than the margin.
export TESTQ_SLOTS="${TESTQ_SLOTS:-2}"
export TESTQ_HEARTBEAT="${TESTQ_HEARTBEAT:-30}"

# The `cargo` shim (~/dotfiles/tools/shims/cargo) must precede ~/.cargo/bin so
# that heavy cargo work cannot run outside the queue. It lives HERE, not in
# .paths.zsh, for the same reason as the block above: .paths.zsh is sourced
# from .zshrc, which only runs for INTERACTIVE shells, while agents invoke
# `zsh -c`. A shim that is absent from exactly the shells agents use would
# guard nothing.
#
# The PreToolUse hook matches command STRINGS, so any indirection escapes it
# (`zsh build.sh`, `just test`, `make check`, `env FOO=1 cargo build`). This
# shim cannot be escaped that way: whatever finally execs cargo runs it.
# MEASURED 2026-07-20: a `zsh script.sh` containing `cargo build` slipped the
# hook and ran unqueued at 48% CPU against a live nextest suite.
#
# To disable: delete these two lines. Nothing else depends on them.
[[ -d "$HOME/tools/shims" ]] && path=("$HOME/tools/shims" $path)
export PATH
