# export WANDB_API_KEY="local-1cb84cdb8818ab552fb57da6b591af732d4ba09d"
# export WANDB_BASE_URL="http://localhost:8080"
export PYTHONPATH=~/.python:~/.roma-scripts:$PYTHONPATH
export PATH=~/.local/bin:$PATH
export PATH="$HOME/.npm-global/bin:$PATH"
export PATH=$PATH:/home/vaden/go/bin:/usr/local/go/bin
export BAT_THEME="Solarized (light)"


# REMOVE DUPLICATES
export PATH=$(echo -n $PATH | awk -v RS=: -v ORS=: '!seen[$0]++' | sed 's/:$//')

alias vscode='cursor'

alias DT='tee ~/Desktop/terminalOut.txt'    # DT:           Pipe content to file on MacOS Desktop

alias mysql_start='sudo /usr/local/mysql/support-files/mysql.server start'
alias mysql_stop='sudo /usr/local/mysql/support-files/mysql.server stop'
alias mysql_shell='mysql -u root -p -h localhost'

#postgres
alias pg_start="launchctl load ~/Library/LaunchAgents/homebrew.mxcl.postgresql.plist"
alias pg_stop="launchctl unload ~/Library/LaunchAgents/homebrew.mxcl.postgresql.plist"

alias less='less -M -X -g -i -J --underline-special --SILENT'

# Config
alias config='/usr/bin/git --git-dir=$HOME/.myconf/ --work-tree=$HOME'


alias l='eza -aHl --icons --git'
alias lt='eza -aHl --icons --git --sort=modified'
alias lf='eza -aHl --icons --git --sort=size --total-size'
alias ld='eza -aHlD --icons --git'

#cd alias'#
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
alias t='eza -aHl --icons --tree --no-user --no-permissions'
alias t2='eza -aHl --icons --tree --no-user --no-permissions -L 2'
alias t3='eza -aHl --icons --tree --no-user --no-permissions -L 3'
alias t4='eza -aHl --icons --tree --no-user --no-permissions -L 4'

#Preferred implementations
alias mv='mv -iv'                           # Preferred 'mv' implementation
alias mkdir='mkdir -pv'                     # Preferred 'mkdir' implementation
alias ll='ls -FGlAhp'                       # Preferred 'ls' implementation
alias less='less -FSRXc'                    # Preferred 'less' implementation
alias rm='rm -v'                            # Show what has been removed
alias cp='cp -v'                            # Show what has been copied
alias fr='open -a Finder ./'                # fr:            Opens current directory in MacOS Finder
alias ~="cd ~"                              # ~:            Go Home
alias h="history"                           # h:            History
alias path='echo -e ${PATH//:/\\n}'         # path:         Echo all executable Paths
alias fix_stty='stty sane'                  # fix_stty:     Restore terminal settings when screwed up
alias cic='set completion-ignore-case On'   # cic:          Make tab-completion case-insensitive
alias fd='fd -HI'                           # fd all
alias rg='rg --no-ignore'
alias bat='bat -n --color=always'
alias du='du -sh'

alias mmv='noglob zmv -W'
alias refresh='source ~/.zshrc'
alias ta="tmux attach"
alias brew="arch -x86_64 /usr/local/bin/brew"
alias hxlog="hx /home/vadmas/.cache/helix/helix.log"
alias reset-tmux='rm -rf ~/.local/share/tmux/resurrect'
alias zshrc='hx ~/.zshrc'
alias alsenvs='hx ~/.aliases-and-envs.zsh'
alias dots='hx ~/dotfiles/'
alias hxconf='hx ~/dotfiles/hx_config.toml'

# fzf

if [ -d "$HOME/.cursor-server" ]; then
  export CURSOR_FOLDER=".cursor-server"
else
  export CURSOR_FOLDER=".cursor"
fi

export EXTENSION_PATH=$(find ~/.cursor-server/extensions  -type d -name 'tomrijndorp*')
export GOPROXY=proxy.golang.org
alias ga="lazygit"

# bfs
alias bfs='bfs -L '

move_and_symlink() {
    local source="$1"
    local dest="$2"

    if [ -e "$source" ]; then
        local source_dir="$(dirname "$source")"
        local source_name="$(basename "$source")"

        mkdir -p "$dest"
        mv "$source" "$dest/"
        ln -si "$dest/$source_name" "$source_dir"
    else
        echo "Error: $source does not exist"
        return 1
    fi
}
