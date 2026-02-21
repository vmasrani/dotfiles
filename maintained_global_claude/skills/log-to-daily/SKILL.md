---
name: log-to-daily
description: Process all Claude Code sessions for a day (or backfill) and write structured daily log notes to the Dendron vault. Run once per day from any session.
---

# Log to Daily

Scan ALL Claude Code sessions across all projects, summarize each via sonnet subagents, and write Dendron daily log notes. Works from any session — doesn't depend on current conversation history.

## Configuration

- **Tool:** `~/tools/claude-session-digest` (Python CLI — scanning, filtering, transcript extraction)
- **Summarization:** sonnet subagents via Task tool (`model: "sonnet"`)
- **Vault path (primary):** `/Users/vmasrani/dev/dendron/vault/`
- **Fallback path (remote):** `~/dotfiles/local/daily-logs/`
- **Note pattern:** `daily.log.YYYY.MM.DD.md` (Dendron dot-notation)

## Step 1 — Show status

Run the status command to see which dates have sessions and which are already logged:

```bash
~/tools/claude-session-digest status
```

Display the table to the user.

## Step 2 — Ask about scope

Based on the status table, ask the user:

- **Process today only?** (default)
- **Backfill specific dates?** Show which dates have non-trivial sessions but no log file (or fewer logged sessions than non-trivial sessions available).

Let the user pick which dates to process. Suggest dates that have sessions but are unlogged.

## Step 3 — Sync remote sessions

For each selected date, sync Claude sessions from remote hosts:

```bash
~/tools/claude-session-digest sync YYYY-MM-DD
```

This parses zsh history for SSH commands on that date, discovers remote hosts,
and rsyncs their `~/.claude/projects/` to `~/.claude/remote-sessions/{host}/`.

Show the user the sync results (which hosts were found, which were reachable,
how many sessions were pulled). Unreachable hosts are skipped automatically.

After syncing, remote sessions will be included in subsequent extract/status commands.

## Step 4 — Extract transcripts

For each date the user selected, run:

```bash
~/tools/claude-session-digest extract YYYY-MM-DD
```

This outputs a JSON array to stdout. Each element has: `session_id`, `project_name`, `project_path`, `slug`, `git_branch`, `time_hhmm`, `remote_host`, `transcript`.

Capture this output for the next step.

## Step 5 — Summarize via sonnet subagents

For each session in the extracted JSON, spawn a **sonnet** subagent using the Task tool with `model: "sonnet"` and `subagent_type: "general-purpose"`.

**Spawn sessions in parallel** — launch all Task tool calls for a given date in a single message (up to the tool call limit). If there are more sessions than the tool call limit, batch them.

Each subagent prompt should be:

```
Summarize this Claude Code session transcript into a structured markdown section. Output ONLY the markdown — no preamble, no code fence.

Session: {slug} | Project: {project_name} | Branch: {git_branch} | Time: {time_hhmm} | Host: {remote_host or "local"}

TEMPLATE (omit empty sections except Focus and Completed):

## Session Log - {time_hhmm} [{project_name}]

**Focus:** 1-2 sentence summary of what was accomplished.

### Completed
- Concrete outcome (not activity)

### Decisions Made
| Decision | Rationale |
|----------|-----------|

### Files Modified
- `path/to/file` - change description

### Next Steps
- [ ] follow-up task

RULES:
- Completed: deliverables not activities. "Added OAuth login flow" not "Worked on auth".
- Decisions Made: only if alternatives were considered.
- Next Steps: MUST use `- [ ]` checkbox format.
- Omit any section (except Focus and Completed) if it would be empty.
- If the session has no meaningful work outcomes — just greetings, health checks, debugging that went nowhere, or failed attempts without resolution — respond with exactly: SKIP

TRANSCRIPT:
{transcript}
```

Collect all subagent responses. Drop any that returned "SKIP".

## Step 6 — Write daily log files

For each date, determine the vault path:

```bash
test -d /Users/vmasrani/dev/dendron/vault && echo "vault" || echo "fallback"
```

- If `vault` → use `/Users/vmasrani/dev/dendron/vault/`
- If `fallback` → use `~/dotfiles/local/daily-logs/` (create directory if needed via `mkdir -p`)

Compute the note path: `<vault>/daily.log.YYYY.MM.DD.md`

### If the note does NOT exist — create it

Generate the Dendron frontmatter. Use Python for ID and timestamps:

```bash
uv run python -c "import secrets; print(secrets.token_hex(12)[:23])"
```

```bash
uv run python -c "import time; print(int(time.time() * 1000))"
```

Create the file with this exact structure using the Write tool:

```markdown
---
id: <23-char random alphanumeric>
title: 'YYYY-MM-DD'
desc: ''
updated: <unix ms timestamp>
created: <unix ms timestamp>
traitIds:
  - journalNote
---

# DayOfWeek, Mon DD YYYY
```

Match the date heading format from existing `daily.journal.*` notes (e.g., `# Thursday, Feb 19 2026`).

Then append the collected markdown summaries after the heading.

### If the note already exists — update it

1. Read the existing file.
2. Replace the `updated:` line in the frontmatter with the current Unix ms timestamp using the Edit tool.
3. Check existing `## Session Log` headings to avoid appending duplicates. Compare the time+project in each heading against what the subagents produced. Only append new sessions.
4. Append the new session markdown at the end of the file using the Edit tool.

## Step 7 — Confirm

Report to the user:
- Which files were created vs updated
- How many sessions were logged per day
- The vault path used
- A one-line summary per day of what was logged
