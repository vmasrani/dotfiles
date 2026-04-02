# wip
> Scratch area for experimental and in-progress work — iMessage extraction scripts, tmux config experiments, and GitHub parallel-dev process docs.
`19 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `project.md` | Full reference doc for GitHub-based parallel development process with `gh` CLI — templates, Actions, branch conventions |
| `imessage_extractor.py` | Reads iMessages from `~/Library/Messages/chat.db` using `imessage_tools` lib; defaults to system DB path |
| `imessage_analyzer.py` | Analysis layer on top of extractor — likely sentiment/stats over exported messages |
| `messages_export.csv` | Exported iMessage data (real data — treat as sensitive) |
| `process_json.sh` | Shell script for processing `updated.json` |
| `dracula.conf` | Dracula theme for tmux — WIP alternative to the main tmux theme |
| `.tmux.conf.sidepanel` | Experimental tmux sidepanel config (not yet merged into main `tmux/.tmux.conf`) |
| `show-tmux-popup.sh` | Script for triggering tmux popup windows — prototype for tmux integration |
| `pyproject.toml` | uv-managed Python project for the iMessage tools |

<!-- peek -->

## Gotchas
- `messages_export.csv` contains real iMessage data — do not commit or share.
- `imessage_extractor.py` requires Full Disk Access permission on macOS to read `~/Library/Messages/chat.db`; will raise `FileNotFoundError` without it.
- The tmux files here (`.tmux.conf.sidepanel`, `dracula.conf`) are NOT symlinked — they are experiments that have not been promoted to `tmux/`.
- `main.py` is a stub (prints "Hello from wip!") — not a real entry point for anything.
- This directory is intentionally unstructured; files here may be abandoned experiments.
