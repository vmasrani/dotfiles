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
import re
import shlex
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PY = "/usr/bin/python3"
# resolve() above already followed the ~/.claude/hooks symlink into the dotfiles
# repo, so testq is a sibling of the hooks that rewrite commands into it.
TESTQ = HOOKS.parents[1] / "tools" / "testq"

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


def expect_at_least(label, got, floor):
    ok = got is not None and got >= floor
    if not ok:
        fails.append(f"{label}: wanted weight >= {floor}, got {got}")
    print(f"  [{'ok  ' if ok else 'FAIL'}] {label}  -> weight {got} (floor {floor})")


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

print("\n== bash_footgun_guard: local path-dep commit (real repo) ==")
SWAPPED = """[tool.uv.sources]
# parot = { git = "ssh://git@github.com/x/parot.git", rev = "ec3454c" }
parot = { path = "../parot", editable = true }
"""
PINNED = """[tool.uv.sources]
parot = { git = "ssh://git@github.com/x/parot.git", rev = "ec3454c" }
# parot = { path = "../parot", editable = true }
"""
# A vendored/workspace path dep: committed on purpose, no parked alternative.
WORKSPACE = """[dependencies]
vers-vecs = { path = "vendor/vers-vecs" }
serde = { version = "1.0", features = ["derive"] }
"""

with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "repo"
    root.mkdir()
    sh = lambda *a, cwd=root: subprocess.run(  # noqa: E731
        a, cwd=str(cwd), capture_output=True, text=True, check=True
    )
    sh("git", "init", "-q", "-b", "main")
    sh("git", "config", "user.email", "t@t.t")
    sh("git", "config", "user.name", "t")
    (root / "pyproject.toml").write_text(PINNED)
    sh("git", "add", "-A")
    sh("git", "commit", "-qm", "init")

    # Staged swap -- the exact shape that shipped twice.
    (root / "pyproject.toml").write_text(SWAPPED)
    sh("git", "add", "pyproject.toml")
    expect(
        "git commit with the swapped path dep STAGED",
        decision('git commit -m "x"', cwd=str(root)),
        "deny",
    )
    expect(
        "git add -A && git commit (same swap)",
        decision('git add -A && git commit -m "x"', cwd=str(root)),
        "deny",
    )

    # Unstaged swap + `commit -am`: the index still looks clean, the worktree does not.
    sh("git", "reset", "-q", "HEAD", "pyproject.toml")
    expect(
        "git commit -am with the swap only in the WORKTREE",
        decision('git commit -am "x"', cwd=str(root)),
        "deny",
    )
    expect(
        "git commit (no -a) while the swap is unstaged -- not in this commit",
        decision('git commit -m "x"', cwd=str(root)),
        "pass",
    )

    # Restoring the pin must commit cleanly, or the guard is unusable.
    (root / "pyproject.toml").write_text(PINNED)
    sh("git", "add", "pyproject.toml")
    expect(
        "git commit restoring the pinned source",
        decision('git commit -m "restore pin"', cwd=str(root)),
        "pass",
    )

    # An ordinary workspace path dep has no parked alternative -> must not fire.
    (root / "Cargo.toml").write_text(WORKSPACE)
    sh("git", "add", "Cargo.toml")
    expect(
        "git commit with a plain workspace path dep",
        decision('git commit -m "vendor"', cwd=str(root)),
        "pass",
    )
    expect(
        "git commit outside any repo",
        decision('git commit -m "x"', cwd="/tmp"),
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

print("\n== hook <-> testq: nothing the hook queues may weigh 1 ==")
# THE INVARIANT, in one line: if the hook thinks a command is heavy enough to
# queue, the queue must think it is heavy enough to reserve capacity for.
#
# These are two files that decide "heavy" independently -- test_queue_guard.py
# by argv token, testq's classify() by weight table -- and they drifted apart
# twice. `just ci-fast` was heavy to the hook and weight 1 to the queue; every
# hook-wrapped `zsh -c '...'` was weight 1 because the queue never unwrapped the
# shell the hook is REQUIRED to add. Both failures look like normal operation:
# jobs queue, jobs run, twelve suites overlap and the box thrashes. So the test
# feeds the hook's real output into the real classifier rather than asserting
# against a copy of either table.
if not TESTQ.exists():
    print(f"  [FAIL] cannot find testq at {TESTQ}")
    fails.append(f"testq not found at {TESTQ}")


def queue_weight(command):
    """Hook -> rewritten command -> testq --explain. None if the hook passed it through."""
    proc = run_hook("test_queue_guard.py", {"tool_name": "Bash", "tool_input": {"command": command}})
    if not proc.stdout.strip():
        return None
    rewritten = json.loads(proc.stdout)["hookSpecificOutput"]["updatedInput"]["command"]
    argv = shlex.split(rewritten)
    argv = argv[argv.index("testq") + 1 :]  # drop any TESTQ_SESSION= prefix and `testq`
    out = subprocess.run(
        [str(TESTQ), "--explain", *argv], capture_output=True, text=True, check=True
    )
    return int(re.search(r"weight=(\d+)", out.stdout).group(1))


# Floor 9 = runs a suite (must be effectively exclusive); floor 3 = compiles.
for cmd, floor in [
    ("cargo nextest run --workspace", 9),
    ("cargo test", 9),
    ("cargo +nightly test -p parot-daemon", 9),
    ("cargo bench --bench index", 9),
    ("cargo miri test", 9),
    ("just test", 9),
    ("just test-unit", 9),
    ("just ci-fast", 9),
    ("just ci-deep", 9),
    ("just bench", 9),
    ("cd /repo && cargo nextest run", 9),
    ("RUST_LOG=debug cargo test", 9),
    ("cargo build && cargo nextest run", 9),
    ("just ci-fast > /tmp/x.log 2>&1", 9),
    ("cargo nextest run 2>&1 | tail -20", 9),
    ("cargo-slot agent-1 cargo test", 9),
    ("cargo build --release", 3),
    ("cargo check --workspace", 3),
    ("cargo clippy --all-targets -- -D warnings", 3),
    ("cargo install --path .", 3),
    ("just lint", 3),
]:
    expect_at_least(cmd, queue_weight(cmd), floor)

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
