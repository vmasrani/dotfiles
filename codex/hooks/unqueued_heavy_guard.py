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
import shlex
import subprocess
import sys
from pathlib import Path

# resolve() matters: ~/.codex/hooks is a symlink into the dotfiles repo.
sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
from shell_tokens import command_heads, skip_env_assigns, tokenize  # noqa: E402

QUEUE_CMDS = {"queue", "testq"}

# THE RULE (2026-10-01): every compile and every test run holds a queue slot.
#
# Why: the 4 TB external volume stalls under builds that bypass the queue. With
# ~23 concurrent compilers/linkers from three epics, a small file create+unlink
# there took a 451 ms median (max 3 s); with the builds drained it was a 2 ms
# median. Builds ran outside the queue because the old rule (2026-08-14) said
# compiles idled an 18-core Mac while ~10 jobs waited. The express pool answers
# that: a command that keeps finishing in under 30 s auto-joins a separate
# 2-slot pool, so a quick incremental `cargo check` never waits behind a suite
# -- which is also the old "check waits behind a suite" concern, solved without
# leaving builds unqueued.
#
# Two KINDS, because the pre-dev integration guard below only forbids workers
# from running TESTS/GATES off the integration branch -- workers still build on
# their own branches (queued):
#   "build" -- compiles, runs nothing: cargo build|check|clippy|install|doc|
#              rustc|run, `cargo test|nextest run --no-run`, `cargo test --list`,
#              `cargo nextest list|archive` (these compile the test binaries),
#              maturin build|develop, and the build-shaped just recipes.
#   "test"  -- runs tests or benchmarks: cargo test|bench|miri, `cargo nextest
#              run`, and just test*/bench*/ci-fast*/ci-deep*.
#
# NOT heavy (no compile, no test run): cargo fmt|metadata|tree|update|add|
# search|--version, `cargo nextest --version|show-config|self`.
CARGO_BUILD_VERBS = {"build", "check", "clippy", "install", "doc", "rustc", "run"}
CARGO_TEST_VERBS = {"test", "bench", "miri"}
# cargo's built-in short aliases (b, c, d, r, t) resolve to the verbs above.
CARGO_ALIASES = {"b": "build", "c": "check", "d": "doc", "r": "run", "t": "test"}
NEXTEST_BUILD_VERBS = {"list", "archive"}
MATURIN_BUILD_VERBS = {"build", "develop"}

# The CI contract every kitted project carries. `ci-fast` is the aggregate gate
# every agent runs before opening a PR; in a python project it fans out to a
# full pytest suite, so no cargo-shaped rule would ever catch it.
JUST_TEST_RE = re.compile(r"\A(?:test|bench|ci-fast|ci-deep)[a-z0-9-]*\Z")
JUST_BUILD_RE = re.compile(
    r"\A(?:(?:build|install|lint|check|clippy|fastdev)[a-z0-9-]*|[a-z0-9-]*-release)\Z"
)

ALL_KINDS = ("build", "test")


def _classify_cargo(tokens, i):
    """(label, kind) for the `cargo` at index `i`, or None."""
    j = i + 1
    if j < len(tokens) and tokens[j].startswith("+"):  # +nightly toolchain selector
        j += 1
    if j >= len(tokens):
        return None
    verb = CARGO_ALIASES.get(tokens[j], tokens[j])
    rest = tokens[j + 1 :]
    if verb in CARGO_BUILD_VERBS:
        return f"cargo {verb}", "build"
    if verb == "nextest":
        if not rest:
            return None
        sub = rest[0]
        if sub in ("run", "r"):
            # `--no-run` only compiles the test binaries.
            return ("cargo nextest run --no-run", "build") if "--no-run" in rest else ("cargo nextest run", "test")
        if sub in NEXTEST_BUILD_VERBS:
            return f"cargo nextest {sub}", "build"
        return None  # --version, show-config, self, ...: no compile
    if verb in CARGO_TEST_VERBS:
        # `cargo test --no-run|--list` still compiles the test binaries but runs no tests.
        if verb == "test" and ("--no-run" in rest or "--list" in rest):
            return "cargo test --no-run", "build"
        return f"cargo {verb}", "test"
    return None


def _classify_at(tokens, i):
    """(label, kind) of the heavy command starting at index `i`, or None."""
    tok = tokens[i]
    if tok == "cargo":
        return _classify_cargo(tokens, i)
    if tok == "maturin" and i + 1 < len(tokens) and tokens[i + 1] in MATURIN_BUILD_VERBS:
        return f"maturin {tokens[i + 1]}", "build"
    if tok == "just" and i + 1 < len(tokens):
        recipe = tokens[i + 1]
        if JUST_TEST_RE.match(recipe):
            return f"just {recipe}", "test"
        if JUST_BUILD_RE.match(recipe):
            return f"just {recipe}", "build"
    return None


def _heavy_at(tokens, i, kinds=ALL_KINDS):
    """Name the heavy command of one of `kinds` starting at index `i`, or None."""
    hit = _classify_at(tokens, i)
    return hit[0] if hit and hit[1] in kinds else None


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


def _heavy_ignoring_queue(tokens):
    """Like inspect(), but treats a `queue`/`testq` prefix as transparent and
    counts only TEST/GATE commands (kind "test"), never builds.

    Used only by the pre-dev concurrent-work guard below, where even a
    correctly queued test/gate must be denied off the `pre-dev` branch --
    the queue's job is scheduling, not exemption from "workers never run
    gates". Workers still build on their own branches (queued), so builds are
    deliberately invisible here.
    """
    for _sep, head in command_heads(tokens):
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens):
            continue
        if tokens[i] in QUEUE_CMDS:
            i = skip_env_assigns(tokens, i + 1)
            if i >= len(tokens):
                continue
        offender = _heavy_at(tokens, i, kinds=("test",))
        if offender:
            return offender
    return None


def _git(cwd, *args, timeout=5):
    """`git -C cwd <args>` stdout, or None on any failure -- no git, no repo,
    and a missing ref are all a legitimate absence, not something to raise."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


_PRE_DEV_RE = re.compile(r"pre-dev\d*")


def _pre_dev_branches(cwd):
    """Local branches matching `^pre-dev[0-9]*$` -- AGENTS.md's numbered
    concurrent-wave integration branches (`pre-dev`, `pre-dev2`, `pre-dev3`,
    ...), each with the same rules. Empty when there are none, no git, or not
    a repo -- a legitimate absence, not something to raise (fail open)."""
    out = _git(cwd, "for-each-ref", "--format=%(refname:short)", "refs/heads/")
    if out is None:
        return []
    return sorted(name for name in out.splitlines() if _PRE_DEV_RE.fullmatch(name))


def pre_dev_offender(tokens, cwd):
    """Concurrent work = pre-dev integration (AGENTS.md): while any local
    branch matching `^pre-dev[0-9]*$` exists, heavy gates run ONCE, from that
    integration branch itself, by the orchestrator -- a worker's own `queue`
    prefix is not an exemption. Returns (offending command name, the
    integration branches that exist), or None when the rule does not apply
    here (no cwd, no git, not a repo, no such branch, or already on one)."""
    if not cwd:
        return None
    branches = _pre_dev_branches(cwd)
    if not branches:
        return None
    branch = _git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch is None or _PRE_DEV_RE.fullmatch(branch):
        return None
    offender = _heavy_ignoring_queue(tokens)
    return (offender, branches) if offender else None


def reason_pre_dev(offender, branches):
    names = ", ".join(branches)
    return (
        f"pre-dev integration is active ({names}): workers never run gates. `{offender}` is "
        f"denied here even though it looks queued -- `queue` schedules, it does not exempt.\n\n"
        f"Merge into the integration branch and let the orchestrator run the single "
        f"`{offender}` from its worktree -- never from a worker branch. Concurrent waves may "
        f"be numbered (pre-dev, pre-dev2, ...), each with the same rules. See AGENTS.md: "
        f'"Concurrent work = pre-dev integration".'
    )


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
        f"`{offender}` compiles or runs tests and was not sent to the queue. Many of these at "
        f"once starve the box (and the external volume's file I/O) rather than finish.\n\n"
        f"Run it as:\n"
        f"    queue {shlex.quote(command.strip()[:200])}\n\n"
        f"`queue X` behaves exactly like `X` -- it waits for a free slot, then streams "
        f"live output and returns the command's own exit code. Check the queue with "
        f"`queue -l`. Run long suites as background jobs so queue wait plus suite "
        f"time does not block an interactive tool call."
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

    # Concurrent-work guard runs even when the command above came back clean
    # because it was correctly queued -- pre-dev's "workers never run gates"
    # is not something a queue prefix can opt out of.
    try:
        tokens = tokenize(command)
    except ValueError:
        tokens = None
    if tokens is not None:
        pd_result = pre_dev_offender(tokens, data.get("cwd"))
        if pd_result:
            pd_offender, pd_branches = pd_result
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "PreToolUse",
                            "permissionDecision": "deny",
                            "permissionDecisionReason": reason_pre_dev(pd_offender, pd_branches),
                        }
                    }
                )
            )
            sys.exit(0)

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
