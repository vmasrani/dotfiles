Generate or refresh `*-context.md` files for the current project using progressive disclosure.

Context files live inside the directory they describe, named `{dirname}-context.md` (e.g., `src/src-context.md`).

## Shell tools available

You have four helper tools on PATH (in `~/tools/`):

- **`ctx-index [dir] [--full]`** — Project map: one summary line per directory from all `*-context.md` files. Use `--full` to include file count and date metadata.
- **`ctx-tree [dir] [depth]`** — Shows directory tree using eza (respects gitignore, filters noise). Default depth: 3.
- **`ctx-peek [dir] [lines]`** — Shows first N lines of all `*-context.md` files under a directory. Default: 12 lines. Use this to scan existing context files without loading them fully.
- **`ctx-stale [dir] [--max-depth N] [--min-files N]`** — Lists directories with missing or stale context files. Skips dirs with fewer than N files (default: 2) and limits scan depth (default: 4).

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
For each directory needing a context file, launch a `context-researcher` agent via the Task tool with `model: haiku`.

**Launch ALL agents in a single message** — multiple Task calls in one response. Do **NOT** use `run_in_background`. Do **NOT** use `TaskOutput`. Parallel Task calls in a single message already run concurrently.

Use a **short** description (e.g., `"ctx: src/utils"`). The agent prompt should be:
> Analyze the directory `{path}` and write the context file to `{path}/{dirname}-context.md`. Return ONLY "SUCCESS: wrote {path}" or "ERROR: {path} — {reason}". Nothing else.

Each agent returns a single status line as its Task return value. That is all you need.

**CRITICAL:** Do NOT read the generated context files. Do NOT use TaskOutput or Read to check agent output files. The Task return values are your only input for the report.

### 4. Report
Read each Task return value (a single status line per agent). Summarize:
- **Created:** N new context files
- **Updated:** N refreshed context files
- **Skipped (SKIP marker):** N directories with intentional SKIP markers
- **Skipped (up-to-date):** N fresh directories (from ctx-stale output)
- **Errors:** N failures (list any error messages)
