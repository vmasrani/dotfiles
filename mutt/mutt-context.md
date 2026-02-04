# mutt

## Purpose
Comprehensive NeoMutt email client configuration for Gmail integration with local mail synchronization, advanced filtering, and modern terminal UI rendering. Includes IMAP sync (mbsync), SMTP sending (msmtp), full-text search (notmuch), and calendar/HTML email rendering.

## Key Files
| File | Role | Notable Features |
|------|------|------------------|
| muttrc | Main NeoMutt config | Caching, threading, notmuch integration, sidebar, security settings |
| accounts/gmail.muttrc | Gmail account setup | Local Maildir storage, folder macros, mbsync integration, notmuch search |
| keys/binds.muttrc | Custom keybindings | Vim-style navigation, thread collapse, macro definitions for mail actions |
| keys/unbinds.muttrc | Unbind defaults | Clears all default keybindings for clean custom keymap setup |
| styles.muttrc | Color theme (gum-inspired) | Pink/magenta accent palette, index colors, sidebar, headers, quotes |
| powerline-fixed.muttrc | Powerline format strings | Nerd font symbols, status bar formats, attachment indicators |
| mailcap | MIME type handlers | HTML-to-markdown rendering, image/video/PDF handlers, calendar parsing |
| isync/mbsyncrc | Mail sync config | Gmail IMAP, local Maildir storage, folder patterns, sync state |
| msmtp/config | SMTP sending | Gmail SMTP, TLS auth, password management from secrets file |
| notmuch/notmuchrc | Full-text search | Database path, user info, tag exclusions, Maildir flag sync |
| scripts/mailsync | Mail sync runner | mbsync wrapper with new mail detection, macOS notifications, internet check |
| scripts/mailsync-daemon | Sync daemon wrapper | pm2-compatible loop for periodic mail sync (5-min default interval) |
| scripts/inbox-cleanup | Inbox organization | Batch label assignment based on sender patterns (idempotent, dry-run support) |
| scripts/mutt-trim | Perl quote cleaner | Beautifies quoted messages, removes greeting duplicates (invoked by editor) |
| scripts/mutt-viewical | Calendar parser | Python script with vobject, renders ICS invitations inline |
| scripts/beautiful_html_render | HTML renderer | Converts HTML to markdown via html2text, renders with glow |
| scripts/render-calendar-attachment.py | Calendar renderer | Python uv script, parses VEVENT properties with timezone handling |
| gmail-filters.xml | Gmail filter export | Atom feed format, 70+ auto-label/archive/spam rules by sender category |

## Patterns
- **Configuration Composition**: Multi-file sourcing hierarchy (unbind → bind → account → styles → powerline)
- **Secret Management**: Passwords stored in git-ignored `~/.mutt_secrets`, sourced at runtime by shell commands
- **Folder-based Organization**: Subdirectories separate concerns (accounts, keys, isync, msmtp, notmuch, scripts)
- **Macro-driven UX**: Keyboard macros for folder navigation (gi=inbox, gs=sent, gd=drafts), mail actions (M=move, C=copy, D=delete), and sync triggers
- **Render Pipeline**: Mailcap chains external tools (html-to-markdown → glow, icalendar parsing, system `open` for media)
- **Idempotent Sync**: Guard checks prevent duplicate mbsync/mail processes; guards check internet, user login, existing processes
- **Lazy Editor**: `mutt-trim` beautifies quoted text before Helix launches for composition
- **Tag-based Search**: Notmuch integration for fast full-text search with query macros and virtual mailbox support

## Dependencies
- **External (Tools):**
  - `neomutt` - email client
  - `mbsync` (isync) - IMAP sync daemon
  - `msmtp` - SMTP sender
  - `notmuch` - full-text email indexer
  - `glow` (charmbracelet) - markdown renderer with theme support
  - `html-to-markdown` or `html2text` - HTML-to-markdown conversion
  - `helix` (hx) - text editor (invoked for composition via `mutt-trim`)
  - `pandoc` - markdown-to-HTML macro (for rich email composition)
  - `urlscan` - link extraction and opening utility
  - `git-split-diffs` - patch viewer macro
  - `osascript` (macOS) - system notifications
  - `pm2` - optional process manager for mailsync daemon

- **External (Python):**
  - `icalendar` - ICS file parsing (mutt-viewical)
  - `pytz`, `tzlocal` - timezone handling (calendar rendering)
  - `vobject` - vCard/vEvent parsing (render-calendar-attachment.py)

- **Internal:**
  - `shell/gum_utils.sh` - terminal UI utilities (inbox-cleanup sources, fallback to raw echo)

## Entry Points
- **Primary**: `/Users/vmasrani/dotfiles/mutt/muttrc` - sourced by `~/.config/mutt/muttrc` (via symlink from dotfiles setup)
- **Scripts**: All scripts in `scripts/` are symlinked to `~/bin/` during setup; callable standalone or via mutt macros
- **Mail Sync**: `mailsync` command (runs `mailsync gmail` macro from index) or `mailsync-daemon` via pm2

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| accounts/ | Per-account configurations (Gmail) | No |
| isync/ | mbsync IMAP sync config | No |
| msmtp/ | SMTP sending configuration | No |
| notmuch/ | Full-text search indexing setup | No |
| scripts/ | Utility scripts for rendering, syncing, cleanup | No |
| keys/ | Keybinding definitions (binds & unbinds) | No |
