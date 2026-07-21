#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""Behavioural tests for the PreToolUse/PostToolUse guards.

Run: ./hooks_selftest.py   (exits nonzero on any failure)

A guard nobody tests is a guard that silently stops guarding -- and these ones
fail OPEN, so a regression here looks exactly like normal operation. Every case
below is either a footgun that actually fired (see parot-stats/FOOTGUNS.md) or a
false-positive shape that must keep working.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PY = "/usr/bin/python3"

fails = []


def run_hook(script, payload):
    proc = subprocess.run(
        [PY, str(HOOKS / script)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
    )
    return proc


def decision(command, cwd="/tmp"):
    proc = run_hook(
        "bash_footgun_guard.py",
        {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}},
    )
    if proc.returncode != 0:
        return f"ERROR({proc.stderr.strip()})"
    if not proc.stdout.strip():
        return "pass"
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


def expect(label, got, want):
    status = "ok  " if got == want else "FAIL"
    if got != want:
        fails.append(f"{label}: wanted {want}, got {got}")
    print(f"  [{status}] {label}  -> {got}")


print("\n== bash_footgun_guard: must DENY ==")
for cmd in [
    "rg -rn 'word_index_from_tokens'",
    "rg -rl foo",
    "rg -r foo src/",
    "rg -nr foo",
    "rg -ln foo",
    "rg -l -n foo",
    "cargo nextest run --workspace | tail -25",
    "cargo nextest run -p parot-daemon 2>&1 | rg FAIL",
    "just test | tail -5",
    "cd /repo && cargo build | head -20",
    'git add -A && git commit -m "x" ; echo "=== committed ==="',
    "git push origin --delete feature-branch",
    "git push origin :refs/heads/gone",
]:
    expect(cmd, decision(cmd), "deny")

print("\n== bash_footgun_guard: must PASS ==")
for cmd in [
    "rg -n 'foo'",
    "rg -l foo",
    "rg --replace=X foo",
    "rg -er foo",  # r is the VALUE of -e, not a flag
    "rg foo -- -r",  # after --, not a flag
    'rg -n "^test|nextest|cargo test" justfile',  # quoted pipe is data
    "set -o pipefail; cargo nextest run --workspace | tail -25",
    "cargo nextest run --workspace",
    "cargo metadata --format-version 1 | jq .",
    "echo hi | cat && cargo build",
    'git commit -m "x" && echo done',
    'git commit -m "x"; git log -1',
    "git push origin main",
    "ls -la",
    "rg -n 'unbalanced",  # unbalanced quote -> not ours to judge
]:
    expect(cmd, decision(cmd), "pass")

print("\n== bash_footgun_guard: git worktree rules (real repo) ==")
with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "repo"
    root.mkdir()
    sh = lambda *a, cwd=root: subprocess.run(  # noqa: E731
        a, cwd=str(cwd), capture_output=True, text=True, check=True
    )
    sh("git", "init", "-q", "-b", "main")
    sh("git", "config", "user.email", "t@t.t")
    sh("git", "config", "user.name", "t")
    (root / "a.txt").write_text("hello\n")
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", "init")

    wt = Path(td) / "wt-dirty"
    sh("git", "worktree", "add", "-q", "-b", "dirty-branch", str(wt))
    (wt / "work.txt").write_text("uncommitted integration work\n")

    wt_clean = Path(td) / "wt-clean"
    sh("git", "worktree", "add", "-q", "-b", "clean-branch", str(wt_clean))

    # The exact footgun: --merged lists it as merged because it has no commits.
    merged = subprocess.run(
        ["git", "branch", "--merged", "main"], cwd=str(root), capture_output=True, text=True
    ).stdout
    print(f"  (git branch --merged reports: {merged.split()!r})")

    expect(
        "git branch -d dirty-branch (uncommitted work in worktree)",
        decision("git branch -d dirty-branch", cwd=str(root)),
        "deny",
    )
    expect(
        "git branch -d clean-branch (clean worktree)",
        decision("git branch -d clean-branch", cwd=str(root)),
        "pass",
    )
    expect(
        "git worktree remove --force <dirty>",
        decision(f"git worktree remove --force {wt}", cwd=str(root)),
        "deny",
    )
    expect(
        "git worktree remove <dirty> (unforced: git refuses on its own)",
        decision(f"git worktree remove {wt}", cwd=str(root)),
        "pass",
    )
    expect(
        "git branch -d x outside any repo",
        decision("git branch -d whatever", cwd="/tmp"),
        "pass",
    )

print("\n== test_queue_guard still rewrites after the refactor ==")
proc = run_hook(
    "test_queue_guard.py",
    {"tool_name": "Bash", "tool_input": {"command": "cargo nextest run --workspace"}},
)
out = json.loads(proc.stdout) if proc.stdout.strip() else {}
got = out.get("hookSpecificOutput", {}).get("updatedInput", {}).get("command")
expect("cargo nextest run --workspace", got, "testq zsh -c 'cargo nextest run --workspace'")
proc = run_hook(
    "test_queue_guard.py",
    {"tool_name": "Bash", "tool_input": {"command": 'rg -n "a|cargo test" justfile'}},
)
expect("quoted 'cargo test' not queued", proc.stdout.strip() or "pass", "pass")

print("\n== test_count_guard ==")
NEXTEST_742 = "    Summary [   9.293s] 742 tests run: 742 passed, 3 skipped"
NEXTEST_751 = "    Summary [   9.512s] 751 tests run: 751 passed, 3 skipped"
CARGO = "test result: ok. 12 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out"


def count_hook(command, stdout, cwd):
    proc = run_hook(
        "test_count_guard.py",
        {
            "tool_name": "Bash",
            "cwd": cwd,
            "tool_input": {"command": command},
            "tool_response": {"stdout": stdout, "stderr": "", "interrupted": False},
        },
    )
    if proc.returncode != 0:
        return f"ERROR({proc.stderr.strip()})"
    if not proc.stdout.strip():
        return ""
    return json.loads(proc.stdout)["hookSpecificOutput"]["additionalContext"]


with tempfile.TemporaryDirectory() as td:
    state = Path.home() / ".claude" / "state" / "testcounts"
    before = set(state.glob("*.json")) if state.exists() else set()

    cmd = "cargo nextest run -p parot-daemon -p parot-cli"
    first = count_hook(cmd, NEXTEST_742, td)
    expect("first run records a baseline", "baseline recorded" in first.lower(), True)

    same = count_hook(cmd, NEXTEST_742, td)
    expect("identical count stays silent", same, "")

    up = count_hook(cmd, NEXTEST_751, td)
    expect("count rose -> reconcile prompt", "742 -> 751 (+9)" in up, True)

    down = count_hook(cmd, NEXTEST_742, td)
    expect("count DROPPED -> stale-binary warning", "went DOWN" in down, True)

    expect(
        "queued form keys the same as the bare command",
        count_hook(f"testq zsh -c '{cmd}'", NEXTEST_742, td),
        "",
    )
    expect(
        "a different command gets its own baseline",
        "baseline recorded"
        in count_hook("cargo nextest run --workspace", NEXTEST_751, td).lower(),
        True,
    )
    expect("plain `cargo test` output parses", "baseline" in count_hook("cargo test", CARGO, td).lower(), True)
    expect("non-test command ignored", count_hook("ls -la", "a.txt b.txt", td), "")

    for p in (set(state.glob("*.json")) - before):
        p.unlink()

print()
if fails:
    print(f"{len(fails)} FAILURE(S):")
    for f in fails:
        print(f"  - {f}")
    sys.exit(1)
print("all guard tests passed")
