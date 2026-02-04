# isync

_Last updated: 2026-01-27_

## Purpose
Configuration for `mbsync` (isync), which synchronizes Gmail IMAP mailboxes to local Maildir storage. Enables offline-capable mutt mail client functionality with selective folder sync and message limits.

## Key Files
| File | Role | Notable Content |
|------|------|-----------------|
| `mbsyncrc` | Primary mbsync configuration | Gmail IMAP remote store, local Maildir store, sync channel with folder patterns, max message limits |

## Dependencies
- **External:** `mbsync` (isync package), Gmail account with IMAP enabled, TLS certificates (`/etc/ssl/cert.pem`)
- **Internal:** `~/.mutt_secrets` (stores Gmail password reference), `~/.local/share/mail/gmail/` (local sync destination)

## Entry Points
`mbsyncrc` — Primary configuration file sourced by `mbsync` command for automated mail synchronization.

## Configuration Details

### Gmail IMAP Remote Store
- **Host:** `imap.gmail.com` (Port 993, IMAPS)
- **User:** `vadmas@gmail.com`
- **Password:** Retrieved from `~/.mutt_secrets` via PassCmd
- **Authentication:** LOGIN with TLS

### Local Maildir Store
- **Path:** `~/.local/share/mail/gmail/`
- **INBOX:** `~/.local/share/mail/gmail/INBOX`
- **Subfolders:** Verbatim (preserve folder names)
- **Flatten:** Dot-style folder flattening

### Sync Channel: gmail
- **Direction:** Bidirectional (`Expunge Both`)
- **Patterns:** Syncs all folders except `[Gmail]` system folders, but explicitly includes `[Gmail]/Sent Mail`, `[Gmail]/Starred`, `[Gmail]/Drafts`, `[Gmail]/All Mail`
- **Message Limit:** `MaxMessages 1000` per folder
- **Unread Preservation:** `ExpireUnread no`
- **State Management:** `SyncState *` for tracking sync progress

## Related Configuration
Part of larger mutt mail setup. Coordinates with:
- `muttrc` — Mutt client configuration
- `msmtp/` — SMTP configuration for sending mail
- `accounts/` — Account definitions
- `scripts/` — Mail-related utility scripts
- `mutt-context.md` — Overall mutt directory documentation
