# Source PATH management
[[ -f ~/.paths.zsh ]] && source ~/.paths.zsh

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
alias ta="tmux attach || tmux new-session -s default"
alias hxlog="hx $HOME/.cache/helix/helix.log"
alias reset-tmux='rm -rf ~/.local/share/tmux/resurrect'
alias zshrc='hx ~/.zshrc'
alias dots='cd ~/dotfiles/'
alias rsync='rsync -avz --compress --verbose --human-readable --partial --progress'
alias ga="lazygit"
alias bfs='bfs -L'
alias chals='alias | grep' #check aliases
alias npp='uv init . && uv add ipython joblib matplotlib numpy pandas pandas_flavor polars pyjanitor requests rich IProgress scikit_learn seaborn torch tqdm pandas numpy requests ipdb PyYAML ipykernel openai ollama git+https://github.com/vmasrani/machine_learning_helpers.git mysql-connector-python'
alias act='source .venv/bin/activate'




# bfs
alias bfs='bfs -L '


# Update the get_filtered_pids function to use the environment variable
get_filtered_pids() {
    pgrep -vfd, "$HTOP_FILTER"
}

alias ht='htop -t -u "$(whoami)" -p "$(get_filtered_pids)"'

alias archive-agent='/Users/vmasrani/dev/archive-agent/Archive-Agent/archive-agent.sh'
alias cc='claude'
alias ccc='claude --continue'
alias upd='update-packages'
alias updq='update-packages --quiet'


# uwu shorcut
alias ::='uwu-cli'
alias :::='uwu'

alias gpt='oai'

# codex() {
#   command codex --dangerously-bypass-approvals-and-sandbox --enable web_search_request -s workspace-write -c "sandbox_workspace_write.writable_roots=['/Users/my-user/.cache/uv']" "$@"
# }

export TABSTACK_API_KEY="23d0b47596440ff73e012c941e343dba6c861df78c5346047dfa340d7aa56877"
alias g='glow'
