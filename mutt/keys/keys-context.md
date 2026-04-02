# keys
> Neomutt keybinding config: wipes ALL default bindings then applies a clean vim-style layer.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `unbinds.muttrc` | Nukes every default mutt binding across all contexts — must be sourced BEFORE binds.muttrc |
| `binds.muttrc` | Full vim-style rebind: j/k navigation, gg/G top/bottom, Ctrl+j/k for sidebar, compose shortcuts |

<!-- peek -->

## Conventions

`unbinds.muttrc` must be sourced first in the parent muttrc — it blanket-noops every key across all contexts (generic, pager, editor, index, compose, browser, attach), so any bind defined before it will be silently overwritten.

The `D` (delete) and `A` (archive) macros in `binds.muttrc` use `:set resolve=no` guards to prevent mutt from auto-advancing to the next message after the action — this is intentional and must be preserved if those macros are edited.

## Gotchas

`\ci` (Ctrl+I) and `<Tab>` are the same key in terminals — `unbinds.muttrc` noops `<Tab>` globally, so `\ci` in binds.muttrc (limit by flagged on index) works because it's re-bound after the noop. Adding new `<Tab>` binds in other contexts requires a corresponding re-bind here.

The `gg` binding is implemented differently across contexts: in pager it goes to `top` (a pager-specific function), but in index/attach/browser/query it maps to `first-entry` — these are not interchangeable.

Archive macro (`A`) hardcodes `=[Gmail].All\ Mail` as the destination — Gmail-specific, will break for non-Gmail IMAP accounts.
