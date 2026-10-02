# sccache environment -- POSIX sh, sourced by shell/.zshenv (EVERY zsh, incl. the
# non-interactive `zsh -c` agents use).
#
# Why this is not in .zshrc / .aliases-and-envs.zsh: the sccache SERVER inherits the
# environment of whichever `sccache` client happens to start it, and that is often an
# agent's non-interactive shell. Those never read .zshrc, so a server started there
# silently ran with the default cache dir and the default 10 GiB limit.
# Every setting uses `:-` so a caller's or .zshenv.local's value wins.
#
# tools/sccache-watchdog NEVER starts a server (a server started from launchd gets its
# rustc children blocked by a macOS TCC consent prompt for /Volumes), so the server's
# logging has to come from the clients' environment too.
#
# Cache on the external SSD when there is one (Rust artifacts are big and the dev
# trees live there anyway). Linux boxes and Macs without /Volumes/external fall
# back to ~/.cache/sccache (a Mac path on Linux made every cargo build fail with
# "failed to create directory /Volumes/external/sccache: Permission denied").
if [ -z "${SCCACHE_DIR:-}" ]; then
  if [ -d /Volumes/external ]; then
    SCCACHE_DIR=/Volumes/external/sccache
  else
    SCCACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/sccache"
  fi
fi
# 1 GiB (the old launchctl value) was 100% full and thrashing -- Rust hit rate 1.39%.
SCCACHE_CACHE_SIZE="${SCCACHE_CACHE_SIZE:-100G}"
export SCCACHE_DIR SCCACHE_CACHE_SIZE

# Server request log (macOS only: it is what tools/sccache-watchdog reads and rotates).
# SCCACHE_LOG is filtered to the server/compiler modules, so clients print nothing extra
# into cargo's output. The directory must exist: the server dies at startup if it cannot
# open its error log.
if [ "$(uname -s)" = Darwin ]; then
  _sccache_state="${XDG_CACHE_HOME:-$HOME/.cache}/sccache-watchdog"
  [ -d "$_sccache_state" ] || mkdir -p "$_sccache_state"
  SCCACHE_ERROR_LOG="${SCCACHE_ERROR_LOG:-$_sccache_state/sccache-server.log}"
  SCCACHE_LOG="${SCCACHE_LOG:-sccache::server=debug,sccache::compiler=debug}"
  export SCCACHE_ERROR_LOG SCCACHE_LOG
  unset _sccache_state
fi
