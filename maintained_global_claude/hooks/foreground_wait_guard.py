#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""PreToolUse guard: refuse a Bash command that BLOCKS ON A WAIT in the foreground.

WHY
    A foreground wait (load-gate `while ...; do sleep 30; done`, `flock`, a
    `queue` job waiting for a slot, `tail -f`) holds the whole agent turn until
    it exits -- agents have sat at the "ctrl+b ctrl+b to run in background"
    prompt for many minutes. The Bash tool's `run_in_background: true` runs the
    same command detached and re-invokes the agent when it exits, so the fix is
    always the same one-flag retry. A command already sent with
    `run_in_background: true` is never touched.

WHAT IS A WAIT (command position only, via utils/shell_tokens.py)
    - `flock` without -n/--nonblock/-w/--timeout/--wait
    - `queue`/`testq` unless its args are read-only (-l, --list, --status,
      --exit-code, --last, -h, --help, --ahead, --triage)
    - a `while`/`until` loop whose body runs `sleep` (a polling loop)
    - `sleep N` with N >= 30 s (or any m/h/d suffix that reaches 30 s)
    - `tail -f/-F`, `watch`, `gh run watch`, `inotifywait`
    Words that merely appear as arguments (`rg sleep f`, `echo flock`,
    `git log --grep=flock`) are not in command position and never match.

FAILURE POSTURE
    Fails OPEN but never SILENTLY: an unexpected error exits 1 (non-blocking).
    Only ever emits a deny; says nothing otherwise (never `allow`).
"""

import json
import re
import sys
from pathlib import Path

# resolve() matters: ~/.claude/hooks is a symlink into the dotfiles repo.
sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
from shell_tokens import args_until_operator, command_heads, skip_env_assigns, tokenize  # noqa: E402

QUEUE_CMDS = {"queue", "testq"}
QUEUE_READONLY = {"-l", "--list", "--exit-code", "--last", "-h", "--help", "--status", "--ahead", "--triage"}
FLOCK_NONBLOCKING_LONG = {"--nonblock", "--timeout", "--wait"}
FLOCK_VALUE_FLAGS = {"-w", "--timeout", "--wait", "-E", "--conflict-exit-code"}
LOOP_KEYWORDS = {"while", "until"}
# Shell keywords that precede a real command word inside a compound command.
PREFIX_KEYWORDS = {"do", "then", "else", "elif", "!", "time", "{"}
SLEEP_LIMIT_S = 30
_SLEEP_ARG_RE = re.compile(r"\A(\d+(?:\.\d+)?)([smhd]?)\Z")
_UNIT_S = {"": 1, "s": 1, "m": 60, "h": 3600, "d": 86400}


def _flock_blocks(args):
    """True unless flock's own options include a non-blocking / timeout flag."""
    k = 0
    while k < len(args) and args[k].startswith("-") and args[k] != "-":
        tok = args[k]
        if tok in FLOCK_NONBLOCKING_LONG or any(tok.startswith(f + "=") for f in FLOCK_NONBLOCKING_LONG):
            return False
        if not tok.startswith("--") and ("n" in tok[1:] or tok[1:].startswith("w") or "w" in tok[1:]):
            return False
        k += 2 if tok in FLOCK_VALUE_FLAGS else 1
    return True


def _sleep_seconds(args):
    """Total requested seconds, or None when an arg is not a plain duration."""
    total = 0.0
    for a in args:
        m = _SLEEP_ARG_RE.match(a)
        if not m:
            return None
        total += float(m.group(1)) * _UNIT_S[m.group(2)]
    return total if args else None


def _tail_follows(args):
    for a in args:
        if a == "--":
            return False
        if a.startswith("--follow") or (a.startswith("-") and not a.startswith("--") and re.search(r"[fF]", a)):
            return not re.fullmatch(r"-\d+", a)
    return False


def _real_word(tokens, head):
    """Index of the command word at `head`, skipping env assigns and `do`/`then`-style keywords."""
    i = skip_env_assigns(tokens, head)
    while i < len(tokens) and tokens[i] in PREFIX_KEYWORDS:
        i = skip_env_assigns(tokens, i + 1)
    return i


def _words(tokens):
    for _sep, head in command_heads(tokens):
        i = _real_word(tokens, head)
        if i < len(tokens):
            yield i, tokens[i]


def _wait_at(tokens, i):
    """Name the foreground wait starting at command word `i`, or None."""
    word, args = tokens[i], args_until_operator(tokens, i + 1)
    if word == "flock" and _flock_blocks(args):
        return "flock"
    if word in QUEUE_CMDS and args and args[0] not in QUEUE_READONLY:
        return word
    if word == "sleep":
        secs = _sleep_seconds(args)
        if secs is not None and secs >= SLEEP_LIMIT_S:
            return f"sleep {' '.join(args)}"
    if word == "tail" and _tail_follows(args):
        return "tail -f"
    if word in ("watch", "inotifywait"):
        return word
    if word == "gh" and args[:2] == ["run", "watch"]:
        return "gh run watch"
    return None


def inspect(command):
    """Name of the first foreground wait found in `command`, else None."""
    try:
        tokens = tokenize(command)
    except ValueError:
        return None  # unbalanced quotes: not a runnable command, leave it alone
    words = list(_words(tokens))
    if any(w in LOOP_KEYWORDS for _i, w in words) and any(w == "sleep" for _i, w in words):
        return "polling loop (while/until ... sleep)"
    for i, _w in words:
        wait = _wait_at(tokens, i)
        if wait:
            return wait
    return None


def reason(offender):
    return (
        f"Foreground wait: '{offender}' blocks this agent until it exits. "
        "Re-run with run_in_background: true; you'll be re-invoked when it finishes."
    )


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    data = json.loads(raw)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    tool_input = data.get("tool_input") or {}
    if tool_input.get("run_in_background") is True:
        sys.exit(0)
    command = tool_input.get("command") or ""
    offender = inspect(command) if command else None
    if not offender:
        sys.exit(0)
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason(offender),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open, but visibly -- exit 1 is non-blocking
        print(f"foreground_wait_guard: passing command through unchecked: {exc}", file=sys.stderr)
        sys.exit(1)
