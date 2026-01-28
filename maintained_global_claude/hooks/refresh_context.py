#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "anthropic",
#     "python-dotenv",
# ]
# ///

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import anthropic

SYSTEM_PROMPT = """You are a codebase analyst. Analyze the provided directory listing and file contents to produce a concise context file.

Output format (raw markdown, no code fences):

# {Directory Name}

## Purpose
{1-2 sentences}

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| {file} | {role} | {exports} |

## Patterns
{Architectural patterns used}

## Dependencies
- **External:** {packages}
- **Internal:** {imports from other dirs}

## Entry Points
{Main entry files}

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| {subdir} | {one-liner} | {yes/no} |

Only include sections with content. Be concise."""

SKIP_EXTENSIONS = {".pyc", ".pyo", ".so", ".dylib", ".o", ".a", ".class", ".jar", ".whl", ".egg", ".lock", ".min.js", ".min.css", ".map"}
SKIP_FILES = {"package-lock.json", "yarn.lock", "pnpm-lock.yaml", "uv.lock", ".DS_Store", "Thumbs.db"}
MAX_FILE_SIZE = 32_000
MAX_FILES = 30


def read_directory_contents(dir_path: Path) -> str:
    """Read directory listing and file contents for the prompt."""
    parts = []
    files = sorted(dir_path.iterdir())
    subdirs = [f for f in files if f.is_dir() and not f.name.startswith(".")]
    regular_files = [
        f for f in files
        if f.is_file()
        and f.suffix not in SKIP_EXTENSIONS
        and f.name not in SKIP_FILES
        and not f.name.endswith("-context.md")
    ]

    parts.append(f"Directory: {dir_path.name}/\n")

    if subdirs:
        parts.append("Subdirectories:")
        for sd in subdirs:
            has_ctx = (sd / f"{sd.name}-context.md").exists()
            parts.append(f"  {sd.name}/ {'(has context file)' if has_ctx else ''}")
        parts.append("")

    parts.append(f"Files ({len(regular_files)}):\n")
    for f in regular_files[:MAX_FILES]:
        parts.append(f"--- {f.name} ---")
        if f.stat().st_size > MAX_FILE_SIZE:
            parts.append(f"[File too large: {f.stat().st_size} bytes, showing first {MAX_FILE_SIZE} chars]")
            parts.append(f.read_text(errors="replace")[:MAX_FILE_SIZE])
        else:
            parts.append(f.read_text(errors="replace"))
        parts.append("")

    if len(regular_files) > MAX_FILES:
        parts.append(f"[...and {len(regular_files) - MAX_FILES} more files]")

    return "\n".join(parts)


def generate_context(dir_path: Path, client: anthropic.Anthropic) -> str:
    """Call Anthropic API to generate context for a directory."""
    content = read_directory_contents(dir_path)
    response = client.messages.create(
        model="claude-haiku-4-20250414",
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Analyze this directory:\n\n{content}"}],
    )
    return response.content[0].text


def main():
    if len(sys.argv) < 2:
        sys.exit(0)

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        sys.exit(0)

    client = anthropic.Anthropic(api_key=api_key)
    dirs = [Path(d) for d in sys.argv[1:] if Path(d).is_dir()]

    for dir_path in dirs:
        dirname = dir_path.name
        context_file = dir_path / f"{dirname}-context.md"
        context_md = generate_context(dir_path, client)
        context_file.write_text(context_md)


if __name__ == "__main__":
    main()
