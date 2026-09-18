# Setup fzf
# ---------
# fzf ships as a prebuilt binary in ~/.local/bin (GitHub release); shell
# integration comes straight from `fzf --bash`.
command -v fzf >/dev/null && eval "$(fzf --bash)"
