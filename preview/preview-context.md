# preview

## Purpose
Collection of file preview utilities for FZF and terminal viewing. Handles various data formats (CSV, JSON, Parquet, PyTorch, NumPy, Feather, pickle) and media types (images, PDFs, videos, notebooks) with syntax highlighting and pretty-printing.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| fzf-preview.sh | Main dispatcher that routes files to appropriate previewers based on file extension | Previews 20+ file types |
| torch-preview.py | Loads and pretty-prints PyTorch model tensors | torch version info, tensor data |
| pkl-preview.py | Displays pickle files with rich formatting, handles pandas objects | Formatted pickle contents |
| feather-preview.py | Reads and displays Apache Feather columnar data | pandas DataFrame |
| npy-preview.py | Renders NumPy arrays as matplotlib heatmaps for 2D/3D data | Text output or PNG via chafa |
| torch-preview.sh | Legacy shell wrapper for torch preview (deprecated by .py version) | torch tensor display |

## Patterns
- **Format dispatcher**: Single entry point (fzf-preview.sh) routes to specialized previewers via file extension matching
- **Language-specific handlers**: Python scripts for data-heavy formats (torch, numpy, pandas), shell for light formats
- **Rich formatting**: Uses `rich`, `glow`, `bat`, `jq` for colored terminal output
- **Graceful degradation**: Falls back to syntax highlighting (bat) or tldr when specialized tools unavailable
- **Inline dependencies**: Python scripts use uv inline script format (`#!/usr/bin/env -S uv run --script`)

## Dependencies
- **External CLI tools**: sqlite3, parquet-tools, jq, bat, markitdown, glow, chafa, vd, pdftotext, ffmpegthumbnailer, tldr, eza, rich
- **Python libraries**: torch, pandas, pyarrow, numpy, matplotlib, rich, pickle (stdlib)
- **Media viewers**: chafa (terminal image viewer), ffmpegthumbnailer (video thumbnails)

## Entry Points
- **fzf-preview.sh**: Primary entry point, typically invoked by FZF as a preview command for file browsing
- Individual .py/.sh scripts: Called as subcommands from fzf-preview.sh or directly from shell

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| .claude | Claude AI logs (post_tool_use.json, stop.json, chat.json, subagent_stop.json) | no |
