# ~/.bashrc — minimal, portable, snapshot-friendly.
#
# Most interactive work happens in zsh. This file exists so that:
#   1. Non-interactive bash (Claude Code's snapshot, scripts) gets PATH + env fast
#   2. Interactive bash is still usable as a fallback
#
# Keep this file SMALL. Anything heavy (nvm.sh, conda init, completions) goes
# below the interactivity guard, lazy-loaded so non-interactive bash never pays
# the cost. Sourcing nvm.sh in particular is what kills Claude's 10s snapshot
# budget, hence the early return + lazy stub.

# ---------------------------------------------------------------------------
# PATH (kept in sync with ~/.paths.zsh)
# ---------------------------------------------------------------------------
PATH_ADDITIONS=(
    "$HOME/.local/bin"
    "$HOME/bin"
    "$HOME/tools"
    "$HOME/.claude"
    "$HOME/.bun/bin"
    "$HOME/.npm-global/bin"
    "$HOME/go/bin"
    "/usr/local/go/bin"
    "$HOME/.cargo/bin"
    "/opt/homebrew/sbin"
    "/opt/homebrew/bin"
)
for d in "${PATH_ADDITIONS[@]}"; do
    [[ -d "$d" && ":$PATH:" != *":$d:"* ]] && PATH="$d:$PATH"
done

# Add latest nvm-installed Node bin without sourcing nvm.sh (which is slow).
# Loops without forking; takes the last entry, which on a normal install is
# the most recently created version directory.
if [[ -d "$HOME/.nvm/versions/node" ]]; then
    _node_bin=""
    for d in "$HOME"/.nvm/versions/node/*/bin; do
        [[ -d "$d" ]] && _node_bin="$d"
    done
    [[ -n "$_node_bin" ]] && PATH="$_node_bin:$PATH"
    unset _node_bin
fi

export PATH

# ---------------------------------------------------------------------------
# Env vars (safe for non-interactive shells)
# ---------------------------------------------------------------------------
export EDITOR="hx"
export BAT_THEME="Solarized (light)"

# ---------------------------------------------------------------------------
# Bail out for non-interactive shells.
# Claude Code's `bash -c -l` lands here and returns immediately with a
# fully-populated PATH, no snapshot timeout.
# ---------------------------------------------------------------------------
case $- in
    *i*) ;;
    *)   return 0 ;;
esac

# ---------------------------------------------------------------------------
# Interactive-only below this line
# ---------------------------------------------------------------------------

# Lazy-load nvm: first call to `nvm` sources nvm.sh and re-invokes itself.
# Avoids the ~1–3s startup cost on every interactive bash launch.
nvm() {
    unset -f nvm
    export NVM_DIR="$HOME/.nvm"
    [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
    nvm "$@"
}

# fzf keybindings if installed
[ -f ~/.fzf.bash ] && source ~/.fzf.bash

# Plain prompt (you live in zsh; this is just for bash fallback sessions)
PS1='\u@\h:\w\$ '
