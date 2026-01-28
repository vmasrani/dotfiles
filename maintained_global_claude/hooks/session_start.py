#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import os
import subprocess
import sys
from pathlib import Path


def find_stale_context_files(project_dir: Path) -> list[Path]:
    """Find directories with missing or stale context files."""
    stale = []
    skip_dirs = {".git", ".venv", "node_modules", "__pycache__", "dist", "build", ".next", ".claude", ".mypy_cache", ".pytest_cache", ".ruff_cache", "venv", "env"}

    for dirpath, dirnames, filenames in os.walk(project_dir):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs and not d.startswith(".")]
        dp = Path(dirpath)
        dirname = dp.name
        context_file = dp / f"{dirname}-context.md"

        source_files = [f for f in filenames if not f.endswith("-context.md")]
        if not source_files:
            continue

        if not context_file.exists():
            stale.append(dp)
            continue

        context_mtime = context_file.stat().st_mtime
        for f in source_files:
            if (dp / f).stat().st_mtime > context_mtime:
                stale.append(dp)
                break

    return stale


def main():
    input_data = json.load(sys.stdin)
    cwd = input_data.get("cwd", os.getcwd())
    project_dir = Path(cwd)

    if not (project_dir / ".git").exists():
        sys.exit(0)

    stale_dirs = find_stale_context_files(project_dir)
    if not stale_dirs:
        sys.exit(0)

    refresh_script = Path(__file__).parent / "refresh_context.py"
    if not refresh_script.exists():
        sys.exit(0)

    dir_args = [str(d) for d in stale_dirs[:20]]
    subprocess.Popen(
        ["uv", "run", str(refresh_script)] + dir_args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )

    print(f"[context-refresh] Refreshing {len(dir_args)} stale context files in background")
    sys.exit(0)


if __name__ == "__main__":
    main()
