---
name: gws
description: >-
  Google Workspace CLI power-user skill for managing Gmail, Drive, Calendar, Tasks,
  Sheets, Docs, and Chat from the terminal via the `gog` CLI. Use this skill whenever
  the user mentions email, inbox, gmail, send email, check email, archive, calendar,
  agenda, meetings, schedule, drive, upload, download, google docs, spreadsheet, sheets,
  tasks, todo, google workspace, gws, gog, or any operation involving their Google
  Workspace account. Also use when the user asks to triage email, search inbox, forward
  a message, draft a reply, create a calendar event, upload a file to drive, read a
  spreadsheet, or manage tasks. Even for simple requests like "what's on my calendar"
  or "any new emails?" — this skill has the exact commands.
---

# Google Workspace CLI (`gog`)

The `gog` CLI provides full access to Google Workspace from the terminal. Binary: `/opt/homebrew/bin/gog` (`gogcli` v0.12+).

> Note: the skill directory is still named `gws` for trigger compatibility, but the underlying tool is `gog`. The older `gws` (`googleworkspace-cli`) binary is also installed but its OAuth token has expired — always use `gog`.

## Command Pattern

```
gog <service> <command> [args] [flags]      # e.g. gog gmail send --to ...
gog <top-level-alias> [args] [flags]         # e.g. gog upload (= drive upload)
```

Top-level aliases for common ops: `send`, `ls`, `search`, `upload` (`up`,`put`), `download` (`dl`), `open`, `login`, `status`, `me`/`whoami`.

## Global Flags

| Flag | Purpose |
|------|---------|
| `-j, --json` | JSON output (best for scripting/`jq`) |
| `-p, --plain` | Stable TSV output, no colors |
| `--results-only` | In JSON mode, drop envelope (e.g. `nextPageToken`) |
| `--select=a,b,c` | In JSON mode, project specific fields |
| `-n, --dry-run` | Print intended action, do not execute |
| `-y, --force` | Skip confirmations on destructive ops |
| `--no-input` | Never prompt; fail instead (CI-safe) |
| `-a, --account EMAIL` | Override default account |
| `gog schema [command...]` | Machine-readable command/flag schema |

Default output (no `-j`/`-p`) is human-readable text.

## Auth & Status

```bash
gog status                                   # show config, account, credentials
gog whoami                                   # show profile
gog login user@example.com                   # authorize new account
gog logout user@example.com                  # remove stored refresh token
gog auth services                            # list authorized API scopes
```

If a command returns a 401/auth error, run `gog login <email>` to re-authorize.

---

## Gmail

### Search / triage

`gog` has no `+triage` helper — use `gmail messages search` (or its alias `gog gmail search`) with Gmail query syntax.

```bash
gog gmail search 'is:unread label:inbox' --max 20
gog gmail search 'from:boss is:unread' --max 50
gog gmail search 'has:attachment newer_than:3d' -p          # parseable TSV
gog gmail search 'is:unread' -j --results-only | jq '.[].subject'
```

Useful flags on `gmail search`: `--max N`, `--all` (paginate), `--include-body`, `--fail-empty` (exit 3 on no results), `-z TZ` / `--local` (timezone).

### Read a message

```bash
gog gmail get MSG_ID                         # full message (default)
gog gmail get MSG_ID --format metadata --headers 'From,Subject,Date'
gog gmail get MSG_ID --format raw             # raw RFC 822
gog gmail get MSG_ID -j | jq '.payload.headers'
gog gmail attachment MSG_ID ATTACH_ID -o file.pdf
```

### Read a thread (all messages in conversation)

```bash
gog gmail thread get THREAD_ID --full
gog gmail thread get THREAD_ID --download --out-dir ./attachments
gog gmail thread attachments THREAD_ID
```

### Send email

```bash
gog gmail send --to alice@example.com --subject 'Hello' --body 'Hi Alice!'
gog gmail send --to alice@example.com --subject 'Report' --body-html '<b>See attached</b>'
gog gmail send --to alice@example.com --subject 'Files' --body 'Attached' \
  --attach report.pdf --attach data.csv
gog gmail send --to a@ex.com --cc b@ex.com --bcc c@ex.com --subject 'Team' --body 'FYI'
gog gmail send --to alice@example.com --subject 'Long' --body-file ./body.txt
echo 'piped body' | gog gmail send --to alice@example.com --subject 'Hi' --body-file -
gog gmail send --from alias@example.com --to ... --subject ... --body ...   # send-as alias
```

> `gog` has no `--draft` flag on `send`. To save a draft, use `gog gmail drafts create` with the same flags as `send`.

### Reply / Reply All

Replies are just `send` with `--reply-to-message-id` (or `--thread-id`):

```bash
gog gmail send --reply-to-message-id MSG_ID --to alice@example.com \
  --subject 'Re: ...' --body 'Thanks, got it!'

gog gmail send --reply-to-message-id MSG_ID --reply-all --subject 'Re: ...' --body 'Sounds good'
gog gmail send --reply-to-message-id MSG_ID --quote --subject 'Re: ...' --body 'See below:'
```

`--reply-all` auto-populates To/Cc from the original. To drop a recipient, omit `--reply-all` and set `--to`/`--cc` explicitly.

### Forward

There is no dedicated forward command. Two options:

1. Pull the original with `gog gmail get MSG_ID -j`, build a new message with quoted body, and `gog gmail send --to dave@example.com --subject 'Fwd: ...' --body-file ...`.
2. Use `gog gmail thread get THREAD_ID --download --out-dir ./tmp`, then send a new message with `--attach` for each file.

### Archive / Read / Trash

```bash
gog gmail archive MSG_ID                     # remove INBOX label
gog gmail archive MSG_ID1 MSG_ID2 MSG_ID3    # bulk
gog gmail mark-read MSG_ID
gog gmail unread MSG_ID
gog gmail trash MSG_ID                       # move to trash (recoverable)
gog gmail batch delete MSG_ID1 MSG_ID2       # PERMANENT delete
```

Bulk archive by query:

```bash
gog gmail search 'older_than:7d label:inbox -is:unread' --all -j --results-only \
  | jq -r '.[].id' \
  | xargs gog gmail archive
```

### Labels

```bash
gog gmail labels list
gog gmail labels get LABEL_ID
gog gmail labels create 'MyLabel'
gog gmail labels rename OLD_NAME NEW_NAME
gog gmail labels delete LABEL_ID

# Apply / remove labels (operates on threads):
gog gmail labels modify THREAD_ID --add LABEL_ID
gog gmail labels modify THREAD_ID --remove LABEL_ID

# Single-message label change:
gog gmail messages modify MSG_ID --add STARRED
gog gmail messages modify MSG_ID --remove UNREAD
```

System label IDs: `INBOX`, `UNREAD`, `STARRED`, `IMPORTANT`, `TRASH`, `SPAM`, `SENT`, `DRAFT`.

### Drafts

```bash
gog gmail drafts list
gog gmail drafts create --to alice@example.com --subject 'Draft' --body 'Review this'
gog gmail drafts get DRAFT_ID
gog gmail drafts update DRAFT_ID --body 'New body'
gog gmail drafts send DRAFT_ID
gog gmail drafts delete DRAFT_ID
```

### Gmail search syntax

Standard Gmail operators work in `gog gmail search`:

| Operator | Example |
|----------|---------|
| `from:` / `to:` / `subject:` | `from:alice@example.com` |
| `has:attachment` / `filename:pdf` | `has:attachment` |
| `is:unread` / `is:starred` / `is:important` | `is:unread` |
| `label:` / `in:` | `label:work`, `in:trash` |
| `older_than:` / `newer_than:` | `older_than:7d` |
| `after:` / `before:` | `after:2026/01/01` |
| `larger:` | `larger:5M` |
| `"exact phrase"` | `"project update"` |
| `-` (exclude), `OR` | `from:alice -subject:test` |

---

## Drive

### Upload

```bash
gog upload ./report.pdf                                  # alias for `drive upload`
gog drive upload ./report.pdf
gog drive upload ./report.pdf --parent FOLDER_ID
gog drive upload ./data.csv --name 'Q1 Sales Data.csv'
gog drive upload ./new.pdf --replace EXISTING_FILE_ID    # overwrite content
gog drive upload ./img.bin --mime-type image/png         # override inference
```

### List / search

```bash
gog ls                                       # list root (alias)
gog drive ls --max 50
gog drive ls --parent FOLDER_ID
gog drive ls --query "name contains 'report'"
gog drive ls --no-all-drives                 # My Drive only

gog search 'quarterly report'                # full-text search (alias)
gog drive search 'budget' --max 25
gog drive search "mimeType='application/pdf'" --raw-query
```

`--raw-query` switches to the Drive query language (same as `--query` on `ls`).

### Download

```bash
gog download FILE_ID --out report.pdf                       # any file (alias)
gog drive download FILE_ID --out ./report.pdf

# Export Google-native files (Docs/Sheets/Slides) — pick a format:
gog drive download DOC_ID --format pdf --out doc.pdf
gog drive download SHEET_ID --format csv --out data.csv
gog drive download SHEET_ID --format xlsx --out data.xlsx
gog drive download SLIDE_ID --format pptx --out deck.pptx
```

### File operations

```bash
gog drive get FILE_ID                                     # metadata
gog drive copy FILE_ID 'Copy of Report'
gog drive move FILE_ID --parent NEW_FOLDER_ID
gog drive rename FILE_ID 'New Name.pdf'
gog drive delete FILE_ID                                  # to trash
gog drive delete FILE_ID --permanent                      # permanent
gog drive mkdir 'New Folder'
gog drive mkdir 'Subfolder' --parent PARENT_FOLDER_ID
gog drive url FILE_ID [FILE_ID ...]                       # printable web URLs
gog open FILE_ID                                          # alias: print web URL
```

### Sharing

```bash
gog drive share FILE_ID --email alice@example.com --role reader
gog drive share FILE_ID --email bob@example.com --role writer --notify
gog drive share FILE_ID --anyone --role reader            # public link
gog drive permissions FILE_ID                             # list current perms
gog drive unshare FILE_ID PERMISSION_ID
```

### Drive query language

Use in `--query` (on `ls`) or `--raw-query` (on `search`):

| Query | Finds |
|-------|-------|
| `name contains 'keyword'` | Files with keyword in name |
| `name = 'exact name.pdf'` | Exact filename |
| `mimeType = 'application/pdf'` | PDFs |
| `mimeType = 'application/vnd.google-apps.spreadsheet'` | Google Sheets |
| `mimeType = 'application/vnd.google-apps.document'` | Google Docs |
| `mimeType = 'application/vnd.google-apps.folder'` | Folders |
| `'FOLDER_ID' in parents` | Files in specific folder |
| `modifiedTime > '2026-01-01T00:00:00'` | Modified after |
| `trashed = false` | Not in trash |
| `sharedWithMe = true` | Shared with me |
| `starred = true` | Starred |

Combine with `and`: `name contains 'report' and mimeType = 'application/pdf' and modifiedTime > '2026-01-01'`.

### Extracting file IDs from URLs

```
Google Docs:    https://docs.google.com/document/d/FILE_ID/edit
Google Sheets:  https://docs.google.com/spreadsheets/d/FILE_ID/edit
Google Slides:  https://docs.google.com/presentation/d/FILE_ID/edit
Drive file:     https://drive.google.com/file/d/FILE_ID/view
```

---

## Calendar

### View events / agenda

```bash
gog calendar events --today
gog calendar events --tomorrow
gog calendar events --week
gog calendar events --days 7                              # next 7 days
gog calendar events --from 2026-04-01 --to 2026-04-07
gog calendar events --cal Work --today
gog calendar events --all --today                         # across all calendars
gog calendar events --query 'standup' --week
```

### Create event

```bash
gog calendar create primary \
  --summary 'Team Standup' \
  --from '2026-04-01T09:00:00-07:00' \
  --to   '2026-04-01T09:30:00-07:00'

# With attendees and Meet link
gog calendar create primary \
  --summary 'Design Review' \
  --from '2026-04-01T14:00:00-07:00' \
  --to   '2026-04-01T15:00:00-07:00' \
  --attendees 'alice@example.com,bob@example.com' \
  --with-meet \
  --location 'Room 301' \
  --description 'Review Q2 designs'

# All-day event (date-only)
gog calendar create primary --all-day --summary 'Holiday' --from 2026-07-04 --to 2026-07-05
```

Times must be RFC 3339 with timezone offset (e.g. `-07:00` for PDT). The first positional arg is the calendar ID — use `primary` for your own calendar.

### Update / delete

```bash
gog calendar update primary EVENT_ID --summary 'New Title' --location 'Room 5'
gog calendar delete primary EVENT_ID
gog calendar respond  primary EVENT_ID --status accepted     # rsvp
```

### Other

```bash
gog calendar event primary EVENT_ID                       # get one event
gog calendar freebusy --from 2026-04-01 --to 2026-04-02   # availability
gog calendar conflicts --week                             # find overlapping events
gog calendar focus-time --from ... --to ... primary       # block focus time
gog calendar out-of-office --from ... --to ... primary    # OOO
gog calendar working-location --from ... --to ... --type home primary
gog calendar users                                        # list workspace users
```

---

## Tasks

```bash
gog tasks lists list                                      # show all task lists
gog tasks list TASKLIST_ID                                # tasks in a list
gog tasks list @default                                   # default list

gog tasks add TASKLIST_ID --title 'Buy groceries' \
  --notes 'Milk, eggs, bread' --due 2026-04-01

gog tasks add @default --title 'Sub-item' --parent PARENT_TASK_ID  # subtask

gog tasks update TASKLIST_ID TASK_ID --title 'Renamed' --due 2026-04-05
gog tasks done   TASKLIST_ID TASK_ID                      # complete
gog tasks undo   TASKLIST_ID TASK_ID                      # uncomplete
gog tasks delete TASKLIST_ID TASK_ID
gog tasks clear  TASKLIST_ID                              # purge completed
```

---

## Sheets

```bash
gog sheets read SHEET_ID 'Sheet1!A1:D10'
gog sheets read SHEET_ID 'Sheet1!A1:D10' -p               # TSV output
gog sheets read SHEET_ID 'Sheet1' -j                      # whole sheet as JSON

# Append rows (USER_ENTERED parses formulas; RAW writes literally)
gog sheets append SHEET_ID 'Sheet1' --values-json '[["Alice","100",true]]'
gog sheets append SHEET_ID 'Sheet1' --values-json '[["Alice",100],["Bob",200]]' --input RAW

gog sheets create 'Q2 Budget'                             # new spreadsheet
gog sheets copy SHEET_ID 'Q2 Budget — Copy'
gog sheets export SHEET_ID --format csv  --out data.csv
gog sheets export SHEET_ID --format xlsx --out data.xlsx
gog sheets export SHEET_ID --format pdf  --out data.pdf

gog sheets metadata SHEET_ID                              # tabs, IDs, ranges
gog sheets add-tab SHEET_ID 'Notes'
gog sheets rename-tab SHEET_ID 'Sheet1' 'Data'
gog sheets delete-tab SHEET_ID 'Notes' --force
gog sheets find-replace SHEET_ID 'old text' 'new text'
```

Wrap ranges in single quotes — the `!` in `Sheet1!A1:D10` triggers bash history expansion otherwise.

---

## Docs

```bash
gog docs cat DOC_ID                                       # plain text
gog docs cat DOC_ID > doc.txt
gog docs info DOC_ID                                      # metadata
gog docs structure DOC_ID                                 # numbered paragraphs

gog docs create 'Meeting Notes - April 1'

# Write content
gog docs write DOC_ID --text 'Replaces document body'
gog docs write DOC_ID --append --text 'Appended paragraph'
gog docs write DOC_ID --file ./notes.md
echo 'piped' | gog docs write DOC_ID --append --file -

# Insert at a specific index (use `gog docs structure` to find indices)
gog docs insert DOC_ID 'Inline text' --index 42
gog docs delete DOC_ID --start 100 --end 200

# Find / replace
gog docs find-replace DOC_ID 'old' 'new'
gog docs find-replace DOC_ID 'old' 'new' --first
gog docs sed DOC_ID 's/foo/bar/g'                         # regex sed-style

gog docs export DOC_ID --format pdf --out doc.pdf         # pdf|docx|txt|md
gog docs copy DOC_ID 'New Title'
gog docs clear DOC_ID                                     # erase all content
```

---

## Chat

```bash
gog chat spaces list                                      # all spaces
gog chat spaces find 'Engineering'                        # by display name
gog chat spaces create 'New Space'

gog chat messages list spaces/SPACE_ID --max 20
gog chat messages send spaces/SPACE_ID --text 'Deploy complete!'
gog chat messages react spaces/SPACE_ID/messages/MSG_ID '👍'

gog chat dm send alice@example.com --text 'Hey, ping me'
gog chat dm space alice@example.com                       # find/create DM space
```

---

## Other Services

| Service | Status | Notes |
|---------|--------|-------|
| Slides | Available | `gog slides --help` |
| Forms | Available | `gog forms --help` |
| Apps Script | Available | `gog appscript --help` |
| Classroom | Available | `gog classroom --help` |
| Groups | Available | `gog groups --help` |
| People (directory) | Available | `gog people search`, `gog me` |
| Contacts | Available | `gog contacts list/search/create` |
| Keep | Workspace-only | `gog keep --help` |
| Admin (Directory API) | Requires DWD | `gog admin --help` |

---

## Power-User Patterns

### Pipe and filter with jq

```bash
# Get all unread subjects
gog gmail search 'is:unread' -j --results-only | jq -r '.[].subject'

# Get file IDs for all PDFs
gog drive search "mimeType='application/pdf'" --raw-query --max 100 -j --results-only \
  | jq -r '.[] | "\(.id)\t\(.name)"'

# Get this week's event titles
gog calendar events --week -j --results-only | jq -r '.[].summary'
```

### Bulk operations

```bash
# Archive all newsletters older than 30 days
gog gmail search 'label:newsletters older_than:30d label:inbox' --all -j --results-only \
  | jq -r '.[].id' \
  | xargs -n 50 gog gmail archive

# Trash all messages from a sender
gog gmail search 'from:noreply@spammy.com' --all -j --results-only \
  | jq -r '.[].id' \
  | xargs -n 50 gog gmail trash
```

> ⚠️ The naive `search --all | xargs` patterns above are fine for hundreds of
> messages but **break at scale** (thousands+): `gog gmail search` enriches every
> result (1 API call each), so `--all` blasts past Gmail's burst limit
> (~250 quota units/user/**second**) and 429s. They also archive at the *message*
> level, so **multi-message threads** (bundled Uber/Airbnb/GitHub notifications)
> stay in the inbox. For big jobs use the bundled helper instead.

### `gog-bulk` — rate-limit-safe bulk ops (use for thousands of messages)

Script lives next to this skill: `gws/gog-bulk` (executable). It auto-throttles +
retries on 429, operates at the **thread** level, and passes ids zsh-safely.

```bash
SKILL=~/.codex/skills/gws/gog-bulk

# Count first (throttled, read-only)
$SKILL count   'is:unread in:inbox category:promotions' -a vadmas@gmail.com

# Archive + mark read everything bulk, keeping personal + starred
$SKILL clean   'is:unread in:inbox -category:personal -is:starred' -a vadmas@gmail.com

# Other actions: archive | read | clean | unread | star | trash | label | modify | pull
$SKILL label   'from:substack.com' --add Newsletters -a vadmas@gmail.com
$SKILL trash   'from:spammy.com' -y
$SKILL pull    'is:unread in:inbox' out.json          # snapshot to JSON for analysis
```

Add `-n/--dry-run` to preview the match count without changing anything; `-y` skips
the confirm prompt. **Daily quota is ~1e9 units (effectively unlimited)** — the only
real constraint is *pacing*, which this handles. Gmail's unread/search counters lag
minutes after bulk ops; verify with `gog gmail get <id> --format metadata`, not the badge.

### Drafts as scheduling primitive

`gog` has no native scheduled send. Pattern: create a draft now, send later via cron or manually:

```bash
gog gmail drafts create --to alice@example.com --subject 'Reminder' --body '...'
# later:
gog gmail drafts send DRAFT_ID
```

### Schema introspection

When you need exact flags / params for any command:

```bash
gog schema                                                # full schema (large)
gog schema gmail send
gog schema drive upload
gog schema calendar create
```

### Parseable output for scripting

Prefer `-p` (TSV) for shell pipelines and `-j --results-only` for `jq` work. Default output is human-readable text and may change between versions.

```bash
gog gmail search 'is:unread' -p | awk -F'\t' '{print $1, $3}'
gog drive ls -j --results-only --select 'id,name,mimeType' | jq .
```

---

## Important Notes

- All commands accept `-n/--dry-run` — use before any destructive op (`delete`, `trash`, bulk `modify`).
- Default account is configured at `~/Library/Application Support/gogcli/config.json`. Override per-call with `-a EMAIL`.
- For Gmail labels, use `gog gmail labels modify <THREAD_ID>` (operates on threads) or `gog gmail messages modify <MSG_ID>` (single message).
- Calendar times must be RFC 3339 with timezone (e.g. `2026-04-01T09:00:00-07:00`); calendar ID `primary` = your default calendar.
- File IDs can be extracted from Google Workspace URLs (see Drive section).
- The legacy `gws` (`googleworkspace-cli`) binary is also installed but its OAuth token is stale — do not use it; if you encounter examples using `gws ... +helper`, translate to the `gog` equivalents above.
