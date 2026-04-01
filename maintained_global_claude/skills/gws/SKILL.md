---
name: gws
description: >-
  Google Workspace CLI power-user skill for managing Gmail, Drive, Calendar, Tasks,
  Sheets, Docs, and Chat from the terminal. Use this skill whenever the user mentions
  email, inbox, gmail, send email, check email, archive, calendar, agenda, meetings,
  schedule, drive, upload, download, google docs, spreadsheet, sheets, tasks, todo,
  google workspace, gws, or any operation involving their Google Workspace account.
  Also use when the user asks to triage email, search inbox, forward a message,
  draft a reply, create a calendar event, upload a file to drive, read a spreadsheet,
  or manage tasks. Even for simple requests like "what's on my calendar" or "any new
  emails?" — this skill has the exact commands.
---

# Google Workspace CLI (`gws`)

The `gws` CLI provides full access to Google Workspace from the terminal. Binary: `/opt/homebrew/bin/gws`.

## Command Pattern

```
gws <service> +<helper>   [flags]     # helper commands (easy mode)
gws <service> <resource> <method> [flags]  # raw API access (full control)
```

## Global Flags

| Flag | Purpose |
|------|---------|
| `--dry-run` | Preview request without executing — use before destructive ops |
| `--format json\|table\|yaml\|csv` | Output format (default: json) |
| `--page-all` | Auto-paginate, streaming NDJSON |
| `--page-limit N` | Max pages to fetch (default: 10) |
| `-o, --output PATH` | Save binary response to file |
| `gws schema SERVICE.RESOURCE.METHOD` | Inspect any API's parameters |

## Access Status

| Service | Status | Notes |
|---------|--------|-------|
| Gmail | Full | Send, read, modify, labels, triage |
| Drive | Full | Upload, download, export, CRUD |
| Calendar | Full | Events, agenda, create |
| Tasks | Full | Lists, CRUD |
| Sheets | Full | Read, append, create |
| Docs | Full | Read, append, create |
| Chat | Full | Send messages, list spaces |
| People/Contacts | **No access** | 403 insufficient scopes |
| Keep | **No access** | 403 insufficient scopes |

---

## Gmail

### Triage (check inbox)

```bash
gws gmail +triage                                    # unread inbox summary (table)
gws gmail +triage --max 50                           # show more messages
gws gmail +triage --query 'from:boss is:unread'      # filtered triage
gws gmail +triage --labels                           # include label names
gws gmail +triage --format json | jq '.[].subject'   # pipe subjects
```

### Read a message

```bash
gws gmail +read --id MSG_ID                   # plain text body
gws gmail +read --id MSG_ID --headers         # include From, To, Subject, Date
gws gmail +read --id MSG_ID --html            # HTML body
gws gmail +read --id MSG_ID --format json     # full JSON
```

### Send email

```bash
gws gmail +send --to alice@example.com --subject 'Hello' --body 'Hi Alice!'
gws gmail +send --to alice@example.com --subject 'Report' --body '<b>See attached</b>' --html
gws gmail +send --to alice@example.com --subject 'Files' --body 'Attached' -a report.pdf -a data.csv
gws gmail +send --to a@ex.com --cc b@ex.com --bcc c@ex.com --subject 'Team' --body 'FYI'
gws gmail +send --to alice@example.com --subject 'Draft' --body 'Review this' --draft  # save as draft
gws gmail +send --to alice@example.com --subject 'Hi' --body 'Hello' --from alias@example.com
```

### Reply

```bash
gws gmail +reply --message-id MSG_ID --body 'Thanks, got it!'
gws gmail +reply --message-id MSG_ID --body 'Looping in Carol' --cc carol@example.com
gws gmail +reply --message-id MSG_ID --body '<b>Acknowledged</b>' --html
gws gmail +reply --message-id MSG_ID --body 'Updated version' -a updated.docx
gws gmail +reply --message-id MSG_ID --body 'Draft for review' --draft
```

### Reply All

```bash
gws gmail +reply-all --message-id MSG_ID --body 'Sounds good!'
gws gmail +reply-all --message-id MSG_ID --body 'Updated' --remove bob@example.com  # drop a recipient
gws gmail +reply-all --message-id MSG_ID --body 'Adding Eve' --cc eve@example.com
```

### Forward

```bash
gws gmail +forward --message-id MSG_ID --to dave@example.com
gws gmail +forward --message-id MSG_ID --to dave@example.com --body 'FYI see below'
gws gmail +forward --message-id MSG_ID --to dave@example.com --no-original-attachments
gws gmail +forward --message-id MSG_ID --to dave@example.com -a extra-notes.pdf
gws gmail +forward --message-id MSG_ID --to dave@example.com --draft  # save as draft
```

### Archive

Archiving removes the INBOX label. There is no dedicated archive command — use modify:

```bash
# Archive a single message
gws gmail users messages modify \
  --params '{"userId":"me","id":"MSG_ID"}' \
  --json '{"removeLabelIds":["INBOX"]}'

# Bulk archive — e.g., all read messages older than 7 days
gws gmail users messages list \
  --params '{"userId":"me","q":"older_than:7d label:inbox -is:unread","maxResults":500}' \
  --format json \
  | jq -r '.messages[].id' \
  | while read id; do
      gws gmail users messages modify \
        --params "{\"userId\":\"me\",\"id\":\"$id\"}" \
        --json '{"removeLabelIds":["INBOX"]}'
    done
```

### Trash / Delete

```bash
gws gmail users messages trash --params '{"userId":"me","id":"MSG_ID"}'
gws gmail users messages delete --params '{"userId":"me","id":"MSG_ID"}'  # permanent!
```

### Labels

```bash
# List all labels
gws gmail users labels list --params '{"userId":"me"}' --format table

# Create a label
gws gmail users labels create --params '{"userId":"me"}' --json '{"name":"MyLabel"}'

# Apply label to message
gws gmail users messages modify \
  --params '{"userId":"me","id":"MSG_ID"}' \
  --json '{"addLabelIds":["LABEL_ID"]}'

# Remove label
gws gmail users messages modify \
  --params '{"userId":"me","id":"MSG_ID"}' \
  --json '{"removeLabelIds":["LABEL_ID"]}'

# Common system label IDs:
#   INBOX, UNREAD, STARRED, IMPORTANT, TRASH, SPAM, SENT, DRAFT
# Star a message:    addLabelIds: ["STARRED"]
# Mark as read:      removeLabelIds: ["UNREAD"]
# Mark as unread:    addLabelIds: ["UNREAD"]
```

### Search messages (raw API)

```bash
gws gmail users messages list --params '{"userId":"me","q":"QUERY","maxResults":20}' --format json
```

### Gmail Search Syntax

| Operator | Example | What it finds |
|----------|---------|---------------|
| `from:` | `from:alice@example.com` | From specific sender |
| `to:` | `to:bob@example.com` | To specific recipient |
| `subject:` | `subject:invoice` | Subject contains word |
| `has:attachment` | `has:attachment` | Has any attachment |
| `filename:` | `filename:pdf` | Attachment by type/name |
| `is:unread` | `is:unread` | Unread messages |
| `is:starred` | `is:starred` | Starred messages |
| `label:` | `label:work` | Has specific label |
| `in:` | `in:trash` | In specific folder |
| `older_than:` | `older_than:7d` | Older than 7 days (d/m/y) |
| `newer_than:` | `newer_than:1d` | Newer than 1 day |
| `after:` | `after:2026/01/01` | After date |
| `before:` | `before:2026/03/01` | Before date |
| `larger:` | `larger:5M` | Larger than 5MB |
| `has:drive` | `has:drive` | Contains Drive links |
| `"exact phrase"` | `"project update"` | Exact phrase match |
| `-` | `-from:noreply` | Exclude matches |
| `OR` | `from:a OR from:b` | Either condition |

Combine freely: `from:alice is:unread has:attachment newer_than:3d`

---

## Drive

### Upload

```bash
gws drive +upload ./report.pdf
gws drive +upload ./report.pdf --parent FOLDER_ID
gws drive +upload ./data.csv --name 'Q1 Sales Data.csv'
```

### List files

```bash
gws drive files list --params '{"pageSize":20}' --format table
gws drive files list --params '{"q":"name contains '\''report'\''","pageSize":10}' --format table
gws drive files list --params '{"q":"mimeType='\''application/pdf'\''","pageSize":10}' --format table
gws drive files list --params '{"q":"'\''FOLDER_ID'\'' in parents"}' --format table
```

### Download

```bash
# Regular files (PDFs, images, etc.)
gws drive files get --params '{"fileId":"FILE_ID","alt":"media"}' -o report.pdf

# Export Google Docs as PDF
gws drive files export --params '{"fileId":"FILE_ID","mimeType":"application/pdf"}' -o doc.pdf

# Export Google Sheet as CSV
gws drive files export --params '{"fileId":"FILE_ID","mimeType":"text/csv"}' -o data.csv

# Export Google Slides as PPTX
gws drive files export --params '{"fileId":"FILE_ID","mimeType":"application/vnd.openxmlformats-officedocument.presentationml.presentation"}' -o slides.pptx
```

### File operations

```bash
# Get file metadata
gws drive files get --params '{"fileId":"FILE_ID"}'

# Copy
gws drive files copy --params '{"fileId":"FILE_ID"}' --json '{"name":"Copy of Report"}'

# Move (change parent folder)
gws drive files update --params '{"fileId":"FILE_ID","addParents":"NEW_FOLDER_ID","removeParents":"OLD_FOLDER_ID"}'

# Rename
gws drive files update --params '{"fileId":"FILE_ID"}' --json '{"name":"New Name.pdf"}'

# Delete (permanent)
gws drive files delete --params '{"fileId":"FILE_ID"}'

# Create folder
gws drive files create --json '{"name":"New Folder","mimeType":"application/vnd.google-apps.folder"}'

# Create folder inside another folder
gws drive files create --json '{"name":"Subfolder","mimeType":"application/vnd.google-apps.folder","parents":["PARENT_FOLDER_ID"]}'
```

### Drive Search Syntax

Use in the `q` parameter of `files list`:

| Query | What it finds |
|-------|---------------|
| `name contains 'keyword'` | Files with keyword in name |
| `name = 'exact name.pdf'` | Exact filename |
| `mimeType = 'application/pdf'` | PDFs |
| `mimeType = 'application/vnd.google-apps.spreadsheet'` | Google Sheets |
| `mimeType = 'application/vnd.google-apps.document'` | Google Docs |
| `mimeType = 'application/vnd.google-apps.folder'` | Folders |
| `'FOLDER_ID' in parents` | Files in specific folder |
| `modifiedTime > '2026-01-01T00:00:00'` | Modified after date |
| `trashed = false` | Not in trash |
| `sharedWithMe = true` | Shared with me |
| `starred = true` | Starred files |

Combine with `and`: `name contains 'report' and mimeType = 'application/pdf' and modifiedTime > '2026-01-01'`

### Extracting file IDs from URLs

```
Google Docs:   https://docs.google.com/document/d/FILE_ID/edit
Google Sheets: https://docs.google.com/spreadsheets/d/FILE_ID/edit
Google Slides: https://docs.google.com/presentation/d/FILE_ID/edit
Drive file:    https://drive.google.com/file/d/FILE_ID/view
```

---

## Calendar

### View agenda

```bash
gws calendar +agenda                                  # upcoming events (table)
gws calendar +agenda --format json                     # JSON output
gws calendar +agenda --calendar 'Work'                 # specific calendar
```

### Create event

```bash
gws calendar +insert \
  --summary 'Team Standup' \
  --start '2026-04-01T09:00:00-07:00' \
  --end '2026-04-01T09:30:00-07:00'

# With attendees and Meet link
gws calendar +insert \
  --summary 'Design Review' \
  --start '2026-04-01T14:00:00-07:00' \
  --end '2026-04-01T15:00:00-07:00' \
  --attendee alice@example.com \
  --attendee bob@example.com \
  --meet \
  --location 'Room 301' \
  --description 'Review Q2 designs'
```

Times must be RFC 3339 with timezone offset (e.g., `-07:00` for PDT).

### Raw event operations

```bash
# List events in a date range
gws calendar events list --params '{"calendarId":"primary","timeMin":"2026-04-01T00:00:00Z","timeMax":"2026-04-07T00:00:00Z","singleEvents":true,"orderBy":"startTime"}'

# Update event
gws calendar events update \
  --params '{"calendarId":"primary","eventId":"EVENT_ID"}' \
  --json '{"summary":"Updated Title","location":"New Room"}'

# Delete event
gws calendar events delete --params '{"calendarId":"primary","eventId":"EVENT_ID"}'

# List all calendars
gws calendar calendarList list --format table
```

---

## Tasks

```bash
# List task lists
gws tasks tasklists list --format table

# List tasks in default list
gws tasks tasks list --params '{"tasklist":"@default"}' --format table

# List tasks in specific list
gws tasks tasks list --params '{"tasklist":"TASKLIST_ID"}' --format table

# Create task
gws tasks tasks insert --params '{"tasklist":"@default"}' \
  --json '{"title":"Buy groceries","notes":"Milk, eggs, bread","due":"2026-04-01T00:00:00Z"}'

# Complete task
gws tasks tasks update --params '{"tasklist":"@default","task":"TASK_ID"}' \
  --json '{"status":"completed"}'

# Delete task
gws tasks tasks delete --params '{"tasklist":"@default","task":"TASK_ID"}'
```

---

## Sheets

```bash
# Read data
gws sheets +read --spreadsheet SHEET_ID --range 'Sheet1!A1:D10'
gws sheets +read --spreadsheet SHEET_ID --range 'Sheet1!A1:D10' --format table
gws sheets +read --spreadsheet SHEET_ID --range 'Sheet1' --format csv  # whole sheet

# Append single row
gws sheets +append --spreadsheet SHEET_ID --values 'Alice,100,true'

# Append multiple rows
gws sheets +append --spreadsheet SHEET_ID --json-values '[["Alice","100"],["Bob","200"]]'

# Create new spreadsheet
gws sheets spreadsheets create --json '{"properties":{"title":"Q2 Budget"}}'
```

Wrap ranges in single quotes — the `!` in `Sheet1!A1:D10` triggers bash history expansion otherwise.

---

## Docs

```bash
# Read document content
gws docs documents get --params '{"documentId":"DOC_ID"}'

# Append text to document
gws docs +write --document DOC_ID --text 'New paragraph appended here'

# Create new document
gws docs documents create --json '{"title":"Meeting Notes - April 1"}'
```

For rich formatting, use the raw `batchUpdate` API instead of `+write`.

---

## Chat

```bash
# List spaces
gws chat spaces list --format table

# Send message to a space
gws chat +send --space spaces/SPACE_ID --text 'Deploy complete!'
```

---

## Cross-Service Workflows

These combine multiple Google services in one command:

```bash
# Morning standup — today's meetings + open tasks
gws workflow +standup-report

# Meeting prep — agenda, attendees, linked docs for next meeting
gws workflow +meeting-prep
gws workflow +meeting-prep --calendar Work

# Convert email to task
gws workflow +email-to-task --message-id MSG_ID
gws workflow +email-to-task --message-id MSG_ID --tasklist TASKLIST_ID

# Weekly digest — this week's meetings + unread email count
gws workflow +weekly-digest
gws workflow +weekly-digest --format table
```

---

## Power-User Patterns

### Pipe and filter with jq

```bash
# Get all unread subjects
gws gmail +triage --format json | jq -r '.[].subject'

# Get file IDs for all PDFs
gws drive files list --params '{"q":"mimeType='\''application/pdf'\''","pageSize":100}' \
  | jq -r '.files[] | "\(.id)\t\(.name)"'

# Get all event titles this week
gws calendar events list \
  --params '{"calendarId":"primary","timeMin":"2026-03-31T00:00:00Z","timeMax":"2026-04-07T00:00:00Z","singleEvents":true}' \
  | jq -r '.items[].summary'
```

### Bulk operations

```bash
# Archive all newsletters older than 30 days
gws gmail users messages list \
  --params '{"userId":"me","q":"label:newsletters older_than:30d label:inbox","maxResults":500}' \
  --format json \
  | jq -r '.messages[].id' \
  | while read id; do
      gws gmail users messages modify \
        --params "{\"userId\":\"me\",\"id\":\"$id\"}" \
        --json '{"removeLabelIds":["INBOX"]}'
    done

# Download all attachments from a message — use +read to get the message,
# then extract attachment IDs from JSON and download each
```

### Schema introspection

When you need to figure out the exact parameters for a raw API call:

```bash
gws schema gmail.users.messages.modify
gws schema drive.files.list
gws schema calendar.events.insert --resolve-refs
gws schema sheets.spreadsheets.values.get
```

### Pagination

```bash
# Stream all results as NDJSON
gws drive files list --params '{"pageSize":100}' --page-all | jq '.files[].name'

# Limit to 3 pages
gws drive files list --params '{"pageSize":100}' --page-all --page-limit 3
```

---

## Important Notes

- Always use `"userId":"me"` in raw Gmail API params
- Calendar times must be RFC 3339 with timezone (e.g., `2026-04-01T09:00:00-07:00`)
- Use `--dry-run` before any destructive operation (delete, trash, send)
- Use `--draft` flag on `+send`, `+reply`, `+forward` to save as draft instead of sending
- People/Contacts and Keep APIs return 403 — do not attempt those services
- File IDs can be extracted from Google Workspace URLs (see Drive section)
- Pipe JSON output through `jq` for extraction and processing
