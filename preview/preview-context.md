# preview
> FZF preview scripts for 30+ file types (data, ML, docs, images, archives) symlinked to `~/bin/`.
`6 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `fzf-preview.sh` | Main dispatcher — resolves symlinks, detects file type by extension, delegates to specialized tools or Python scripts |
| `feather-preview.py` | Renders Apache Feather files via pandas; uv inline deps (no install needed) |
| `pkl-preview.py` | Renders pickle files with rich formatting; handles DataFrame, dict, list, and arbitrary objects |
| `npy-preview.py` | Renders NumPy `.npy` arrays |
| `torch-preview.py` | Inspects PyTorch `.pt`/`.pth` checkpoint files |
| `onnx-preview.py` | Inspects ONNX model files |

<!-- peek -->

## Conventions
- All Python scripts use `#!/usr/bin/env -S uv run --script` with inline `# /// script` dependency blocks — no venv or pip install required. These are self-contained executables.
- Scripts are symlinked to `~/bin/` (not `~/tools/`) via `install_dotfiles` in `install/install_functions.sh`. The `fzf-preview.sh` calls the Python scripts by their bare names (e.g., `feather-preview`, `pkl-preview`), relying on `~/bin/` being in PATH.
- The `preview()` wrapper in `fzf-preview.sh` applies a 5-second `timeout` to every external command — add new handlers inside `preview` calls to maintain this safety net.
- Markdown files use `mdterm` (not `bat` or `glow`) for rendering; `markitdown` converts office formats before piping to `mdterm`.

## Gotchas
- `.zip` files use `vd -b` (visidata) piped to `colorize-columns`, not `unzip -l` — requires visidata installed.
- Binary detection uses `file --brief --mime-encoding` and falls through to `file --brief` output for truly unrecognized binaries; adding a new extension requires placing the case branch BEFORE the catch-all `*` block.
- `console = Console(force_terminal=True)` in the Python scripts is necessary because stdout is piped in fzf preview pane — without it, rich strips color codes.
- Video preview writes to `/tmp/thumbnail.png` with no cleanup — concurrent fzf previews of different videos will race on that path.
