# mutt/accounts

_Last updated: 2026-01-27_

## Purpose
Per-account mail client configuration files for mutt. Each account file defines credentials, folder structure, local storage paths, and custom keybindings specific to that email provider.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `gmail.muttrc` | Gmail account configuration | `realname`, `from`, `folder`, `spoolfile`, `mailboxes`, folder navigation macros |

## Patterns
Per-account configuration sourcing. Each account file:
- Sources secrets from `~/.mutt_secrets` for credentials
- Defines mail storage location via mbsync (Maildir format)
- Sets account-specific cache paths (headers/bodies)
- Configures folder structure and mailbox list
- Provides folder navigation shortcuts (g prefix) and move/copy macros (M/C prefix)
- Integrates with notmuch full-text search

## Dependencies
- **External:** `msmtp` (mail sending), `mbsync` (mail synchronization), `notmuch` (full-text search)
- **Internal:** Secrets from `~/.mutt_secrets` (git-ignored)

## Entry Points
Sourced by `/Users/vmasrani/dotfiles/mutt/muttrc` at startup:
```
source $HOME/.config/mutt/accounts/gmail.muttrc
```

## Configuration Details
**Gmail-specific setup:**
- Local mail folder: `~/.local/share/mail/gmail` (Maildir format)
- Spool file: `+INBOX`
- Postponed (drafts): `+[Gmail].Drafts`
- Per-account cache: `~/.cache/mutt/gmail/{headers,bodies}`
- Configured mailboxes: INBOX, Sent Mail, Drafts, Starred, All Mail
- Folder shortcuts: `gi` (Inbox), `gs` (Sent), `gd` (Drafts), `g*` (Starred), `ga` (All Mail)
- Sync macro: `o` triggers `mailsync gmail`
- Search: `Ctrl-f` queries notmuch across gmail/* paths
