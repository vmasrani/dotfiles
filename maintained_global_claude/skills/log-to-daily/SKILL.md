---
name: log-to-daily
description: Summarize the current Claude Code session and append it to today's Dendron daily log note. Creates the note if it doesn't exist.
---

# Log to Daily

Summarize the current session and append it to today's daily log note in the Dendron vault.

## Configuration

- **Vault path (primary):** `/Users/vmasrani/dev/dendron/vault/`
- **Fallback path (remote):** `~/dotfiles/local/daily-logs/`
- **Note pattern:** `daily.log.YYYY.MM.DD.md` (Dendron dot-notation)
- **Multiple calls per day:** Append with timestamps to the same note

## Step 1 — Determine today's note path

First, check if the Dendron vault exists:

```bash
test -d /Users/vmasrani/dev/dendron/vault && echo "vault" || echo "fallback"
```

- If `vault` → use `/Users/vmasrani/dev/dendron/vault/`
- If `fallback` → use `~/dotfiles/local/daily-logs/` (create the directory if needed via `mkdir -p`)

Compute the note path using today's date within the chosen directory:

```
<chosen_dir>/daily.log.YYYY.MM.DD.md
```

For example: `daily.log.2025.10.22.md`

Tell the user which location is being used (vault or fallback).

## Step 2 — If the note does NOT exist, create it

Create the file with Dendron-compatible frontmatter (used for both locations so fallback logs can be moved into the vault later). Generate the `id` using Python:

```bash
python3 -c "import secrets; print(secrets.token_hex(12)[:23])"
```

Generate Unix millisecond timestamps:

```bash
python3 -c "import time; print(int(time.time() * 1000))"
```

The file must have this exact structure:

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

Match the date heading format from existing `daily.journal.*` notes (e.g., `# Wednesday, Oct 22 2025`).

Write the file using the Write tool.

## Step 3 — If the note already exists, update the `updated` timestamp

Read the existing file. Replace the `updated:` line in the frontmatter with the current Unix ms timestamp using the Edit tool.

## Step 4 — Summarize the session

Review the full conversation history and produce a session log section. Focus on **outcomes, not activities**. Be concise.

## Step 5 — Append the session log

Use the Edit tool to append the following section at the end of the note. Find the last line of the file and append after it.

```markdown

## Session Log - HH:MM

**Focus:** 1-2 sentence summary of what the session accomplished.

### Completed
- Concrete outcome 1
- Concrete outcome 2

### Decisions Made
| Decision | Rationale |
|----------|-----------|
| decision 1 | why |

### Files Modified
- `path/to/file` - change description

### Next Steps
- [ ] follow-up task 1
- [ ] follow-up task 2
```

**Rules for the session log:**
- **Completed:** List concrete deliverables, not activities. "Added OAuth login flow" not "Worked on auth".
- **Decisions Made:** Only include decisions where alternatives were considered. Skip if none.
- **Files Modified:** List every file created or edited during the session. Use relative paths from the project root.
- **Next Steps:** Only include items that were explicitly discussed or are clearly implied. Skip if none.
- Omit any section (except Focus and Completed) if it would be empty.

## Step 6 — Confirm

Tell the user the note path and a one-line summary of what was logged.
