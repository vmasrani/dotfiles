# preview
> FZF file preview dispatcher with handlers for 20+ data/media formats using syntax highlighting and specialized libraries
`7 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| fzf-preview.sh | Main dispatcher routing files to format-specific previewers; 5-second timeout guard; symlink resolution |
| torch-preview.py | PyTorch model tensor display with version info |
| pkl-preview.py | Rich-formatted pickle inspection, handles pandas objects |
| feather-preview.py | Apache Feather columnar data reader |
| npy-preview.py | NumPy array heatmap rendering via matplotlib/chafa |

## Conventions
- **Timeout protection**: All previews wrapped in `timeout 5s` to prevent hangs in FZF
- **Binary detection fallback**: Unmatched files tested with `file --mime-type` to distinguish text from binary
- **Symlink resolution**: Input paths checked for symlinks and resolved before processing
- **Empty file handling**: Empty files return `[empty file]` instead of error
- **Python script format**: All `.py` scripts use `#!/usr/bin/env -S uv run --script` with inline `# ///` dependency block
- **MAX_LINES=500**: Hard limit on output lines to prevent FZF panel overflow

## Gotchas
- **Timeout kills long operations**: Archives and large files may timeout at 5s; no fallback for partial results
- **sqlite3 defaults to first table**: Multi-table databases only preview the first table
- **Chafa sizing fixed**: Image/video previews always use 80x80 or 60x60 character size, no adapting to terminal
- **Tool availability**: Scripts fail silently if external tools (parquet-tools, jq, markitdown, chafa) are missing; relies on catch-all text/binary fallback
