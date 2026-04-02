# vscode
> VSCode profiles for Python, Markdown, and LaTeX workflows — exported as `.code-profile` JSON blobs for manual import.
`3 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `python.code-profile` | Python dev profile: tab size 4, word wrap, material icons, Cursor AI integration, conda env path |
| `markdown.code-profile` | Markdown-focused profile (separate settings from python profile) |
| `latex.code-profile` | LaTeX writing profile |

<!-- peek -->

## Conventions
- Files are VSCode's exported profile format: a single-line JSON blob with doubly-escaped settings inside. Do not hand-edit — import/export via VSCode's profile UI (`File > Preferences > Profiles > Export`).
- These profiles are NOT symlinked by `setup.sh` or `install_dotfiles` — they must be imported manually into VSCode via the Profiles UI.

## Gotchas
- The python profile hardcodes `~/miniconda/envs/ml3/bin/python` as the Python interpreter path. On a new machine this path likely won't exist and IntelliSense will silently fail until the interpreter is updated.
- `python.autoComplete.extraPaths` includes `~/.python` — this directory must exist or extension may warn on startup.
- `formatOnSave` is disabled for Python; `formatOnType` is enabled. Don't assume save-triggered formatting will run.
