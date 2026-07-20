# Source PATH management
[[ -f ~/.paths.zsh ]] && source ~/.paths.zsh

# ===================================================================
# SHELL OPTIONS
# ===================================================================
# Re-enable `>` overwriting existing files. Prezto's directory module
# (~/.zprezto/modules/directory/init.zsh:21) does `unsetopt CLOBBER`,
# which makes a plain `cmd > existing_file` fail with "file exists"
# instead of truncating. That is a genuine footgun for scripted and
# agent-driven work: the redirect fails, the surrounding command often
# still reports success, and you get a silent no-op that looks like it
# ran. (Cost a real debugging cycle: a `git show HEAD:file > file`
# meant to stage a revert silently did nothing, and the test run that
# followed "passed" while proving nothing.)
#
# This file is sourced from ~/.zshrc AFTER the prezto init, so setting
# it here wins. Prezto itself is a vendored submodule — do not patch it
# directly; the change would be lost on update.
#
# Use `>!` if you ever want the guarded behaviour for a single command.
setopt CLOBBER

# ===================================================================
# APPLICATION ALIASES
# ===================================================================
alias vscode='cursor'
alias config='/usr/bin/git --git-dir=$HOME/.myconf/ --work-tree=$HOME'

# ===================================================================
# UTILITY ALIASES
# ===================================================================
alias DT='tee ~/Desktop/terminalOut.txt'    # Pipe content to file on MacOS Desktop
alias less='less -M -X -g -i -J --underline-special --SILENT'


# ===================================================================
# FILE LISTING ALIASES (EZA)
# ===================================================================
alias L='eza -aHl --icons --grid --time-style relative --group-directories-first'
alias l='eza -aHl --icons --time-style relative --group-directories-first'
alias lt='eza -aHl --icons --sort=modified --time-style relative --group-directories-first'
alias lf='eza -aHl --icons --sort=size --total-size --time-style relative --group-directories-first'
alias ld='eza -aHlD --icons --time-style relative --group-directories-first'



alias p='fzf-preview'

# ===================================================================
# NAVIGATION ALIASES
# ===================================================================
alias cd..='cd ../'                         # Go back 1 directory level (for fast typers)
alias ..='cd ../'                           # Go back 1 directory level
alias .1='cd ../'                           # Go back 1 directory level
alias .2='cd ../../'                        # Go back 2 directory levels
alias .3='cd ../../../'                     # Go back 3 directory levels
alias .4='cd ../../../../'                  # Go back 4 directory levels
alias .5='cd ../../../../../'               # Go back 5 directory levels
alias .6='cd ../../../../../../'            # Go back 6 directory levels
alias .7='cd ../../../../../../../'         # Go back 7 directory levels
alias .8='cd ../../../../../../../../'      # Go back 8 directory levels
alias .9='cd ../../../../../../../../../'   # Go back 9 directory levels

#tree alias's"
export EZA_TREE_IGNORE='.venv|.git|.mypy_cache|__pycache__|.pytest_cache|node_modules'

alias t='eza -aHl --icons --tree --no-user --no-permissions -I "$EZA_TREE_IGNORE"'
alias t1='eza -aHl --icons --tree --no-user --no-permissions -L 1 -I "$EZA_TREE_IGNORE"'
alias t2='eza -aHl --icons --tree --no-user --no-permissions -L 2 -I "$EZA_TREE_IGNORE"'
alias t3='eza -aHl --icons --tree --no-user --no-permissions -L 3 -I "$EZA_TREE_IGNORE"'
alias t4='eza -aHl --icons --tree --no-user --no-permissions -L 4 -I "$EZA_TREE_IGNORE"'

#Preferred implementations
alias mv='mv -iv'                           # Preferred 'mv' implementation
alias mkdir='mkdir -pv'                     # Preferred 'mkdir' implementation
alias ll='ls -FGlAhp'                       # Preferred 'ls' implementation
alias less='less -FSRXc -M -g -i -J --underline-special --SILENT'
alias rm='rm -v'                            # Show what has been removed
alias cp='cp -v'                            # Show what has been copied
alias ~="cd ~"                              # ~:            Go Home
alias path='echo -e ${PATH//:/\\n}'         # path:         Echo all executable Paths
alias fix_stty='stty sane'                  # fix_stty:     Restore terminal settings when screwed up
alias cic='set completion-ignore-case On'   # cic:          Make tab-completion case-insensitive
alias fd='fd -HI'                           # fd all
alias rg='rg --no-ignore'
alias bat='bat -n --color=always'
alias du='du -sh'

# alias mmv='noglob zmv -W'
alias refresh='source ~/.zshrc'
alias ta="tmux attach-session -t default || tmux new-session -s default"
alias hxlog="hx $HOME/.cache/helix/helix.log"
alias reset-tmux='rm -rf ~/.local/share/tmux/resurrect'
alias zshrc='hx ~/.zshrc'
alias dots='cd ~/dotfiles/'
alias rsync='rsync -avz --compress --verbose --human-readable --partial --progress'

# Switch iTerm2 profile on SSH to Mac Mini, revert on disconnect
ssh() {
    local mac_mini="vadens-mac-mini"
    if [[ "$*" == *"$mac_mini"* ]]; then
        echo -ne "\033]1337;SetProfile=SSH-Server\007"
    fi
    command ssh "$@"
    echo -ne "\033]1337;SetProfile=Default\007"
}
alias ga="lazygit"
alias bfs='bfs -L'
alias chals='alias | grep' #check aliases
alias npp='uv init . && uv add ipython joblib matplotlib numpy pandas pandas_flavor polars pyjanitor requests rich IProgress scikit_learn seaborn torch tqdm pandas numpy requests ipdb PyYAML ipykernel openai ollama git+https://github.com/vmasrani/machine_learning_helpers.git mysql-connector-python'
alias act='source .venv/bin/activate'


fixmouse() {
    # Order matters per xterm/iTerm2 spec:
    #   DISABLE: tracking modes first (1000/1002/1003/1004), then encoding (1015/1006)
    #   ENABLE:  encoding first (1006), then tracking (1000/1002)
    # Modes: 1000=basic 1002=button-motion 1003=any-motion 1004=focus
    #        1005=utf-8 (legacy) 1006=SGR 1015=urxvt (legacy)
    local off='\e[?1000l\e[?1002l\e[?1003l\e[?1004l\e[?1005l\e[?1015l\e[?1006l'

    if [ -n "$TMUX" ]; then
        # 1. Reset iTerm2 directly via DCS passthrough — clears modes the dying
        #    app set on the outer terminal (esp. 1003 + 1004).
        printf '\ePtmux;\e\e[?1000l\e\e[?1002l\e\e[?1003l\e\e[?1004l\e\e[?1005l\e\e[?1015l\e\e[?1006l\e\\'

        # 2. Clear tmux's per-pane inner-state tracking.
        printf "$off"

        # 3. Drain queued mouse bytes on stdin so the next prompt doesn't read them.
        while read -t 0 -k 1 -s 2>/dev/null; do :; done

        # 4. Re-establish tmux's mouse mode (emits spec-ordered DECSET to iTerm2).
        tmux set -g mouse off
        tmux set -g mouse on
    else
        printf "$off"
        while read -t 0 -k 1 -s 2>/dev/null; do :; done
    fi
}


# bfs
alias bfs='bfs -L '


# Update the get_filtered_pids function to use the environment variable
get_filtered_pids() {
    pgrep -vfd, "$HTOP_FILTER"
}

alias ht='htop -t -u "$(whoami)" -p "$(get_filtered_pids)"'

alias cc='claude'
alias ccc='claude --continue'
alias ccd='claude --dangerously-skip-permissions'
alias upd='update-packages'
alias updq='update-packages --quiet'

# neomutt email client
alias mutt='neomutt -F ~/.config/mutt/muttrc'
export ESCDELAY=0  # Required for responsive neomutt keybindings
export NOTMUCH_CONFIG="$HOME/.config/notmuch/notmuchrc"
export NODE_OPTIONS="--dns-result-order=ipv4first"
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
export CLAUDE_CODE_NO_FLICKER=1

# ── sccache (shared compiler cache) ────────────────────────────────────
# `rustc-wrapper = sccache` is set in ~/.cargo/config.toml. Two settings
# make it actually earn its keep:
#
# 1. Cache on the external 2 TB SSD, not the 228 GB internal. Rust
#    artifacts are big and the dev trees live on this volume anyway, so
#    if it's unmounted nothing builds regardless.
# 2. 1 GiB (the old launchctl value) was 100% FULL and thrashing —
#    evicting entries faster than they could be reused. Measured Rust
#    hit rate at 1 GiB: 1.39%.
export SCCACHE_DIR=/Volumes/external/sccache
export SCCACHE_CACHE_SIZE=100G
# export CARGO_INCREMENTAL=0

# CARGO_INCREMENTAL is deliberately NOT exported here. The tradeoff:
#
#   sccache CANNOT cache incremental compilations — it silently skips
#   them. Cargo's dev/test profile turns `-C incremental` ON by default,
#   which is why 3495 of ~4456 calls were rejected with reason
#   "incremental": the cache did nothing for Rust no matter how large it
#   was. So CARGO_INCREMENTAL=0 is what makes sccache work at all.
#
#   BUT incremental is the right default for THIS shell — one dev, one
#   tree, editing one file and rebuilding. Incremental reuses per-function
#   codegen units and beats a cache lookup on that loop. Setting 0 here
#   would tax every interactive rebuild to benefit runs that don't happen
#   in this shell.
#
# So it is scoped to CI, worktrees, and parallel agents that each need
# their own CARGO_TARGET_DIR (cargo takes an EXCLUSIVE lock on target/,
# so concurrent builds sharing one dir serialize). `cargo-slot`
# (~/dotfiles/tools/cargo-slot) sets both CARGO_TARGET_DIR and
# CARGO_INCREMENTAL=0 per slot — see `cargo-slot --help`.
#
# MEASURED, so we don't overclaim: with incremental off, a clean rebuild
# of the SAME target dir went 6/6 sccache hits, 3.77s -> 1.33s. The same
# code built into a DIFFERENT target dir got 0 hits, so sccache keys are
# path-specific. Practical upshot: sccache pays off on clean rebuilds,
# branch switches and CI within a tree; it does NOT let two slots share
# compile work. Each slot pays its own dependency build once.
#
# WHY it's path-specific (corrected 2026-07-20 — the earlier note here blamed
# "--out-dir/-L/--extern paths embedded in rustc's args", which is WRONG):
# sccache's generate_hash_key (src/compiler/rust.rs) explicitly STRIPS those
# path args and hashes their file CONTENTS instead. The actual culprit is
# further down the same function — it hashes the compile's `cwd` (comment in
# source: "this will wind up in the rlib"), plus CARGO_* env vars like
# CARGO_MANIFEST_DIR. Those differ per worktree, so the key differs.
# SCCACHE_BASEDIRS does NOT fix this: it covers only the C/C++ preprocessor
# path (upstream issue #2652); the Rust-side fix is still unmerged (PR #2678).
#
# RE-MEASURED 2026-07-20 on parot-core (573 crates, M4, warm sccache),
# full cold `cargo build` of the workspace:
#   incremental default (what this shell does)   71s
#   CARGO_INCREMENTAL=0, sccache live            58s
#   CARGO_INCREMENTAL=0 + APFS cp -c seeded dir  46s
# So the interactive default costs ~13s per COLD target dir — once per
# worktree, not once per edit. The hot single-file edit loop that motivated
# keeping incremental was NOT measured; that reasoning stands unchallenged.
# uwu shorcut
alias ::='uwu-cli'
alias :::='uwu'

alias gpt='oai'

# codex() {
#   command codex --dangerously-bypass-approvals-and-sandbox --enable web_search_request -s workspace-write -c "sandbox_workspace_write.writable_roots=['/Users/my-user/.cache/uv']" "$@"
# }

unalias gws 2>/dev/null  # free gws for googleworkspace-cli

autoload -Uz bracketed-paste-magic
zle -N bracketed-paste bracketed-paste-magic
alias m='mdterm'

function y() {
	local tmp="$(mktemp -t "yazi-cwd.XXXXXX")" cwd
	command yazi "$@" --cwd-file="$tmp"
	IFS= read -r -d '' cwd < "$tmp"
	[ "$cwd" != "$PWD" ] && [ -d "$cwd" ] && builtin cd -- "$cwd"
	command rm -f -- "$tmp"
}
