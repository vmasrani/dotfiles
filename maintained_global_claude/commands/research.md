Generate or refresh `*-context.md` files for the current project using progressive disclosure.

Context files live inside the directory they describe, named `{dirname}-context.md` (e.g., `src/src-context.md`).

## Steps

### 1. Setup
Check if `*-context.md` is in the project's `.gitignore`. If not, append it:
```
# Auto-generated context files
*-context.md
```

### 2. Discovery
Walk the directory tree starting from `$ARGUMENTS` (or project root if not specified). Respect `.gitignore`. For each directory, check if:
- A `{dirname}-context.md` file exists
- If it exists, check if any sibling file is newer than the context file (stale)

Collect directories that need context files (missing or stale).

Skip directories that are:
- Hidden (`.git`, `.venv`, etc.)
- `node_modules`, `__pycache__`, `dist`, `build`, `.next`
- Already have an up-to-date context file

### 3. Generation
For each directory needing a context file, launch a `context-researcher` agent via the Task tool with `run_in_background: true` and `model: haiku`. Batch 3-5 at a time.

The agent prompt should be:
> Analyze the directory `{path}` and produce a context markdown file. List all files, their roles, patterns used, dependencies, and subdirectories. Output raw markdown only.

Write the agent's output to `{path}/{dirname}-context.md`.

### 4. Report
After all agents complete, summarize:
- **Created:** N new context files
- **Updated:** N refreshed context files
- **Skipped:** N up-to-date directories
- **Errors:** N failures (if any)

List the paths of all created/updated context files.
