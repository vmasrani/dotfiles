# scripts
> Helper scripts for neomutt: mail sync, HTML/ICS rendering, reply cleanup, and notmuch-based inbox triage.
`7 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `mailsync` | Runs mbsync for all or named accounts, notifies on new mail via osascript, then indexes with notmuch and applies initial tags (`+inbox +unread -new`) — this is the primary sync entrypoint |
| `mailsync-daemon` | Loop wrapper for `mailsync` intended to run under pm2; interval controlled by `$SYNC_INTERVAL` env var (default 300s) |
| `inbox-cleanup` | Batch notmuch tagging script: routes newsletters → `+news`, receipts → `+receipts`, spam → `+spam`, platform noise → `+archived`. Supports `--dry-run` / `-n`. Hardcoded sender patterns for ~60+ senders |
| `beautiful_html_render` | Converts HTML attachment to markdown via `html2text`, then renders with `glow -s dark`; strips certain ANSI codes that break terminal display |
| `mutt-viewical` | Python uv-script: parses `.ics` calendar invites from stdin using `icalendar`+`pytz`; respects `$TZ` env or falls back to `tzlocal` |
| `render-calendar-attachment.py` | Alternative ICS renderer using `vobject` library; takes a file path argument rather than stdin |
| `mutt-trim` | Perl script that cleans quoted reply text: trims signatures, collapses nested `> > ` quote markers, strips multilingual greetings/closings up to 3 quote levels |

<!-- peek -->

## Conventions

- `mailsync` reads account names directly from `~/.config/isync/mbsyncrc` channel definitions — no separate account list to maintain.
- Notmuch config is explicitly set to `$HOME/.config/notmuch/notmuchrc` inside `mailsync` (not the default `~/.notmuch-config`).
- `mailsync` sources `~/.mutt_secrets` to get `$my_gmail_user` for auto-tagging sent mail — this file must exist for sent-mail tagging to work.
- New mail detection in `mailsync` uses a touch file at `~/.config/mutt/.mailsynclastrun` as the timestamp reference; if this file is missing, all existing mail counts as "new."
- macOS notifications in `mailsync` are opt-in: set `MAILSYNC_NOTIFY=1` in environment; silent by default.
- `mutt-trim` modifies the mail file **in-place** (opens with `+<`) — it is called by mutt as a pre-reply hook, not a filter.

## Gotchas

- `inbox-cleanup` hardcodes `MAIL_DIR="$HOME/.local/share/mail/gmail"` — only works for the gmail account; other accounts need separate handling.
- Two ICS renderers exist (`mutt-viewical` and `render-calendar-attachment.py`) with different interfaces: `mutt-viewical` reads from stdin, `render-calendar-attachment.py` takes a file path. Check mutt's `mailcap` to see which is actually wired up.
- `mailsync` runs `syncandnotify` for each account in parallel (background `&`) then `wait` — if one account fails, others still complete but the exit code is not checked.
- `mutt-trim` strips signatures from **all** quote levels matching `-- ` lines, which can remove legitimate content in heavily-threaded emails.
