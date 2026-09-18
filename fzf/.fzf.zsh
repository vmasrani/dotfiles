# Setup fzf
# ---------
# fzf ships as a prebuilt binary in ~/.local/bin (GitHub release); shell
# integration comes straight from `fzf --zsh`.
command -v fzf >/dev/null && source <(fzf --zsh)
