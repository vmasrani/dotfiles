# wip

## Purpose
Work-in-progress directory containing experimental iMessage data extraction and analysis tools, plus utilities for JSON processing and tmux popup management. This is a collection of prototypes exploring macOS Messages database access and message analytics.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| imessage_analyzer.py | Comprehensive iMessage extractor and analyzer with CLI interface | `Args`, `export_to_csv`, `search_messages`, `send_message`, `send_bulk_messages` |
| imessage_extractor.py | Class-based wrapper for iMessage database extraction | `iMessageExtractor` class with methods for contacts, chats, attachments, statistics |
| debug.py | Binary-safe message extraction from attributedBody BLOB fields | `extract_text_from_attributed_body`, `extract_messages`, `convert_apple_time` |
| test_imessage_tools.py | Unit tests for imessage_tools library compatibility | `test_imessage_tools` |
| example_usage.py | Comprehensive usage examples for iMessage analyzer | Multiple example functions demonstrating search, statistics, custom analysis |
| process_json.sh | Bash script for processing JSON text fields through aichat OCR fixer | Processes extracted text via external command |
| show-tmux-popup.sh | Create and manage tmux popup sessions with custom keybindings | Session management utilities |
| project.md | Documentation on GitHub-based parallel development workflow | Process templates, issue tracking, progress monitoring |
| pyproject.toml | Python project configuration with uv dependencies | Project metadata, 30 dependencies including pandas, pytorch, sklearn |

## Patterns
- **Database Access**: Direct SQLite3 read-only connections to macOS chat.db with read-only URI mode
- **Data Extraction Pipeline**: Messages -> DataFrame -> CSV export with per-conversation file splits
- **Binary Data Parsing**: Multiple fallback methods for extracting text from Apple's NSAttributedString BLOB format
- **CLI with Dataclass**: Uses Hypers dataclass for argument parsing (custom CLI framework)
- **Statistics Aggregation**: Temporal analysis (by year, month, hour, day), contact frequency, message length stats
- **AppleScript Integration**: Send iMessages programmatically via osascript with escaped string injection protection
- **Project Management Automation**: GitHub CLI workflows with progress tracking via commit counting

## Dependencies
- **External**: pandas, polars, sqlite3, machine-learning-helpers (git), torch, scikit-learn, mysql-connector-python, ollama, openai, requests, rich, seaborn, matplotlib, numpy, ipython, joblib, tqdm, pyyaml, aichat
- **Internal**: imessage_tools library (imported but not in repo), mlh.hypers for CLI argument handling
- **System**: osascript (macOS AppleScript execution), tmux, jq, bash/zsh

## Entry Points
- `/Users/vmasrani/dotfiles/wip/imessage_analyzer.py` — CLI tool for iMessage data extraction, search, and sending
- `/Users/vmasrani/dotfiles/wip/debug.py` — Direct database extraction with advanced BLOB text parsing
- `/Users/vmasrani/dotfiles/wip/example_usage.py` — Demonstration of all analyzer features
- `/Users/vmasrani/dotfiles/wip/process_json.sh` — JSON text processing pipeline
- `/Users/vmasrani/dotfiles/wip/show-tmux-popup.sh` — tmux popup session launcher

## Output Files
- `messages_export.csv` — Flattened message export with sender, content, timestamp
- `updated.json` — Result of process_json.sh OCR text extraction
- `result.txt` — Debug output from database schema inspection
- Individual conversation CSVs generated in Desktop/message_conversations/ and Desktop/imessage_export/
