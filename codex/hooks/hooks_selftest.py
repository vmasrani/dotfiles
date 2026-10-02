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
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOKS = Path(__file__).resolve().parent
PY = "/usr/bin/python3"
# resolve() above already followed the ~/.codex/hooks symlink into the dotfiles
# repo, so queue is a sibling of the hooks that guard it.
QUEUE = HOOKS.parents[1] / "tools" / "queue"

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

print("\n== unqueued_heavy_guard: a forgotten prefix is an error, not a slowdown ==")
# WHAT REPLACED WHAT: test_queue_guard.py used to REWRITE heavy commands into
# the queue, and this section used to assert the rewrite came out byte-exact,
# then cross-check the hook's notion of "heavy" against testq's weight table --
# two independently-maintained classifiers that drifted apart twice. Both are
# gone. Queueing is explicit; the hook only denies.


def guard(command):
    """'allow' if the hook passes the command through, else the denial reason."""
    proc = run_hook(
        "unqueued_heavy_guard.py", {"tool_name": "Bash", "tool_input": {"command": command}}
    )
    if proc.returncode != 0:
        return f"hook errored: {proc.stderr.strip()[:80]}"
    if not proc.stdout.strip():
        return "allow"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"]


for cmd in [
    "cargo nextest run --workspace",
    "cargo nextest r --workspace",
    "cargo test",
    "cargo +nightly test -p parot-daemon",
    "cargo bench --bench index",
    "cargo miri test",
    "just test",
    "just test-unit",
    "just ci-fast",
    "just ci-deep",
    "just bench",
    "cd /repo && cargo nextest run",
    "RUST_LOG=debug cargo test",
    "cargo build && cargo nextest run",
    "just ci-fast > /tmp/x.log 2>&1",
    "cargo nextest run 2>&1 | tail -20",
    # 2026-10-01: every COMPILE holds a slot too. Builds outside the queue
    # stalled the 4 TB volume (451 ms median file create under ~23 concurrent
    # compilers vs 2 ms drained).
    "cargo build",
    "cargo build --workspace",
    "cargo build --release",
    "cargo check --workspace",
    "cargo clippy --all-targets -- -D warnings",
    "cargo install --path .",
    "cargo install --release --path .",
    "cargo doc --no-deps",
    "cargo rustc -- --emit asm",
    "cargo run --bin x",
    "cargo +nightly build",
    "cargo b",
    "cargo nextest run --no-run -p x",
    "cargo nextest list",
    "cargo nextest archive --archive-file a.tar.zst",
    "cargo test --no-run",
    "cargo test --list",
    "just lint",
    "just install",
    "just check",
    "just clippy",
    "just fastdev",
    "just build-linux",
    "just build-cartridge-release",
    "just publish-release",
    "maturin build --release",
    "maturin develop",
    "cd /x && cargo build",
    # The `&&` trap: `queue` received only the `cd` and the suite ran loose.
    # This is the one mistake a command prefix cannot detect for itself, since
    # the shell consumes the operator before `queue` is exec'd -- the hook sees
    # the raw string, so it is the only component that can catch it at all.
    "queue cd /repo && cargo nextest run",
    "queue cd /x && cargo build",
]:
    expect(cmd, guard(cmd), "deny")

print("\n== unqueued_heavy_guard: what must NEVER be denied ==")
for cmd in [
    # no compile, no test run
    "cargo fmt",
    "cargo metadata --format-version 1",
    "cargo tree",
    "cargo update",
    "cargo add serde",
    "cargo search serde",
    "cargo --version",
    "cargo nextest --version",
    "cargo nextest show-config",
    "cargo nextest self update",
    "just --list",
    # already queued -- must never be double-flagged
    "queue cargo nextest run --workspace",
    "queue --solo cargo bench",
    "QUEUE_QUIET=1 queue just ci-fast",
    "queue 'cd /repo && cargo nextest run'",
    "queue cargo build",
    "queue 'cd /x && cargo build'",
    "queue 'cargo check --workspace'",
    "queue 'cd /x && cargo clippy --all-targets -- -D warnings'",
    "queue 'cd /x && cargo install --path .'",
    "queue 'cd /x && cargo test --no-run'",
    "queue just lint",
    "queue 'maturin develop'",
    # not a command in head position -- quoted text is data, not a suite
    'rg -n "a|cargo test" justfile',
    'rg -n "cargo build" justfile',
    "git status",
]:
    expect(cmd, guard(cmd), "allow")

print("\n== unqueued_heavy_guard: pre-dev integration (concurrent-work rule) ==")
# AGENTS.md: "Concurrent work = pre-dev integration" -- while refs/heads/pre-dev
# exists, heavy gates are denied off pre-dev EVEN WHEN CORRECTLY QUEUED, since
# the whole point is that workers never run their own gate, queued or not.


def guard_cwd(command, cwd):
    proc = run_hook(
        "unqueued_heavy_guard.py",
        {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}},
    )
    if proc.returncode != 0:
        return f"hook errored: {proc.stderr.strip()[:80]}"
    if not proc.stdout.strip():
        return "allow"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    return out["permissionDecision"]


with tempfile.TemporaryDirectory() as td:
    root = Path(td) / "repo"
    root.mkdir()
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t.t",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t.t",
    }
    sh = lambda *a, cwd=root: subprocess.run(  # noqa: E731
        a, cwd=str(cwd), capture_output=True, text=True, check=True, env={**os.environ, **env}
    )
    sh("git", "init", "-q", "-b", "issue-1")
    sh("git", "commit", "-q", "--allow-empty", "-m", "init")
    sh("git", "branch", "pre-dev")

    expect(
        "issue-1 branch: queue just ci-fast -> deny (pre-dev active)",
        guard_cwd("queue just ci-fast", str(root)),
        "deny",
    )
    expect(
        "issue-1 branch: just ci-fast -> deny (pre-dev active)",
        guard_cwd("just ci-fast", str(root)),
        "deny",
    )
    # Builds are not gates: a worker still builds on its own branch, queued.
    expect(
        "issue-1 branch: queue cargo build -> allow (builds are not gated by pre-dev)",
        guard_cwd("queue cargo build", str(root)),
        "allow",
    )
    expect(
        "issue-1 branch: queue cargo nextest run --no-run -> allow (compile only)",
        guard_cwd("queue cargo nextest run --no-run", str(root)),
        "allow",
    )
    expect(
        "issue-1 branch: queue cargo nextest run -> deny (test, pre-dev active)",
        guard_cwd("queue cargo nextest run", str(root)),
        "deny",
    )
    expect(
        "issue-1 branch: cargo build unqueued -> deny (queue rule, not pre-dev)",
        guard_cwd("cargo build", str(root)),
        "deny",
    )

    sh("git", "checkout", "-q", "pre-dev")
    expect(
        "pre-dev branch: queue just ci-fast -> allow (the one gate)",
        guard_cwd("queue just ci-fast", str(root)),
        "allow",
    )

    sh("git", "checkout", "-q", "issue-1")
    sh("git", "branch", "-D", "pre-dev")
    expect(
        "issue-1 branch after pre-dev deleted: queue just ci-fast -> allow",
        guard_cwd("queue just ci-fast", str(root)),
        "allow",
    )

    # Numbered integration branches (pre-dev2, pre-dev3, ...) carry the same
    # rules -- a second concurrent wave gets its own branch and its own gate.
    sh("git", "branch", "pre-dev2")
    expect(
        "issue-1 branch: queue just ci-fast -> deny (pre-dev2 active)",
        guard_cwd("queue just ci-fast", str(root)),
        "deny",
    )
    sh("git", "checkout", "-q", "pre-dev2")
    expect(
        "pre-dev2 branch: queue just ci-fast -> allow (its own one gate)",
        guard_cwd("queue just ci-fast", str(root)),
        "allow",
    )

    sh("git", "checkout", "-q", "issue-1")
    sh("git", "branch", "pre-dev")
    expect(
        "issue-1 branch: queue just ci-fast -> deny (pre-dev and pre-dev2 both active)",
        guard_cwd("queue just ci-fast", str(root)),
        "deny",
    )
    sh("git", "checkout", "-q", "pre-dev2")
    expect(
        "pre-dev2 branch: queue just ci-fast -> allow (pre-dev also active)",
        guard_cwd("queue just ci-fast", str(root)),
        "allow",
    )

    sh("git", "checkout", "-q", "issue-1")
    sh("git", "branch", "-D", "pre-dev")
    sh("git", "branch", "-D", "pre-dev2")
    sh("git", "branch", "pre-development")
    sh("git", "branch", "pre-dev-foo")
    expect(
        "issue-1 branch: queue just ci-fast -> allow (pre-development/pre-dev-foo don't match)",
        guard_cwd("queue just ci-fast", str(root)),
        "allow",
    )
    sh("git", "branch", "-D", "pre-development")
    sh("git", "branch", "-D", "pre-dev-foo")

print("\n== hook <-> queue: the names the guard accepts must really exist ==")
# The guard treats a command as safe when it starts with `queue`. If the tool
# were renamed again and the guard not updated, every suite would read as
# already-queued and the guard would pass everything -- failing open, silently.
if not QUEUE.exists():
    print(f"  [FAIL] cannot find queue at {QUEUE}")
    fails.append(f"queue not found at {QUEUE}")
else:
    proc = subprocess.run([str(QUEUE), "--help"], capture_output=True, text=True)
    expect("queue --help works without a daemon", proc.returncode, 0)

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
    state = Path.home() / ".codex" / "state" / "testcounts"
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
        count_hook(f"queue zsh -c '{cmd}'", NEXTEST_742, td),
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
