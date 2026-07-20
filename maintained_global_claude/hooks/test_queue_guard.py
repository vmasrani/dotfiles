#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""PreToolUse guard: route heavy Rust builds / test suites / benches through the global queue.

WHY
    Several agents running full suites at once on a 10-core / 16 GB box do not
    finish faster -- they thrash, and the memory cliff means some never finish
    at all. `testq` serializes them machine-wide. This hook exists so an agent
    cannot forget to use it: any matching command is rewritten in flight.

MECHANISM
    PreToolUse supports `updatedInput`, which replaces the tool input before
    execution. So `cargo nextest run --workspace` silently becomes
    `testq zsh -c 'cargo nextest run --workspace'`. The agent sees normal
    output and a normal exit code; it just waited its turn.

WHY ALWAYS `zsh -c` AND NEVER A BARE PREFIX
    Prefixing the string is prettier and silently WRONG for the two commonest
    agent shapes:
        cd /repo && cargo test        -> `testq cd /repo && cargo test`
                                         queues the `cd`, runs cargo unqueued
        RUST_LOG=debug cargo test     -> ts tries to exec a binary literally
                                         named "RUST_LOG=debug"
    Wrapping the whole command in one quoted `zsh -c` is correct for simple,
    compound, piped, redirected and env-prefixed commands alike. One path.

FAILURE POSTURE
    Fails OPEN but never SILENTLY: an unexpected error exits 1 (non-blocking),
    which surfaces a hook-error line in the transcript rather than quietly
    letting collisions resume. A hook bug must not brick the ability to run
    anything, but it must also not look like success.
"""

import json
import re
import shlex
import sys

# WHY TOKENIZE INSTEAD OF REGEX-OVER-THE-RAW-STRING
#     A regex cannot see shell quoting. An earlier version anchored on shell
#     operators (|, &&, ;) to find "command position", but those bytes also
#     appear INSIDE quoted arguments -- and there they are data, not operators:
#         rg -n "^test|nextest|cargo test" justfile
#     The `|cargo test` inside that rg pattern looked exactly like a piped
#     `cargo test` command, so a read-only grep got queued behind a 20-minute
#     suite. shlex parses quotes correctly: the whole pattern is ONE token and
#     its inner `|` is never mistaken for a pipe. We then match heavy verbs only
#     against tokens that genuinely start a command.

# Heavy cargo verbs -- each one compiles and/or saturates cores.
# Deliberately EXCLUDED as trivial/metadata-only: fmt, metadata, tree, add,
# remove, update, search, login, --version. Those must stay instant.
HEAVY_CARGO_VERBS = {"nextest", "test", "build", "check", "clippy", "bench", "install", "miri"}
# Project recipes that fan out into the above: just test*, just bench-*, just lint*.
JUST_HEAVY_RE = re.compile(r"\A(?:test|bench|lint)[a-z0-9-]*\Z")
# Env prefixes to skip: RUST_LOG=debug cargo test.
ENV_ASSIGN_RE = re.compile(r"\A[A-Za-z_][A-Za-z0-9_]*=")
# Shell control operators shlex emits as their own tokens under punctuation_chars.
_PUNCT = set(";&|()<>")


def _tokenize(command: str):
    """Split respecting quotes; keep shell operators as standalone tokens."""
    lex = shlex.shlex(command, posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    return list(lex)


def _is_operator(tok: str) -> bool:
    return tok != "" and all(c in _PUNCT for c in tok)


def _command_heads(tokens):
    """Yield the index of each token that starts a command (string start or
    immediately after a control operator)."""
    at_start = True
    for i, tok in enumerate(tokens):
        if _is_operator(tok):
            at_start = True
            continue
        if at_start:
            yield i
            at_start = False


def _classify_head(tokens, head):
    """Return (is_heavy, already_queued) for the command beginning at `head`."""
    i = head
    while i < len(tokens) and ENV_ASSIGN_RE.match(tokens[i]):
        i += 1
    # A cargo-slot <name> wrapper precedes the real cargo invocation.
    if i + 1 < len(tokens) and tokens[i] == "cargo-slot":
        i += 2
        while i < len(tokens) and ENV_ASSIGN_RE.match(tokens[i]):
            i += 1
    if i >= len(tokens):
        return False, False
    tok = tokens[i]
    if tok in ("testq", "ts"):
        return False, True  # already routed through the queue -- never double-wrap
    if tok == "cargo":
        j = i + 1
        if j < len(tokens) and tokens[j].startswith("+"):  # +nightly toolchain selector
            j += 1
        if j < len(tokens) and tokens[j] in HEAVY_CARGO_VERBS:
            return True, False
    if tok == "just":
        if i + 1 < len(tokens) and JUST_HEAVY_RE.match(tokens[i + 1]):
            return True, False
    return False, False


def needs_queue(command: str) -> bool:
    try:
        tokens = _tokenize(command)
    except ValueError:
        # Unbalanced quote etc. -- not a runnable heavy command; leave it alone.
        return False
    heavy = False
    for head in _command_heads(tokens):
        is_heavy, already_queued = _classify_head(tokens, head)
        if already_queued:
            return False
        heavy = heavy or is_heavy
    return heavy


def queued(command: str) -> str:
    """Wrap the whole command as a single queued job, quoting-safe."""
    return f"testq zsh -c {shlex.quote(command)}"


def main() -> None:
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)

    data = json.loads(raw)
    if data.get("tool_name") != "Bash":
        sys.exit(0)

    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command") or ""
    if not command or not needs_queue(command):
        sys.exit(0)

    # Replace the ENTIRE tool input (updatedInput is a replacement, not a patch),
    # preserving sibling fields like description / timeout / run_in_background.
    new_input = dict(tool_input)
    new_input["command"] = queued(command)

    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "allow",
                    "updatedInput": new_input,
                    "additionalContext": (
                        "This heavy build/test command was routed through `testq`, the "
                        "machine-wide job queue, so it cannot collide with suites started "
                        "by other agents. It runs one at a time in submission order; a "
                        "wait before output appears is expected, not a hang. Inspect the "
                        "queue with `testq -l`. For long suites prefer run_in_background, "
                        "since queue wait + suite time can exceed the 10-minute tool cap. "
                        "Do not add the prefix yourself -- it is applied automatically."
                    ),
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open, but visibly -- exit 1 is non-blocking
        print(f"test_queue_guard: passing command through unqueued: {exc}", file=sys.stderr)
        sys.exit(1)
