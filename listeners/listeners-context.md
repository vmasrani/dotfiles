# Listeners

## Purpose
Monitors file system events in the Downloads directory and automatically processes newly created PDFs and ebooks using external tools. Uses fswatch to watch for file creation events and triggers corresponding processing scripts via pm2 for background process management.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| start_listeners.sh | Process manager entry point | Starts pm2 daemon with watch scripts |
| watch_pdfs_in_downloads.sh | PDF monitor | Watches for PDF creation and pipes to rename_pdf tool |
| watch_ebooks_in_downloads.sh | Ebook monitor | Watches for EPUB/MOBI creation and pipes to convert_ebook tool |

## Patterns
- **Event-driven file watching**: Uses fswatch to monitor filesystem events with NUL-separated paths for safe handling
- **Pipeline architecture**: File system events → filter by type → safety checks → tool invocation
- **Process management**: pm2 daemon manages long-running listener scripts with automatic startup configuration

## Dependencies
- **External:** fswatch (filesystem watcher at `/opt/homebrew/bin/fswatch`), pm2 (Node.js process manager)
- **Internal:** `tools/rename_pdf`, `tools/convert_ebook`

## Entry Points
- `start_listeners.sh` — Orchestrates pm2 daemon startup and loads listener scripts
- `watch_pdfs_in_downloads.sh` — Continuous process watching for new PDFs
- `watch_ebooks_in_downloads.sh` — Continuous process watching for new ebooks

## Technical Details
Both watch scripts follow identical patterns:
- Monitor `$HOME/Downloads` directory using fswatch with "Created" event filter
- Use NUL-byte delimiter for safe path handling with special characters
- Case-insensitive file extension matching
- Verify file still exists before processing (handles race conditions)
- Pipe file paths directly to external processing tools
- Redirect stdin from `/dev/null` to prevent blocking on interactive prompts
