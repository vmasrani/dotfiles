#!/usr/bin/env bash

# Switch between Ripgrep mode and fzf filtering mode (CTRL-T)
rm -f /tmp/rg-fzf-{r,f}
RG_PREFIX="rg --column --line-number --no-heading --color=always --smart-case --no-ignore-vcs  --hidden "
INITIAL_QUERY="${*:-}"
: | fzf --tmux 95% --ansi --disabled --query "$INITIAL_QUERY" \
	--bind "start:reload:$RG_PREFIX {q}" \
	--bind "change:reload:sleep 0.1; $RG_PREFIX {q} || true" \
	--bind 'ctrl-t:transform:[[ ! $FZF_PROMPT =~ ripgrep ]] &&
      echo "rebind(change)+change-prompt(1. ripgrep> )+disable-search+transform-query:echo \{q} > /tmp/rg-fzf-f; cat /tmp/rg-fzf-r" ||
      echo "unbind(change)+change-prompt(2. fzf> )+enable-search+transform-query:echo \{q} > /tmp/rg-fzf-r; cat /tmp/rg-fzf-f"' \
	--color "hl:-1:underline,hl+:-1:underline:reverse" \
	--prompt '1. ripgrep> ' \
	--delimiter : \
	--header 'CTRL-T: Switch between ripgrep/fzf' \
	--preview 'bat --color=always {1} --highlight-line {2}' \
	--bind 'enter:become(hx {1} +{2})' \
	--bind 'result:' \
    --bind 'focus:' \
    --bind 'focus:+transform-preview-label:' \
    --bind 'focus:+transform-header:' \


