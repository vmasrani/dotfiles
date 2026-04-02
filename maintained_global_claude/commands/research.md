Generate or refresh `*-context.md` files for the current project using progressive disclosure.

**IMPORTANT:** If you are currently in plan mode, call the `ExitPlanMode` tool immediately before doing anything else. This command requires full agent mode to write files and launch subagents.

Context files live inside the directory they describe, named `{dirname}-context.md` (e.g., `src/src-context.md`). They capture non-obvious conventions, gotchas, and key entry points — things an agent can't discover by reading code alone.

## Shell tools available

You have six helper tools on PATH (in `~/tools/`):

- **`ctx-index [dir] [--full] [--depth N]`** — Project map: one summary line per directory from all `*-context.md` files. Use `--full` to include file count and date metadata. Use `--depth N` to limit search depth (e.g., `--depth 1` for top-level only).
- **`ctx-tree [dir] [depth]`** — Shows directory tree using eza (respects gitignore, filters noise). Default depth: 3.
- **`ctx-peek [dir] [lines] [--depth N]`** — Preview context files. No args = this dir only; with dir = dir + immediate children (depth 1). Default: 12 lines. Use `--depth N` to override.
- **`ctx-stale [dir] [--max-depth N] [--min-files N]`** — Lists directories with missing or stale context files. Skips dirs with fewer than N files (default: 2) and limits scan depth (default: 4).
- **`ctx-skip [dir] [reason]`** — Mark a directory as skipped for context generation. Creates a stub with a SKIP marker.
- **`ctx-reset [dir] [--dry-run]`** — Remove all `*-context.md` files from a directory tree. Use `--dry-run` to preview. Useful for starting fresh.

## Steps

### 1. Setup
Context files should be **committed to the repo** — do not add them to `.gitignore`. If `*-context.md` is currently in `.gitignore`, remove that line.

### 2. Discovery
Run `ctx-stale $ARGUMENTS` (or `ctx-stale .` if no arguments) via Bash. This will report:
- **MISSING:** directories that have files but no context file
- **STALE:** directories where files have changed since the context file was written
- **FRESH:** directories with up-to-date context files

Only directories listed as MISSING or STALE need processing.

**Tip:** Use `ctx-skip {dir} "{reason}"` to permanently exclude directories that shouldn't have context files (e.g., auto-generated code, vendor directories, test fixtures). SKIP markers persist across runs and are committed to the repo.

**Tip:** Use `ctx-reset {dir}` to clear all context files and start from scratch.

### 3. Ordering (bottom-up)

Split the directories needing processing into two groups:

- **Leaves**: directories that have NO subdirectories in the processing list
- **Parents**: directories that have at least one subdirectory in the processing list

To determine this: for each directory in the MISSING/STALE list, check if any other directory in that list is a child path of it. If yes, it's a parent. If no, it's a leaf.

Process leaves first (Step 4a), wait for all to complete, then process parents (Step 4b). This ensures parent context files can leverage child summaries via `ctx-index`.

### 4. Generation

For each directory needing a context file, launch a `context-researcher` agent via the Agent tool with `model: sonnet`.

Use a **short** description (e.g., `"ctx: src/utils"`). The agent prompt should be:
> Analyze the directory `{path}` and write the context file to `{path}/{dirname}-context.md`. Today's date is {YYYY-MM-DD}. Return ONLY "SUCCESS: wrote {path}" or "ERROR: {path} — {reason}". Nothing else.

Each agent returns a single status line. That is all you need.

#### 4a. Generate leaf directories

Launch `context-researcher` agents for ALL leaf directories in a single message (parallel Agent calls). Wait for all to complete before proceeding.

#### 4b. Generate parent directories

Launch `context-researcher` agents for ALL parent directories in a single message (parallel Agent calls). These agents will use `ctx-index {dir} --depth 1` to pull summaries from the child context files generated in step 4a.

**CRITICAL:** Do NOT read the generated context files. The agent return values are your only input for the report.

### 5. Report
Read each agent return value (a single status line per agent). Summarize:
- **Phase 1 (leaves):** N directories processed
- **Phase 2 (parents):** N directories processed
- **Created:** N new context files
- **Updated:** N refreshed context files
- **Skipped (SKIP marker):** N directories with intentional SKIP markers
- **Skipped (up-to-date):** N fresh directories (from ctx-stale output)
- **Errors:** N failures (list any error messages)
