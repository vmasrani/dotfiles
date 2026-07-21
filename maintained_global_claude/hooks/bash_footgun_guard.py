#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.9"
# ///
"""PreToolUse guard: block Bash commands that FABRICATE EVIDENCE.

WHY THIS EXISTS
    Every rule here corresponds to a footgun that actually fired during real
    sessions (see parot-stats/FOOTGUNS.md). They share one property, and it is
    the reason they are worth a hook rather than a paragraph: **none of them
    produce an error.** They produce plausible, confident, wrong output --
    a search result that was never in any file, an exit code of 0 for a run
    with three failures, a "committed" marker for a commit that never happened.
    A crash teaches you something. These teach you something false.

    `rg -r` in particular is ALREADY documented in ~/.claude/CLAUDE.md and was
    hit anyway, by an agent that had that text in context. Prose has been tried
    and measured; it failed. Hence a deny.

WHY DENY AND NOT REWRITE
    The sibling hook (`test_queue_guard.py`) rewrites commands, because there
    the intent is unambiguous and the correct form is mechanical. Here the
    intent is NOT recoverable: only the caller knows whether `rg -rn foo` meant
    `-n` or meant a real replacement. Guessing would substitute one silent
    wrong answer for another. So: refuse, and name the correct form.

FAILURE POSTURE
    Fails OPEN but never SILENTLY: an unexpected error exits 1 (non-blocking),
    surfacing a hook-error line rather than quietly disarming the guard. When a
    rule needs to consult git and git cannot answer, that rule abstains -- it
    returns no decision at all, leaving the normal permission flow intact,
    rather than inventing a verdict from missing data.

    Emitting nothing (exit 0, no stdout) is deliberately NOT the same as
    emitting `permissionDecision: allow`: allow would auto-approve the command
    and bypass the user's own permission rules. This hook only ever says "no"
    or says nothing.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "utils"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from shell_tokens import (  # noqa: E402
    args_until_operator,
    command_heads,
    skip_env_assigns,
    tokenize,
)

# "What counts as a heavy build" is owned by the queue guard -- importing it
# keeps one definition. Importing is safe: that module only acts under __main__.
from test_queue_guard import HEAVY_CARGO_VERBS, JUST_HEAVY_RE  # noqa: E402

# ripgrep short flags that CONSUME the rest of their cluster as a value.
# This is what makes `-rn` mean `--replace=n` rather than `-r -n`, and it is
# also what stops us from misreading the `r` in `-er` (there, `r` is the value
# of `-e`, not a flag at all).
RG_VALUE_FLAGS = set("ABCefgjmMrtT")

MARKER_COMMANDS = {"echo", "print", "printf"}


def _deny(reason):
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def _git(cwd, *args):
    """Run a read-only git query. Returns stdout, or None if git can't answer."""
    proc = subprocess.run(
        ["git", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        timeout=5,
    )
    return proc.stdout if proc.returncode == 0 else None


def _rg_flags(argv):
    """Flag letters and long options genuinely passed to an rg invocation.

    Stops at `--`, and stops scanning a cluster at the first value-taking flag,
    so values are never mistaken for flags.
    """
    short, long = set(), set()
    for tok in argv:
        if tok == "--":
            break
        if tok.startswith("--"):
            long.add(tok.split("=", 1)[0])
        elif tok.startswith("-") and len(tok) > 1:
            for ch in tok[1:]:
                short.add(ch)
                if ch in RG_VALUE_FLAGS:
                    break  # rest of the cluster is this flag's value
    return short, long


def _git_subcommand(argv):
    """The git subcommand, skipping global flags like `-C <path>` / `-c k=v`."""
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if tok.startswith("-"):
            i += 1
            continue
        return tok, argv[i + 1 :]
    return None, []


def _worktrees(cwd):
    """Map branch name -> worktree path, from `git worktree list --porcelain`."""
    out = _git(cwd, "worktree", "list", "--porcelain")
    if out is None:
        return None
    trees, path = {}, None
    for line in out.splitlines():
        if line.startswith("worktree "):
            path = line[len("worktree ") :]
        elif line.startswith("branch refs/heads/") and path:
            trees[line[len("branch refs/heads/") :]] = path
    return trees


def _dirty(path):
    """Count of uncommitted changes in a worktree, or None if unknowable."""
    out = _git(path, "status", "--porcelain")
    return None if out is None else len([ln for ln in out.splitlines() if ln.strip()])


# --- rules -------------------------------------------------------------------
# Each takes the token stream (plus cwd) and calls _deny() on a violation.


def check_ripgrep(tokens, heads, cwd):
    """Footgun 3.1 -- `rg -r` is --replace, and silently rewrites every match."""
    for _op, head in heads:
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens) or Path(tokens[i]).name not in ("rg", "ripgrep"):
            continue
        short, long = _rg_flags(args_until_operator(tokens, i + 1))
        if "r" in short:
            _deny(
                "BLOCKED: `rg -r` is --replace, NOT recursive. It rewrites every match to "
                "the following text and prints the result as if it were a search hit -- "
                "plausible, fabricated output, with a zero exit code.\n"
                "  Recursion is ripgrep's DEFAULT; no flag is needed.\n"
                "  -n = line numbers, -l = filenames only (mutually exclusive).\n"
                "If you genuinely want substitution, spell it out: --replace=TEXT."
            )
        if ("l" in short or "--files-with-matches" in long) and (
            "n" in short or "--line-number" in long
        ):
            _deny(
                "BLOCKED: `rg -l` (filenames only) and `-n` (line numbers) are mutually "
                "exclusive -- one silently wins and the output is not what you asked for. "
                "Pick one: -l for a file list, -n for located matches."
            )


def check_piped_test_run(command, tokens, heads, cwd):
    """Footguns 1.1 / 1.2 -- a pipe replaces the suite's exit code with tail's,
    and truncates away the only evidence of WHICH tests ran."""
    if "pipefail" in command:
        return
    ordered = list(heads)
    for idx, (_op, head) in enumerate(ordered):
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens):
            continue
        tok = tokens[i]
        heavy = False
        if tok == "cargo":
            j = i + 1
            if j < len(tokens) and tokens[j].startswith("+"):
                j += 1
            heavy = j < len(tokens) and tokens[j] in HEAVY_CARGO_VERBS
        elif tok == "just":
            heavy = i + 1 < len(tokens) and JUST_HEAVY_RE.match(tokens[i + 1])
        if not heavy:
            continue
        # Is this heavy command's own stdout piped into something?
        if idx + 1 < len(ordered) and ordered[idx + 1][0] == "|":
            _deny(
                "BLOCKED: piping a test/build run discards BOTH things you need from it.\n"
                "  1. The exit code becomes the LAST command's -- `cargo test | tail` exits 0 "
                "even with failing tests. Background-task notifications have reported "
                "\"completed (exit code 0)\" for runs with 3 failures.\n"
                "  2. `| tail -N` keeps the summary line and throws away the list of which "
                "tests actually ran -- exactly the evidence needed to tell a real green from "
                "a stale binary.\n"
                "Instead, capture in full and read the file:\n"
                "  <cmd> > /tmp/run.log 2>&1; echo \"exit=$?\"; tail -40 /tmp/run.log\n"
                "Then grep it explicitly: rg -n 'FAIL|test run failed|^error' /tmp/run.log\n"
                "If you truly need a pipeline, put `set -o pipefail;` at the front."
            )


def check_commit_marker(tokens, heads, cwd):
    """Footgun 1.3 -- `git commit ; echo done` prints the marker even when the
    tree was clean and no commit happened."""
    seen_commit = False
    for op, head in heads:
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens):
            continue
        if seen_commit and op == ";" and Path(tokens[i]).name in MARKER_COMMANDS:
            _deny(
                "BLOCKED: an unconditional success marker after `git commit`. Joined with "
                "`;` the echo prints whether or not the commit happened -- and `git commit` "
                "on an already-clean tree is a NO-OP, so this reliably reports a commit that "
                "was never made (a following `git log -1` then shows someone else's).\n"
                "Use `&&` so the marker is conditional, or better, verify the state changed:\n"
                "  before=$(git rev-parse HEAD); git commit -m '...'; "
                "[ \"$before\" != \"$(git rev-parse HEAD)\" ] && echo committed\n"
                "Or guard the commit itself: git diff --cached --quiet || git commit -m '...'"
            )
        if tokens[i] == "git":
            sub, _rest = _git_subcommand(args_until_operator(tokens, i + 1))
            if sub == "commit":
                seen_commit = True


def check_git_destructive(tokens, heads, cwd):
    """Footguns 1.4 / local-only-cleanup -- deleting a branch whose work is
    uncommitted, or deleting a remote branch."""
    for _op, head in heads:
        i = skip_env_assigns(tokens, head)
        if i >= len(tokens) or tokens[i] != "git":
            continue
        sub, rest = _git_subcommand(args_until_operator(tokens, i + 1))

        if sub == "push":
            if "--delete" in rest or any(a.startswith(":") and len(a) > 1 for a in rest):
                _deny(
                    "BLOCKED: this deletes a REMOTE branch. Cleanup is local-only by default "
                    "-- `git worktree remove`, `git branch -d`, `git fetch --prune`. "
                    "If you really intend to delete the remote branch, say so explicitly and "
                    "the user can approve it."
                )
            continue

        if sub == "branch" and any(a in ("-d", "-D", "--delete") for a in rest):
            names = [a for a in rest if not a.startswith("-")]
            trees = _worktrees(cwd)
            if trees is None:
                continue  # git can't answer -- abstain rather than invent a verdict
            for name in names:
                path = trees.get(name)
                if not path:
                    continue
                n = _dirty(path)
                if n:
                    _deny(
                        f"BLOCKED: branch `{name}` is checked out at {path}, which has "
                        f"{n} uncommitted change(s).\n"
                        "`git branch --merged` LISTS SUCH A BRANCH AS MERGED when it has zero "
                        "commits of its own -- all the work is in the worktree, invisible to "
                        "the merge check -- so -d will happily delete it and the next "
                        "`git worktree remove` destroys the work entirely.\n"
                        f"Commit or stash in {path} first, then re-run."
                    )

        if sub == "worktree" and rest[:1] == ["remove"]:
            if not any(a in ("-f", "--force") for a in rest):
                continue  # unforced remove already refuses on a dirty tree
            targets = [a for a in rest[1:] if not a.startswith("-")]
            for target in targets:
                n = _dirty(target)
                if n:
                    _deny(
                        f"BLOCKED: `git worktree remove --force` on {target}, which has "
                        f"{n} uncommitted change(s). --force exists to override exactly the "
                        "check that is protecting that work right now. Commit or stash it "
                        "first; if the changes are genuinely disposable, say so explicitly."
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
    cwd = data.get("cwd") or Path.cwd()

    try:
        tokens = tokenize(command)
    except ValueError:
        sys.exit(0)  # unbalanced quotes -- not a runnable command, not ours to judge
    heads = list(command_heads(tokens))

    check_ripgrep(tokens, heads, cwd)
    check_piped_test_run(command, tokens, heads, cwd)
    check_commit_marker(tokens, heads, cwd)
    check_git_destructive(tokens, heads, cwd)
    sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # fail open, but visibly -- exit 1 is non-blocking
        print(f"bash_footgun_guard: guard did not run: {exc}", file=sys.stderr)
        sys.exit(1)
