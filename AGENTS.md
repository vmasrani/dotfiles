# Repository Guidelines

## Project Structure & Module Organization
- `shell/` holds zsh and bash startup files plus helpers; edits here feed directly into symlinked dotfiles via `install_dotfiles`.
- `install/` contains installer helpers invoked by `setup.sh`; extend `install_functions.sh` when adding new tool installers.
- `tools/` houses CLI utilities (bash and python) consumed by agents; keep entry points executable and document usage in inline help.
- `preview/` scripts render rich previews for fzf/tui flows; update when adding new filetypes.
- `maintained_global_claude/`, `codex/`, and `vscode/` store agent/editor settings; mirror structural changes in `setup.sh`.
- `local/` is ignored by git and intended for per-machine overrides such as secrets or machine-specific env files.

## Build, Test, and Development Commands
- `./setup.sh` performs the full install/symlink pass; run after structural changes to ensure new files propagate.
- `./tools/update-packages --check` audits package updates; use `--show` before committing dependency bumps.
- `./shell/update_startup.sh` refreshes shells after editing aliases or env vars.
- `python wip/test_imessage_tools.py` sanity-checks the iMessage utilities; keep similar sanity scripts in `wip/` until promotion.

## Coding Style & Naming Conventions
- Shell scripts target zsh or bash, use `set -e`, guard commands with helpers from `shell/helper_functions.sh`, and prefer lowercase-hyphen CLI names (`update-packages`).
- Python utilities follow 4-space indents, snake_case modules, and respect `linters/.pylintrc` & `pyrightconfig.json`; place shared logic in importable modules above CLI wrappers.
- Config templates (.tmux.conf, .p10k.zsh, VS Code profiles) stay declarative and avoid machine-specific paths—redirect overrides to `local/`.

## Testing Guidelines
- Run `shellcheck shell/*.sh` and targeted checks on any new shell script.
- Execute `pyright` and `pylint` against touched Python files (`pyright tools/your_script.py`, `pylint tools/your_script.py`) before submitting.
- Document manual verification steps in the PR when scripts depend on macOS- or Linux-only tooling; attach command transcripts or sample outputs.

## Commit & Pull Request Guidelines
- Follow the existing history: one-line, imperative commit subjects (`fix tmux theme`, `add helix bindings`) and group related symlink or installer changes together.
- Reference impacted directories in the body, list follow-up tasks if work remains, and avoid bundling unrelated tweaks.
- Pull requests should include a concise summary, verification notes, and any screenshots or GIFs for preview/UI changes; link issues or TODOs when applicable.

## Security & Configuration Tips
- Never commit credentials; keep secrets in `local/.secrets` or environment-managed stores referenced by `local/.local_env.sh`.
- When adding installers, confirm they respect both macOS and Linux branches in `install_functions.sh` and do not prompt for credentials interactively.
