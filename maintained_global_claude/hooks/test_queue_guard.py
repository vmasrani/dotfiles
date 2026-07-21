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
from pathlib import Path

# Quote-aware tokenizing lives in utils/shell_tokens.py so this hook and
# bash_footgun_guard.py can never disagree about where a command begins.
# resolve() matters: ~/.claude/hooks is a symlink into the dotfiles repo.
sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
from shell_tokens import command_heads, skip_env_assigns, tokenize  # noqa: E402

# Heavy cargo verbs -- each one compiles and/or saturates cores.
# Deliberately EXCLUDED as trivial/metadata-only: fmt, metadata, tree, add,
# remove, update, search, login, --version. Those must stay instant.
HEAVY_CARGO_VERBS = {"nextest", "test", "build", "check", "clippy", "bench", "install", "miri"}
# Project recipes that fan out into the above: just test*, just bench-*, just lint*.
JUST_HEAVY_RE = re.compile(r"\A(?:test|bench|lint)[a-z0-9-]*\Z")


def _classify_head(tokens, head):
    """Return (is_heavy, already_queued) for the command beginning at `head`."""
    i = skip_env_assigns(tokens, head)
    # A cargo-slot <name> wrapper precedes the real cargo invocation.
    if i + 1 < len(tokens) and tokens[i] == "cargo-slot":
        i = skip_env_assigns(tokens, i + 2)
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
        tokens = tokenize(command)
    except ValueError:
        # Unbalanced quote etc. -- not a runnable heavy command; leave it alone.
        return False
    heavy = False
    for _op, head in command_heads(tokens):
        is_heavy, already_queued = _classify_head(tokens, head)
        if already_queued:
            return False
        heavy = heavy or is_heavy
    return heavy


def queued(command: str, session: str = "") -> str:
    """Wrap the whole command as a single queued job, quoting-safe.

    The session id is passed through as TESTQ_SESSION so the queue can tell
    whose jobs are whose. It uses that for two things a bare PID cannot support:
    `--last` resolves to the caller's OWN most recent job even while other
    agents submit concurrently, and scheduling can round-robin across sessions
    so one agent's fan-out cannot starve everyone else. Without it every tool
    call looks like a different submitter, because each one is a new shell.
    """
    prefix = f"TESTQ_SESSION={shlex.quote(session)} " if session else ""
    return f"{prefix}testq zsh -c {shlex.quote(command)}"


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
    new_input["command"] = queued(command, str(data.get("session_id") or ""))

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
