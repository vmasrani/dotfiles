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

# Match only in COMMAND POSITION: start of string, or just after a shell
# operator. Without this anchor, `git commit -m "fix cargo test failure"`
# matches and a commit gets queued behind a 20-minute suite.
_LEAD = r"(?:\A|[\n;&|(]|&&|\|\|)\s*"
# Tolerate env prefixes (RUST_LOG=debug cargo test) and a cargo-slot wrapper.
_ENV = r"(?:[A-Za-z_][A-Za-z0-9_]*=\S*\s+)*"
_SLOT = r"(?:cargo-slot\s+\S+\s+)?"

# Heavy cargo verbs -- each one compiles and/or saturates cores.
# `+toolchain` is tolerated (cargo +nightly test).
# Deliberately EXCLUDED as trivial/metadata-only: fmt, metadata, tree, add,
# remove, update, search, login, --version. Those must stay instant.
CARGO_HEAVY = re.compile(
    _LEAD + _ENV + _SLOT
    + r"cargo\s+(?:\+\S+\s+)?(?:nextest|test|build|check|clippy|bench|install|miri)\b"
)

# Project recipes that fan out into the above: just test*, just bench-*, just lint.
JUST_HEAVY = re.compile(_LEAD + _ENV + r"just\s+(?:test|bench|lint)[a-z0-9-]*\b")

# Already routed through the queue -- never double-wrap.
ALREADY_QUEUED = re.compile(r"(?:^|[\s;&|(])(?:testq|ts\s+-\w*[nf])\b")


def needs_queue(command: str) -> bool:
    if ALREADY_QUEUED.search(command):
        return False
    return bool(CARGO_HEAVY.search(command) or JUST_HEAVY.search(command))


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
