# mutt/notmuch

_Last updated: 2026-01-27_

## Purpose
Configuration files for notmuch email indexing and search engine integration with mutt. Defines database paths, user credentials, tagging rules, and maildir synchronization behavior.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `notmuchrc` | Primary notmuch configuration | database path, user settings, tag rules, search exclusions |

## Configuration Sections

**[database]** — Email storage location at `~/.local/share/mail`

**[user]** — User identity: Vaden Masrani, primary email vadmas@gmail.com

**[new]** — Tagging rules for newly indexed messages; ignores sync/lock files

**[search]** — Excludes deleted and spam tags from search results

**[maildir]** — Enables flag synchronization between notmuch and mail storage

## Related Components
- Parent directory `mutt/` contains mutt mail client configuration
- Integrates with email storage at `~/.local/share/mail` (symlinked from dotfiles)
- Typically used with `mbsync` for mail synchronization (referenced in ignore patterns)
