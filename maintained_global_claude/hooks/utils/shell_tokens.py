"""Quote-aware shell tokenizing, shared by the PreToolUse Bash hooks.

WHY THIS IS A SHARED MODULE AND NOT COPY-PASTE
    Two hooks inspect the same Bash command for different reasons --
    `test_queue_guard.py` rewrites heavy builds, `bash_footgun_guard.py`
    blocks commands that fabricate evidence. If they disagreed about where a
    command *starts*, one of them would be wrong about every compound command.
    One parser, one answer.

WHY TOKENIZE INSTEAD OF REGEX-OVER-THE-RAW-STRING
    A regex cannot see shell quoting. Anchoring on shell operators (|, &&, ;)
    to find "command position" is wrong because those bytes also appear INSIDE
    quoted arguments -- and there they are data, not operators:

        rg -n "^test|nextest|cargo test" justfile

    The `|cargo test` inside that pattern looks exactly like a piped
    `cargo test`. shlex parses quotes correctly: the whole pattern is ONE token
    and its inner `|` is never mistaken for a pipe.

Stdlib only, and it must stay that way: these hooks run under
`/usr/bin/python3` on every single Bash tool call, so import cost is latency
the user pays for constantly.
"""

import re
import shlex

# Env prefixes that precede the real command: `RUST_LOG=debug cargo test`.
ENV_ASSIGN_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")

# Shell control operators shlex emits as their own tokens under punctuation_chars.
_PUNCT = set(";&|()<>")


def tokenize(command):
    """Split respecting quotes; keep shell operators as standalone tokens.

    Raises ValueError on unbalanced quotes -- callers treat that as "not a
    runnable command, leave it alone" rather than guessing.
    """
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def is_operator(tok):
    return tok != "" and all(c in _PUNCT for c in tok)


def is_redirection(tok):
    """True for >, >>, <, >&, &> ... -- operators that do NOT separate commands.

    This distinction is load-bearing, not pedantry. `cargo test 2>&1 | tail`
    tokenizes as [... '2', '>&', '1', '|', 'tail']. Treating `>&` as a separator
    makes the bare fd `1` look like a whole command, which in turn makes `tail`
    the *second* thing after the test run rather than the first -- so a rule
    asking "is this suite's output piped?" answers no, and the footgun it exists
    to catch walks straight through.
    """
    return is_operator(tok) and ("<" in tok or ">" in tok)


def command_heads(tokens):
    """Yield (preceding_separator, index) for each token that starts a command.

    `preceding_separator` is None for the first command in the string, else the
    operator that separated it from the previous one ("|", "&&", ";").
    Callers need it to tell `git commit && echo ok` (marker is conditional on
    success) from `git commit ; echo ok` (marker always prints -- footgun 1.3).

    Redirections are treated as part of the command they belong to, and their
    target token is consumed with them.
    """
    prev_sep = None
    at_start = True
    skip_target = False
    for i, tok in enumerate(tokens):
        if skip_target:
            skip_target = False
            continue
        if is_redirection(tok):
            skip_target = True  # the file/fd that follows belongs to this command
            continue
        if is_operator(tok):
            prev_sep = tok
            at_start = True
            continue
        if at_start:
            yield prev_sep, i
            at_start = False


def skip_env_assigns(tokens, head):
    """Return the index of the real command word at/after `head`.

    May return len(tokens) if the command is nothing but env assignments.
    """
    i = head
    while i < len(tokens) and ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    return i


def args_until_operator(tokens, start):
    """The argument tokens of one command: from `start` up to the next operator."""
    out = []
    for tok in tokens[start:]:
        if is_operator(tok):
            break
        out.append(tok)
    return out
