#!/usr/bin/env zsh
# fzf-history-delete.zsh — helper for the Ctrl-R history widget.
#
#   list            -> print the history file as fzf-history items
#                      (NUL-separated, "<n>\t<command>", parity with fzf's perl path)
#   delete <file>   -> <file> is fzf's {f} (the current item). Remove every
#                      logical entry in $HISTFILE whose command equals that
#                      item's command, then mark the session as dirty so the
#                      live shell can drop it from memory too.
#
# Safe to run repeatedly. Writes $HISTFILE atomically (tmp + rename).

emulate -L zsh
setopt no_unset pipefail

local action=$1; shift
local HF=${HISTFILE:-$HOME/.zsh_history}
local DIRTY=${TMPDIR:-/tmp}/.fzf_hist_dirty

case $action in
list)
    zmodload zsh/parameter 2>/dev/null
    HISTSIZE=10000000
    fc -R -- "$HF"
    printf '%s\t%s\000' "${(kv)history[@]}" |
        perl -0 -ne 'if (!$seen{(/^\s*[0-9]+\**\t(.*)/s, $1)}++) { s/\n/\n\t/g; print; }'
    ;;

delete)
    local itemfile=$1
    [[ -r $itemfile ]] || return 0
    perl -e '
        my ($hf, $itemfile) = @ARGV;
        # --- target command, recovered from fzf {f} ---
        open(my $IT, "<", $itemfile) or die "item: $!";
        local $/; my $target = <$IT>; close $IT;
        $target =~ s/^\s*[0-9]+\*?\t//;   # drop leading "<event-number>\t"
        $target =~ s/\n\t/\n/g;            # undo the perl wrap-indentation
        $target =~ s/\n\z//;               # one trailing newline, if any
        return unless length $target;

        # --- read history file, split into logical entries ---
        open(my $H, "<", $hf) or die "hist: $!";
        my $data = <$H>; close $H;
        my $trailing = ($data =~ /\n\z/) ? 1 : 0;
        my @phys = split(/\n/, $data, -1);
        pop @phys if @phys && $phys[-1] eq "";   # trailing newline artifact

        my (@keep, @buf);
        for my $i (0 .. $#phys) {
            push @buf, $phys[$i];
            my ($bs) = ($phys[$i] =~ /(\\*)\z/);          # trailing backslashes
            next if length($bs) % 2 == 1 && $i < $#phys;  # escaped newline -> continued
            my $raw = join("\n", @buf);
            my $cmd = $raw;
            $cmd =~ s/^:\s*\d+:\d+;//;   # strip EXTENDED_HISTORY metadata
            $cmd =~ s/\\\n/\n/g;          # unescape embedded newlines
            push @keep, $raw unless $cmd eq $target;
            @buf = ();
        }

        my $out = join("\n", @keep);
        $out .= "\n" if $trailing && length $out;

        my $tmp = "$hf.tmp.$$";
        open(my $W, ">", $tmp) or die "tmp: $!";
        print $W $out; close $W or die "close: $!";
        rename($tmp, $hf) or die "rename: $!";
    ' "$HF" "$itemfile" && : > "$DIRTY"
    ;;

*)
    print -u2 "usage: fzf-history-delete.zsh {list|delete <itemfile>}"
    return 2
    ;;
esac
