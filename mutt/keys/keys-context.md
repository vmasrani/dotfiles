# mutt/keys

_Last updated: 2026-01-27_

## Purpose

Defines custom keybindings for NeoMutt email client. Uses a comprehensive unbind-first strategy to override all default bindings, then selectively rebinds keys with vim-style navigation. This creates a clean, predictable keymap centered on hjkl movement and mnemonic single-character commands.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| unbinds.muttrc | Clears all default mutt keybindings across all contexts (generic, index, pager, compose, attach, browser, query, alias) | Removes ~400+ default bindings by mapping to noop |
| binds.muttrc | Defines custom vim-style keybindings for all mutt interface modes | Navigation (hjkl), mail ops (t/d/u), compose (y/a/p), sidebar (Ctrl+b/j/k) |

## Patterns

**Unbind-first architecture**: Clears the entire default keymap in `unbinds.muttrc` by binding all alphanumerics, symbols, and special keys to `noop` across all contexts (generic, pager, editor, index, compose, browser, attach). This prevents accidental triggering of confusing mutt defaults.

**Vim-style navigation**: Rebinds in `binds.muttrc` using hjkl for movement (pager: j/k for next/prev line, G/gg for bottom/top). Arrow keys still supported for discoverability.

**Context-aware bindings**: Some keys differ by context (index vs pager vs compose) using `bind index,pager` syntax to apply across multiple modes efficiently.

**Mnemonic commands**: Single-letter commands map to actions (f=change-folder, c=compose, r=reply, d=delete, t=tag, etc.).

## Key Bindings

### Navigation
- `j/k` / Arrow keys: Previous/next line (pager), previous/next entry (index/browser)
- `G/gg`: Bottom/top of list or message
- `h/l`: Collapse/expand threads in index
- `zz/zt/zb`: Center/top/bottom current line
- `<Ctrl-u/d>`: Half-page up/down

### Mail Operations
- `t`: Tag message
- `T`: Tag entire thread
- `d`: Delete message
- `u`: Undelete message
- `<Space>`: Flag message
- `\` (backslash): Limit/filter view
- `D`: Delete with archive (macro)
- `A`: Archive to All Mail (macro)

### Compose & Replies
- `c`: Compose new
- `r`: Reply
- `R`: Group reply
- `F`: Forward
- `<Ctrl-r>`: Recall from drafts

### Compose Screen
- `y`: Send
- `a`: Attach file
- `p`: Postpone
- `e`: Edit message body
- `t/f/s/c/b`: Edit To/From/Subject/Cc/Bcc
- `<Ctrl-k/j>`: Move up/down in attachment list

### Sidebar & Navigation
- `<Ctrl-b>`: Toggle sidebar
- `<Ctrl-j/k>`: Next/prev folder in sidebar
- `<Ctrl-o>`: Open selected folder
- `f`: Change folder
- `$`: Sync/refresh mailbox

### Misc
- `n/N`: Search next/previous
- `p`: Search opposite direction
- `v`: View attachments
- `L`: Edit labels
- `H`: View raw message
- `|`: Pipe message
- `\Cl`: Open links with urlscan (macro)
- `O`: Run mbsync to sync all mail (macro)
- `<Ctrl-a>`: Mark all as read (macro)
- `q`: Exit (all contexts)
- `<Esc>`: Abort key

## Dependencies

- **External**: NeoMutt mail client
- **Internal**: Sourced by main mutt configuration file

## Entry Points

These files are sourced from the main mutt config (typically `~/.muttrc` or `~/.config/neomutt/neomuttrc`) via `source` directives to apply keybindings at startup.
