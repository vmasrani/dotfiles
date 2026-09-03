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

# Global build/test queue (see ~/dotfiles/tools/queue). Pinned in .zshenv, not
# .zshrc, so NON-INTERACTIVE shells -- which is how agents run commands -- see
# it too. One socket machine-wide is the whole point: it is what makes agents
# in different repos share a single queue instead of one queue each.
export TS_SOCKET="/tmp/testq-${UID}.sock"
# `:-` matters. .zshenv is sourced by EVERY zsh, including non-interactive
# `zsh -c`, so a bare `export QUEUE_SLOTS=1` runs AFTER a caller's assignment
# prefix and silently clobbers it -- `QUEUE_SLOTS=3 queue ...` would become a
# no-op, and any "export to persist" advice from the tool itself would be
# undone by the next shell. Defaulting instead of assigning lets an explicit
# value survive.

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

# Per-machine concurrency for `queue` (see ~/dotfiles/tools/queue). Defaults to
# 1; a machine-specific override (e.g. this box's Linux-only config) sets it
# earlier in the sourcing chain and this default leaves that untouched.
export QUEUE_SLOTS="${QUEUE_SLOTS:-1}"

# nextest defaults to one test process PER LOGICAL CPU, PER RUN -- so
# QUEUE_SLOTS concurrent jobs oversubscribe (e.g. 64 cpus x 3 slots = 192 test
# processes). Cap per-job threads at cpus/slots, floored at 1; an explicit
# NEXTEST_TEST_THREADS already in the environment always wins.
if command -v nproc >/dev/null 2>&1; then
  _dotfiles_cpus="$(nproc)"
elif command -v sysctl >/dev/null 2>&1; then
  _dotfiles_cpus="$(sysctl -n hw.logicalcpu 2>/dev/null)"
fi
if [[ -n "${_dotfiles_cpus:-}" ]]; then
  _dotfiles_threads=$(( _dotfiles_cpus / QUEUE_SLOTS ))
  (( _dotfiles_threads < 1 )) && _dotfiles_threads=1
  export NEXTEST_TEST_THREADS="${NEXTEST_TEST_THREADS:-$_dotfiles_threads}"
else
  print -u2 "zshenv: neither nproc nor sysctl -n hw.logicalcpu found -- leaving NEXTEST_TEST_THREADS unset"
fi
unset _dotfiles_cpus _dotfiles_threads
