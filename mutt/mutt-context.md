# mutt
> Neomutt email client config for Gmail: local Maildir sync via mbsync, sent via msmtp, indexed by notmuch.
`11 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `muttrc` | Main config entry point — sources keys, account, and styles; sets notmuch integration, threading, and editor to `mutt-trim %s; hx %s` |
| `mailcap` | MIME handler mappings telling mutt how to open HTML, ICS, and other attachments (routes to scripts/) |
| `styles.muttrc` | Color theme and message formatting rules |
| `powerline-fixed.muttrc` | Status bar format string using powerline glyphs |
| `gmail-filters.xml` | Gmail server-side filter definitions (for import in Gmail web UI, not used by mutt directly) |
| `accounts/gmail.muttrc` | Gmail-specific settings: folder paths, mailboxes, folder-nav macros (gi/gs/gd/ga), and notmuch search macro (Ctrl-f) |
| `isync/mbsyncrc` | mbsync config syncing Gmail IMAP to `~/.local/share/mail/gmail/`; password read from `~/.mutt_secrets` via PassCmd grep |
| `msmtp/config` | SMTP send config; requires Gmail App Password (not account password) if 2FA is enabled |
| `notmuch/notmuchrc` | Notmuch index config; database root is `~/.local/share/mail` (covers all accounts, not just gmail) |
| **keys/** | Neomutt keybinding config: wipes ALL default bindings then applies a clean vim-style layer. |
| **scripts/** | Helper scripts for neomutt: mail sync, HTML/ICS rendering, reply cleanup, and notmuch-based inbox triage. |

<!-- peek -->

## Conventions

- All credentials come from `~/.mutt_secrets` (git-ignored, lives in `local/`). Both mbsync and msmtp parse it with shell greps rather than a proper secrets tool.
- Notmuch config is explicitly set to `$HOME/.config/notmuch/notmuchrc` inside `mailsync` — not the default `~/.notmuch-config`. Pointing notmuch at the wrong config silently uses a different database.
- Sent mail is NOT saved locally — `unset record` in `accounts/gmail.muttrc` because Gmail IMAP saves it server-side automatically.
- The editor pipeline is `mutt-trim %s; hx %s` — mutt-trim runs first to clean quoted reply text in-place, then helix opens the file.
- `alternative_order` prefers `text/html` over `text/plain` — newsletters render with links, but plain-text emails that also have HTML parts will show HTML.

## Gotchas

- Gmail requires an **App Password** (not the account password) for both mbsync and msmtp when 2FA is enabled. Regular password auth will silently fail with auth errors.
- `mbsyncrc` uses `Expunge Both` — deleting mail in mutt will permanently delete from Gmail server, not just move to Trash.
- `mbsyncrc` has `MaxMessages 1000` per folder — older mail beyond 1000 messages is not synced locally but remains on Gmail server.
- New mail detection in `mailsync` uses `~/.config/mutt/.mailsynclastrun` as a timestamp reference. If this file is missing (fresh install), all existing mail appears as "new" and triggers notifications.
- Two ICS calendar renderers exist: `mutt-viewical` (reads stdin) and `render-calendar-attachment.py` (takes file path). Check `mailcap` to see which is actually wired up.
- macOS notifications in `mailsync` are opt-in: set `MAILSYNC_NOTIFY=1`; silent by default.
- `inbox-cleanup` hardcodes the gmail mail dir path — doesn't handle additional accounts without modification.
