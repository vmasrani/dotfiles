# Downloads Folder Auto-Processing Plan

## Overview
Automated file watching system for ~/Downloads that processes PDFs and ebooks with intelligent tagging and workflow management.

## Architecture Decision

**File Watcher**: `watchfiles` (modern, Rust-based, by Pydantic author Samuel Colvin)
- Most performant option in 2025
- Cross-platform, minimal CPU usage
- Supports both sync and async operations

**Process Manager**: PM2
- Feature-rich monitoring dashboard
- Automatic restart on failure
- Easy log management
- User-selected preference

## Implementation Components

### 1. File Watcher Script: `~/dotfiles/tools/filewatcher.py`

**Core Functionality**:
```
Watch ~/Downloads (root only, no subdirectories)
On new file detected:
  1. Apply debouncing (3 second wait to ensure download complete)
  2. Check file size threshold (>100KB to skip corrupted downloads)
  3. Identify file type (.pdf, .epub, .mobi)
  4. Tag with Gray badge
  5. Process based on type:
     - PDF → run rename_pdf → tag Green on success
     - EPUB/MOBI → run convert_ebook → tag Gray on output PDF
  6. Log all actions to ~/Downloads/.pm2/filewatcher.log
  7. Send macOS notification on errors
```

**Dependencies** (via uv):
- `watchfiles` - File system monitoring
- `typer` - CLI argument parsing (NOT hypers, user preference)
- `rich` - Pretty console output (already used by Typer)
- Standard library: `subprocess`, `pathlib`, `time`, `logging`

**CLI Arguments** (using Typer):
```python
filewatcher.py [OPTIONS]

Options:
  --downloads-path PATH         Downloads folder to watch [default: ~/Downloads]
  --debounce-seconds FLOAT      Seconds to wait after file change [default: 3.0]
  --min-size-kb INTEGER         Minimum file size in KB to process [default: 100]
  --recursive / --no-recursive  Watch subdirectories [default: no-recursive]
  --log-dir PATH               Log directory [default: ~/Downloads/.pm2/]
  --notify / --no-notify       Send macOS notifications on errors [default: notify]
  --help                       Show this message and exit
```

**Key Features**:
- Event debouncing: Track file modification times, wait 3 seconds of stability
- Size threshold: Skip files <100KB
- Gray/Green tagging via existing `tag` command
- Process output capture for logging
- Error handling with macOS notifications using `osascript`

### 2. PM2 Configuration

**Setup Steps**:
```bash
# Install PM2 globally if not present
npm install -g pm2

# Start the watcher with PM2
pm2 start ~/dotfiles/tools/filewatcher.py --name downloads-watcher --interpreter uv

# Save PM2 process list
pm2 save

# Configure PM2 to start on boot
pm2 startup
```

**PM2 Features Utilized**:
- Auto-restart on crashes
- Log management (stdout/stderr separation)
- Process monitoring via `pm2 monit`
- Status checks via `pm2 status`

### 3. Logging Strategy

**Location**: `~/Downloads/.pm2/`
- `filewatcher.log` - Main application log
- `filewatcher-error.log` - PM2 stderr
- `filewatcher-out.log` - PM2 stdout

**Log Format**:
```
[TIMESTAMP] [LEVEL] Event: NEW_FILE | File: filename.pdf | Action: TAG_GRAY
[TIMESTAMP] [INFO] Event: PROCESSING | File: filename.pdf | Tool: rename_pdf
[TIMESTAMP] [INFO] Event: SUCCESS | File: old.pdf → new_name.pdf | Action: TAG_GREEN
[TIMESTAMP] [ERROR] Event: FAILED | File: broken.epub | Error: conversion API limit
```

### 4. File Tagging Workflow

```
NEW PDF FILE
  ├─> Tag: Gray
  ├─> Run: rename_pdf
  └─> Tag: Green (if successful)

NEW EPUB/MOBI FILE
  ├─> Tag: Gray
  ├─> Run: convert_ebook
  ├─> Output PDF tagged: Gray
  ├─> Run: rename_pdf on output
  └─> Tag: Green (if successful)
```

**Tag Commands**:
- Add Gray: `tag --add Gray <file>`
- Remove Gray, Add Green: `tag --remove Gray --add Green <file>`
- Uses existing `tag` tool (already in rename_pdf script)

### 5. Error Handling

**macOS Notifications**:
```bash
osascript -e 'display notification "Error processing file.pdf" with title "Downloads Watcher" sound name "Basso"'
```

**Retry Strategy**:
- Don't retry failed files automatically (avoid infinite loops)
- Log errors with full stack trace
- Keep Gray tag on failed files for manual review
- Notification alerts user to check logs

### 6. PM2 Management Script: `~/dotfiles/listeners/start_listeners.sh`

**Purpose**: Unified interface to control all PM2-managed file watchers/listeners

**Functionality**:
```bash
start_listeners.sh [command]

Commands:
  start   - Start all listeners
  stop    - Stop all listeners
  restart - Restart all listeners
  delete  - Delete all listeners from PM2
  status  - Show status of all listeners
  logs    - Tail logs for all listeners
  monit   - Open PM2 monitoring dashboard
```

**Implementation**:
- Uses `gum` for styled output and user confirmation
- Tracks all listener process names (currently: downloads-watcher)
- Future-proof: easy to add more listeners
- Applies PM2 commands to all tracked listeners simultaneously
- Provides visual feedback for each operation

**Example Flow**:
```bash
$ start_listeners.sh stop
┌────────────────────────────────┐
│ Stopping PM2 Listeners         │
└────────────────────────────────┘
⠿ Stopping downloads-watcher... Done
✓ All listeners stopped successfully
```

**Features**:
- Colorful `gum style` output for headers
- `gum spin` for operations in progress
- Success/error feedback with appropriate styling
- Confirmation prompts for destructive operations (delete)
- Lists all managed listeners before applying commands

## Files to Create/Modify

### New Files:
1. `~/dotfiles/tools/filewatcher.py` - Main file watcher script
2. `~/dotfiles/listeners/start_listeners.sh` - PM2 management wrapper script

### New Directories:
1. `~/dotfiles/listeners/` - Directory for listener-related scripts

### Modified Files:
None (existing scripts work as-is)

### Configuration:
1. PM2 ecosystem file (optional): `~/dotfiles/pm2.config.js`

## Testing Strategy

1. **Manual Testing**:
   - Drop test PDF in Downloads → verify Gray tag → verify rename → verify Green tag
   - Drop test EPUB → verify Gray → verify conversion → verify output PDF Gray → verify rename → verify Green
   - Drop tiny file (<100KB) → verify skipped
   - Drop file then modify immediately → verify debouncing works

2. **PM2 Verification**:
   - `pm2 status` - Check running
   - `pm2 logs downloads-watcher` - View real-time logs
   - `pm2 restart downloads-watcher` - Verify auto-restart
   - Reboot Mac → verify auto-start

3. **Edge Cases**:
   - Files with special characters in names
   - Very large files (>100MB)
   - Multiple files dropped simultaneously
   - Disk full scenarios

## Installation Steps

1. Create `~/dotfiles/listeners/` directory
2. Create `filewatcher.py` with watchfiles implementation in `~/dotfiles/tools/`
3. Add uv dependencies to script header:
   ```python
   # /// script
   # requires-python = ">=3.12"
   # dependencies = [
   #     "watchfiles",
   #     "typer",
   #     "rich",
   # ]
   # ///
   ```
4. Create `start_listeners.sh` in `~/dotfiles/listeners/`
5. Make `start_listeners.sh` executable: `chmod +x ~/dotfiles/listeners/start_listeners.sh`
6. Test script manually: `uv run ~/dotfiles/tools/filewatcher.py --help`
7. Test with custom options: `uv run ~/dotfiles/tools/filewatcher.py --debounce-seconds 5`
8. Install PM2: `npm install -g pm2`
9. Start with PM2 (using default options):
   ```bash
   pm2 start ~/dotfiles/tools/filewatcher.py \
     --name downloads-watcher \
     --interpreter "uv run" \
     --log ~/Downloads/.pm2/filewatcher.log
   ```
10. Save PM2 config: `pm2 save`
11. Enable startup: `pm2 startup` (follow instructions)
12. Test management script: `~/dotfiles/listeners/start_listeners.sh status`
13. Test end-to-end with sample files

## Future Enhancements (Not in Scope)

- Web dashboard for monitoring
- Configurable file type support
- Different actions per file type
- Integration with other automation tools
- Batch processing of existing files

## References

- [watchfiles documentation](https://watchfiles.helpmanual.io/)
- [watchfiles GitHub](https://github.com/samuelcolvin/watchfiles)
- [PM2 documentation](https://pm2.keymetrics.io/)
- [tag command usage](https://github.com/jdberry/tag)
- [Watchfiles tutorial](https://medium.com/aardvark-infinity/watchfiles-real-time-file-monitoring-in-python-0dd43b632978)
