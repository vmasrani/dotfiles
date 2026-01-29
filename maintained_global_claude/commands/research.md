Generate or refresh `*-context.md` files for the current project using progressive disclosure.

Context files live inside the directory they describe, named `{dirname}-context.md` (e.g., `src/src-context.md`).

## Shell tools available

You have four helper tools on PATH (in `~/tools/`):

- **`ctx-index [dir] [--full]`** — Project map: one summary line per directory from all `*-context.md` files. Use `--full` to include file count and date metadata.
- **`ctx-tree [dir] [depth]`** — Shows directory tree using eza (respects gitignore, filters noise). Default depth: 3.
- **`ctx-peek [dir] [lines]`** — Shows first N lines of all `*-context.md` files under a directory. Default: 12 lines. Use this to scan existing context files without loading them fully.
- **`ctx-stale [dir]`** — Lists directories with missing or stale context files. A context file is "stale" if any sibling file has been modified more recently.

## Steps

### 1. Setup
Context files should be **committed to the repo** — do not add them to `.gitignore`. If `*-context.md` is currently in `.gitignore`, remove that line.

### 2. Discovery
Run `ctx-stale $ARGUMENTS` (or `ctx-stale .` if no arguments) via Bash. This will report:
- **MISSING:** directories that have files but no context file
- **STALE:** directories where files have changed since the context file was written
- **FRESH:** directories with up-to-date context files

Only directories listed as MISSING or STALE need processing.

### 3. Generation
For each directory needing a context file, launch a `context-researcher` agent via the Task tool with `run_in_background: true`, `model: sonnet`, and `max_turns: 12`. Batch 3-5 at a time.

Use a **short** description (e.g., `"ctx: src/utils"`). The agent prompt should be:
> Analyze the directory `{path}` and write the context file to `{path}/{dirname}-context.md`.

Do NOT read or process the agent's output beyond checking for SUCCESS/ERROR.

**CRITICAL:** Do NOT try to read all the generated context files after they're written. They are designed to be consumed one at a time by agents that need them, not loaded in bulk.

### 4. Report
After all agents complete, check each agent's status line for SUCCESS or ERROR. Summarize:
- **Created:** N new context files
- **Updated:** N refreshed context files
- **Skipped:** N up-to-date directories
- **Errors:** N failures (if any)

Do NOT read the generated context files. Just report the SUCCESS/ERROR counts.
