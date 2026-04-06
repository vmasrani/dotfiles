# linters
> Universal linter dispatcher and config files for Python, JS/TS, shell, and Rust — used as fallback configs project-wide.
`6 files | 2026-04-05`

| Entry | Purpose |
|-------|---------|
| `lint` | Zsh script: dispatches to ruff/biome/shellcheck/shfmt/rustfmt by file extension; supports `--fix` mode and both single-file and directory (batch) modes |
| `ruff.toml` | Fallback ruff config (py312, line-length 120, double quotes) — used only when no project-local ruff config is found in parent dirs |
| `biome.json` | Fallback biome config (JS/TS: single quotes, no semicolons, 120 line width) — used only when no project-local biome.json is found in parent dirs |
| `pyrightconfig.json` | Pyright type-checker config with broad exclude list for ML experiment dirs |
| `.pylintrc` | Pylint config (legacy; ruff is preferred) |
| `.sourcery.yaml` | Sourcery AI reviewer config — runs after ruff on Python files |
| `lefthook.yml` | Git pre-commit hook: runs `lint {staged_files}` in parallel for all supported extensions |

<!-- peek -->

## Conventions

- `lint` silently skips any tool that is not installed (`command_exists` guard) — no errors if ruff/biome/sourcery are absent
- Config fallback logic: `ruff_config` and `biome_config` walk up the directory tree looking for project-local configs; only if none found do they return `--config $DOTFILES_DIR/linters/ruff.toml` (or `--config-path $DOTFILES_DIR/linters`). This means project configs always win without any special flag.
- `find_files` uses `command fd` (not the user's aliased `fd -HI`) to respect `.gitignore` — avoids accidentally linting vendored/generated files
- `lefthook.yml` here is the global dotfiles copy; it is NOT auto-symlinked by `setup.sh` — projects must install it manually or reference it

## Gotchas

- Python: `ty` (Astral's new type checker) runs in addition to ruff when installed — it is separate from pyright; both may coexist
- `sourcery review` runs on individual Python files but is skipped silently if the `sourcery` binary is absent (e.g., CI)
- `pyrightconfig.json` points `include` at `.` — if placed in a project root it covers everything, but its exclude list is ML-project-specific and will need pruning for non-ML repos
- Directory mode collects all files with `fd` then passes them as a batch to each linter — this is faster but means a single bad file can cause the whole batch to fail and report as one linter failure
