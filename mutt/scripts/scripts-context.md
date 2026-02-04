# mutt/scripts

_Last updated: 2026-01-27_

## Purpose
Collection of utility scripts for the mutt email client. Handles mail synchronization, calendar invitation rendering, HTML email display, message cleanup, and quoted-text trimming.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `mailsync` | Primary mail sync orchestrator | Runs mbsync, indexes with notmuch, notifies of new mail |
| `mailsync-daemon` | Wrapper for pm2 process manager | Infinite loop with configurable sync interval |
| `inbox-cleanup` | Email triage and auto-tagging | Tag filtering by sender, archive/news/receipt/spam categorization |
| `mutt-trim` | Quote reduction filter | Removes excess quoted text, signatures, greetings |
| `mutt-viewical` | ICS calendar viewer | Parses iCal invitations, formats attendees/dates/recurrence |
| `render-calendar-attachment.py` | Calendar invitation renderer | Pretty-prints .ics files with event details |
| `beautiful_html_render` | HTML email renderer | Converts HTML to markdown via html2text, displays with glow |

## Patterns
- **Mail sync pipeline**: mbsync (fetch) → notmuch (index) → tagging (categorize) → notification (alert)
- **ICS parsing**: Two implementations (Perl `mutt-trim` for legacy, Python `mutt-viewical` for modern invitations)
- **Idempotent cleanup**: `inbox-cleanup` supports dry-run mode, uses notmuch queries for safe batch operations
- **Daemon wrapper**: `mailsync-daemon` for periodic background execution via pm2

## Dependencies
- **External:** mbsync (mail sync), notmuch (email indexing), icalendar, pytz, tzlocal, vobject, html2text, glow, osascript (macOS)
- **Internal:** `shell/gum_utils.sh` (for styled output), `$HOME/.mutt_secrets` (sender identity), `$HOME/.config/notmuch/notmuchrc` (notmuch config)

## Entry Points
- `mailsync` — Main entry point for mail synchronization (called by daemon or cron)
- `mailsync-daemon` — Process manager entry point for continuous background sync
- `inbox-cleanup` — Standalone inbox triage tool with `--dry-run` flag

## Configuration & Secrets
- `NOTMUCH_CONFIG` — Points to `~/.config/notmuch/notmuchrc`
- `MAILSYNC_NOTIFY` — Set to `1` to enable macOS notifications (requires `~/.mutt_secrets`)
- `SYNC_INTERVAL` — Environment variable controlling mailsync-daemon loop delay (default: 300 seconds)
- `DRY_RUN` — Flag for inbox-cleanup to preview changes without applying them

## Key Behaviors
- **Mail sync**: Runs mbsync per account in parallel, extracts subject/from from new messages, displays desktop notifications
- **Tagging**: Uses notmuch queries to batch-tag by sender patterns (news, receipts, spam, archived)
- **Quote trimming**: Perl regex-based; removes signatures, flattens nested quotes (max 3 levels), detects Outlook headers
- **Calendar parsing**: Python uv-shebang script; renders attendee roles/RSVP status, recurrence rules, timezone handling
