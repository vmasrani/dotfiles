# listeners
> Background file-watchers that auto-process Downloads: PDFs get renamed, ebooks get converted on arrival.
`3 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `start_listeners.sh` | Registers both watchers as pm2 daemons and calls `pm2 startup` + `pm2 save` to persist across reboots |
| `watch_pdfs_in_downloads.sh` | Watches `~/Downloads` via `fswatch`, calls `tools/rename_pdf` on any new `.pdf` file |
| `watch_ebooks_in_downloads.sh` | Watches `~/Downloads` via `fswatch`, calls `tools/convert_ebook` on new `.epub`/`.mobi` files |

<!-- peek -->

## Conventions
- Managed by **pm2**, not launchd or cron. Use `pm2 list`, `pm2 logs`, `pm2 restart <name>` to manage.
- `start_listeners.sh` is the single entry point — run it once to register and persist all watchers.
- The processing scripts are in `tools/` (`rename_pdf`, `convert_ebook`), not here.
- Scripts pass `</dev/null` to the tool invocation to prevent stdin issues in pm2's non-TTY context.

## Gotchas
- `fswatch` path is hardcoded to `/opt/homebrew/bin/fswatch` (macOS/Homebrew only) — Linux installs will silently fail.
- pm2 daemon name for ebook watcher is `watch-epbs` (typo of "epubs") — use this exact name with pm2 commands.
- The `.claude/` subdirectory contains local Claude Code session logs — not part of the watcher logic.
