#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""PreToolUse guard: refuse a heavy build/test command that was not sent to `queue`.

WHAT REPLACED WHAT (2026-08-03)
    This file replaces `test_queue_guard.py`, which REWROTE any matching command
    into `testq zsh -c '<cmd>'` behind the agent's back. Queueing is now explicit:
    you type `queue cargo nextest run`. All this hook does is notice when you
    forgot, and say so.

WHY A DENIER IS ALLOWED TO BE DUMB AND A REWRITER WAS NOT
    The old hook had to be exhaustive AND precise, because both directions of
    error were silent and expensive: a keyword it missed meant two suites
    colliding with no error anywhere, and a keyword it over-matched meant an
    innocent `rg -n 'cargo test' justfile` waiting behind a 5-minute suite.
    That is why it grew a weight-aware classifier that had to stay in sync with
    a second classifier inside testq.

    Denying inverts both costs. A miss just means you forgot the prefix -- the
    same as having no hook at all, which is where we started. An over-match
    costs one retype and shows its reasoning on screen. So the rule below is
    deliberately a short keyword table, and it is allowed to be imperfect.

WHY IT STILL TOKENIZES INSTEAD OF GREPPING THE RAW STRING
    Not for precision -- for free correctness. `utils/shell_tokens.py` already
    exists for `bash_footgun_guard.py` and already answers "is this word in
    command position", so `cd /repo && cargo test` and `RUST_LOG=1 cargo test`
    are handled in three lines rather than by a regex that would get them wrong.
    Nothing here would be simpler if it were a regex; it would only be wronger.

THE `&&` CASE IS THE WHOLE REASON THIS HOOK SURVIVED THE REWRITE
    A prefix cannot defend itself. The shell splits on `&&` before `queue` is
    ever exec'd, so in

        queue cd /repo && cargo test

    `queue` receives only `cd /repo`, queues that, exits -- and cargo runs
    unqueued at full tilt. `queue` is structurally blind to this: the operator
    never reaches it. This hook sees the raw command string, so it is the only
    place the mistake is detectable at all. Hence the two distinct denials
    below: "you queued nothing" and "you queued the wrong half".

FAILURE POSTURE
    Fails OPEN but never SILENTLY: an unexpected error exits 1 (non-blocking),
    surfacing a hook-error line rather than quietly denying everything. A bug
    here must never be able to block all work.
"""

import json
import re
import sys
from pathlib import Path

# resolve() matters: ~/.claude/hooks is a symlink into the dotfiles repo.
sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
from shell_tokens import command_heads, skip_env_assigns, tokenize  # noqa: E402

QUEUE_CMDS = {"queue", "testq"}

# ONLY things that must not overlap each other. This list is deliberately
# SHORTER than the old hook's, and the omissions are the entire point.
#
# `check`, `clippy`, `build` and `install` are absent ON PURPOSE. The old model
# had to let them overlap a suite -- that is what the whole 12-unit weighted
# budget existed to express, after a flat 2-slot queue made a `cargo check`
# someone was waiting on sit 9 minutes behind a suite instead of 30 seconds
# (see the TESTQ_SLOTS note this replaced). Under an explicit prefix that
# machinery is unnecessary rather than merely simplified: a command nobody is
# required to queue cannot suffer head-of-line blocking, because it never
# enters the queue at all. Deny only the jobs that genuinely saturate the box,
# and the latency win the weight table bought comes free.
#
# Metadata verbs (fmt, tree, add, metadata, update, search) are absent for the
# same reason, one step further out: nothing needs to classify them as cheap.
HEAVY_CARGO_VERBS = {"nextest", "test", "bench", "miri"}

# The CI contract every kitted project carries. `ci-fast` is the aggregate gate
# every agent runs before opening a PR; in a python project it fans out to a
# full pytest suite, so no cargo-shaped rule would ever catch it. `lint*` is
# omitted alongside `cargo clippy`, per the note above.
#
# `-release`-suffixed and `build-{linux,mac,windows}` recipes are ALSO heavy on
# purpose, despite the "build is cheap" rule above: those are full optimized
# workspace/cross-compile builds (`build-cartridge-release`, `test-release`,
# `build-linux`, ...), not the fast incremental `cargo build`/`cargo check`
# the exclusion was written for. Caught a `just build-cartridge-release` full
# release compile running unqueued on an already-oversubscribed box (2026-08-14).
JUST_HEAVY_RE = re.compile(
    r"\A(?:test|bench|ci-fast|ci-deep)[a-z0-9-]*\Z"
    r"|\A[a-z0-9-]*-release\Z"
    r"|\Abuild-(?:linux|mac|windows)\Z"
)


def _heavy_at(tokens, i):
    """Name the heavy command starting at index `i`, or None."""
    tok = tokens[i]
    if tok == "cargo":
        j = i + 1
        if j < len(tokens) and tokens[j].startswith("+"):  # +nightly toolchain selector
            j += 1
        if j < len(tokens) and tokens[j] in HEAVY_CARGO_VERBS:
            verb = tokens[j]
            rest = tokens[j + 1 :]
            # `cargo nextest` is only heavy when it actually RUNS tests. Every
            # other subcommand (--version, list, show-config, archive, self,
            # ...) is a read-only enumeration/introspection call and must stay
            # unqueued -- denying those trains agents to stop trusting the hook.
            if verb == "nextest":
                if rest and rest[0] in ("run", "r"):
                    return "cargo nextest run"
                return None
            # `cargo test --list` enumerates tests without running them --
            # the same no-run case as `cargo nextest list`.
            if verb == "test" and "--list" in rest:
                return None
            return f"cargo {verb}"
        # `cargo build`/`install` are cheap in debug but a full optimized
        # `--release` workspace build is exactly as heavy as a test suite.
        if j < len(tokens) and tokens[j] in ("build", "install") and "--release" in tokens[j + 1 :]:
            return f"cargo {tokens[j]} --release"
    if tok == "just" and i + 1 < len(tokens) and JUST_HEAVY_RE.match(tokens[i + 1]):
        return f"just {tokens[i + 1]}"
    return None


def inspect(command):
    """Return (offender, any_segment_queued), where offender is None if fine."""
    try:
        tokens = tokenize(command)
    except ValueError:
        return None, False  # unbalanced quotes: not a runnable command, leave it alone
    offender = None
    queued_somewhere = False
    for _sep, head in command_heads(tokens):
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens):
            continue
        if tokens[i] in QUEUE_CMDS:
            queued_somewhere = True
            continue
        offender = offender or _heavy_at(tokens, i)
    return offender, queued_somewhere


# Strip the misplaced prefix (and any env assignments before it) so the
# suggested fix is copy-pasteable. Without this the message reads
# `queue 'queue cd /repo && cargo test'` and has to apologise for itself.
_LEADING_QUEUE_RE = re.compile(r"\A(\s*(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*)(?:queue|testq)\s+")


def reason(command, offender, queued_somewhere):
    if queued_somewhere:
        inner = _LEADING_QUEUE_RE.sub(r"\1", command.strip())[:200]
        return (
            f"`{offender}` runs OUTSIDE the queue here. The shell splits on the operator "
            f"before `queue` is exec'd, so `queue` only received the first segment and "
            f"`{offender}` runs unqueued at full tilt.\n\n"
            f"Pass the whole thing as one quoted string instead:\n"
            f"    queue '{inner}'"
        )
    return (
        f"`{offender}` is heavy and was not sent to the queue. Several of these at once "
        f"on this box thrash rather than finish -- memory is the cliff, not cores.\n\n"
        f"Run it as:\n"
        f"    queue {command.strip()[:200]}\n\n"
        f"`queue X` behaves exactly like `X` -- it waits for a free slot, then streams "
        f"live output and returns the command's own exit code. Check the queue with "
        f"`queue -l`. For long suites prefer run_in_background, since queue wait + suite "
        f"time can exceed the 10-minute tool cap."
    )


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    data = json.loads(raw)
    if data.get("tool_name") != "Bash":
        sys.exit(0)

    command = (data.get("tool_input") or {}).get("command") or ""
    if not command:
        sys.exit(0)

    offender, queued_somewhere = inspect(command)
    if not offender:
        sys.exit(0)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason(command, offender, queued_somewhere),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open, but visibly -- exit 1 is non-blocking
        print(f"unqueued_heavy_guard: passing command through unchecked: {exc}", file=sys.stderr)
        sys.exit(1)
