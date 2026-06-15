#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.8"
# ///
"""PostToolUse hook: record every ripgrep call Claude Code makes — both the built-in
Grep tool (reconstructed as an `rg` argv) and raw `rg` invocations inside Bash commands.

Appends one record per call across all sessions to:
  ~/.claude/rg_history.jsonl   full metadata (ts, src, cwd, argv, cmd, [head_limit])
  ~/.claude/rg_history.txt     just the runnable `rg ...` command, one per line

Intended for collecting a real-world test corpus for a drop-in ripgrep replacement.
Failures are swallowed (exit 0) so the hook never disrupts a tool call — the standard
convention for the other hooks in this directory.
"""

import json
import shlex
import sys
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path.home() / ".claude"
JSONL = OUT_DIR / "rg_history.jsonl"
TXT = OUT_DIR / "rg_history.txt"

# Tokens that may legitimately precede `rg` inside a shell segment.
WRAPPERS = {"command", "builtin", "time", "sudo", "nice", "nohup", "stdbuf", "\\rg"}
SHELL_OPERATORS = {"|", "|&", "||", "&&", ";", "&"}


def grep_tool_argv(ti: dict) -> list:
    """Reconstruct an `rg` argv from the Grep tool's parameters."""
    argv = ["rg"]
    mode = ti.get("output_mode", "files_with_matches")
    if mode == "files_with_matches":
        argv.append("-l")
    elif mode == "count":
        argv.append("-c")
    if ti.get("-i"):
        argv.append("-i")
    if ti.get("-n") and mode == "content":
        argv.append("-n")
    for flag in ("-A", "-B", "-C"):
        if ti.get(flag) is not None:
            argv += [flag, str(ti[flag])]
    if ti.get("multiline"):
        argv += ["-U", "--multiline-dotall"]
    if ti.get("type"):
        argv += ["--type", str(ti["type"])]
    if ti.get("glob"):
        argv += ["--glob", str(ti["glob"])]
    pattern = str(ti.get("pattern", ""))
    argv += ["-e", pattern] if pattern.startswith("-") else [pattern]
    if ti.get("path"):
        argv.append(str(ti["path"]))
    return argv


def _strip_prefix(seg: list) -> list:
    """Drop leading env-assignments (FOO=bar) and wrapper commands (sudo, time, ...)."""
    i = 0
    while i < len(seg):
        tok = seg[i]
        is_env = "=" in tok and tok.split("=", 1)[0].isidentifier()
        if tok in WRAPPERS or is_env:
            i += 1
        else:
            break
    return seg[i:]


def bash_rg_argvs(command: str) -> list:
    """Extract every `rg ...` invocation from a (possibly compound) bash command."""
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        return []
    segments, current = [], []
    for tok in tokens:
        if tok in SHELL_OPERATORS:
            segments.append(current)
            current = []
        else:
            current.append(tok)
    segments.append(current)
    stripped = [_strip_prefix(seg) for seg in segments]
    return [seg for seg in stripped if seg and seg[0] == "rg"]


def records_from(event: dict) -> list:
    """Return [(src, argv), ...] for every rg call in this tool event."""
    tool = event.get("tool_name", "")
    ti = event.get("tool_input") or {}
    if tool == "Grep":
        return [("grep-tool", grep_tool_argv(ti))]
    if tool == "Bash":
        return [("bash", argv) for argv in bash_rg_argvs(ti.get("command", ""))]
    return []


def main() -> None:
    event = json.load(sys.stdin)
    recs = records_from(event)
    if not recs:
        return
    ts = datetime.now(timezone.utc).isoformat()
    cwd = event.get("cwd", "")
    head_limit = (event.get("tool_input") or {}).get("head_limit")
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    jsonl_lines, txt_lines = [], []
    for src, argv in recs:
        cmd = shlex.join(argv)
        rec = {"ts": ts, "src": src, "cwd": cwd, "argv": argv, "cmd": cmd}
        if src == "grep-tool" and head_limit is not None:
            rec["head_limit"] = head_limit
        jsonl_lines.append(json.dumps(rec, ensure_ascii=False))
        txt_lines.append(cmd)

    with open(JSONL, "a", encoding="utf-8") as f:
        f.write("\n".join(jsonl_lines) + "\n")
    with open(TXT, "a", encoding="utf-8") as f:
        f.write("\n".join(txt_lines) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
