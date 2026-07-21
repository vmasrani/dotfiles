#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""PostToolUse: reconcile a test run's COUNT against the last run of the same command.

WHY
    The worst observed failure mode is a suite that reports a clean green while
    executing a binary that does not contain the new tests. It reported
    "742 tests run: 742 passed", no errors -- and a targeted run minutes later,
    same worktree, same file contents, failed deterministically. Nothing in the
    output was false. The summary was accurate about what it ran; it just
    wasn't running the new code.

    What caught it was arithmetic: after the fix the suite reported 751, and
    751 - 742 = 9 was exactly the number of tests added. That binary had
    contained none of them.

    A "N passed" line is easy to produce accidentally. A COUNT is not. So this
    hook keeps the baseline that made the catch possible, instead of relying on
    a human to hold it in their head across a long session.

SCOPE -- WHY IT KEYS ON THE EXACT COMMAND
    `-p parot-daemon -p parot-cli` and `--workspace` legitimately report wildly
    different totals. Comparing across them would emit a false alarm on every
    other run, and an alarm that cries wolf is worse than no alarm -- it trains
    the reader to skip it. So a baseline belongs to one exact command string in
    one repo. Identical counts stay SILENT; only a delta says anything.

    Consequence worth knowing: this cannot see a stale binary that reruns the
    identical set of tests (count unchanged). It catches the common shape --
    the count moved, or moved the wrong way -- not every shape.
"""

import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "state" / "testcounts"

# `Summary [   9.293s] 742 tests run: 739 passed, 3 failed, 3 skipped`
NEXTEST_RE = re.compile(r"(\d+) tests run:\s*(\d+) passed")
# `test result: ok. 742 passed; 0 failed; 3 ignored; ...` -- one per test binary.
CARGO_TEST_RE = re.compile(r"test result:.*?(\d+) passed;\s*(\d+) failed")


def unwrap(command):
    """Strip the `testq zsh -c '<real command>'` wrapper the queue guard adds,
    so a command keys the same whether or not it was routed through the queue."""
    parts = shlex.split(command)
    if len(parts) == 4 and parts[0] in ("testq", "ts") and parts[2] == "-c":
        return parts[3].strip()
    return command.strip()


def extract_counts(text):
    """(tests_run, passed) for the run, or None if this wasn't a test run."""
    nextest = NEXTEST_RE.search(text)
    if nextest:
        return int(nextest.group(1)), int(nextest.group(2))
    cargo = CARGO_TEST_RE.findall(text)
    if cargo:
        passed = sum(int(p) for p, _f in cargo)
        failed = sum(int(f) for _p, f in cargo)
        return passed + failed, passed
    return None


def state_path(repo):
    slug = re.sub(r"[^A-Za-z0-9]+", "-", Path(repo).name).strip("-") or "repo"
    digest = hashlib.sha1(str(repo).encode()).hexdigest()[:8]
    return STATE_DIR / f"{slug}-{digest}.json"


def load(path):
    return json.loads(path.read_text()) if path.exists() else {}


def git_out(cwd, *args):
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args], capture_output=True, text=True, timeout=5
    )
    return proc.stdout.strip() if proc.returncode == 0 else None


def reconcile(previous, tests_run, head):
    """The note to hand back, or None when there is nothing worth saying."""
    if previous is None:
        return (
            f"Test-count baseline recorded: {tests_run} tests for this exact command. "
            "Future runs of it will be reconciled against this number -- a count is hard "
            "to fake accidentally, a 'N passed' line is not."
        )
    before = previous["tests_run"]
    if before == tests_run:
        return None
    delta = tests_run - before
    lead = (
        f"TEST COUNT CHANGED: {before} -> {tests_run} ({delta:+d}) for this exact command"
    )
    if previous.get("head") and previous["head"] != head:
        lead += f" (HEAD {previous['head'][:8]} -> {(head or '?')[:8]})"
    lead += "."
    if delta < 0:
        return (
            lead
            + " The count went DOWN. Unless you deleted exactly that many tests, this is the "
            "signature of a binary that does not contain the current code -- the summary is "
            "accurate about what it ran, it just isn't running your changes. Do NOT treat "
            "this as green: confirm the arithmetic, and if it doesn't reconcile, force a "
            "rebuild (touch the changed file / `cargo clean -p <crate>`) and re-run."
        )
    return (
        lead
        + " Confirm this matches the number of tests you actually added; if the delta is "
        "smaller than expected, some new tests are not in the binary that ran."
    )


def main():
    raw = sys.stdin.read()
    if not raw.strip():
        sys.exit(0)
    data = json.loads(raw)
    if data.get("tool_name") != "Bash":
        sys.exit(0)

    response = data.get("tool_response")
    if isinstance(response, dict):
        if response.get("interrupted"):
            sys.exit(0)
        text = f"{response.get('stdout', '')}\n{response.get('stderr', '')}"
    else:
        text = str(response or "")

    counts = extract_counts(text)
    if counts is None:
        sys.exit(0)
    tests_run, passed = counts

    cwd = data.get("cwd") or str(Path.cwd())
    repo = git_out(cwd, "rev-parse", "--show-toplevel") or cwd
    head = git_out(cwd, "rev-parse", "HEAD")

    command = unwrap((data.get("tool_input") or {}).get("command") or "")
    key = hashlib.sha1(command.encode()).hexdigest()[:12]

    path = state_path(repo)
    store = load(path)
    note = reconcile(store.get(key), tests_run, head)

    store[key] = {
        "command": command,
        "tests_run": tests_run,
        "passed": passed,
        "head": head,
        "when": datetime.now().isoformat(timespec="seconds"),
    }
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2, sort_keys=True))

    if note:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PostToolUse",
                        "additionalContext": note,
                    }
                }
            )
        )
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never let bookkeeping break a real test run
        print(f"test_count_guard: no reconciliation this run: {exc}", file=sys.stderr)
        sys.exit(1)
