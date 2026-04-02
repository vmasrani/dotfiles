# backup
> Archived tmux theme entry-point scripts (Dracula and Catppuccin) kept as reference before theme migration.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `dracula.sh` | Full Dracula theme entry point — sets all tmux status-bar colors, plugin dispatch loop, and window styling via `@dracula-*` tmux options |
| `catppuccin.sh` | Catppuccin Macchiato variant of the same entry point — identical structure but uses Catppuccin palette; maps Dracula semantic names (`white`, `gray`, `cyan`, etc.) to Catppuccin equivalents for backward compat |

<!-- peek -->

## Conventions

These scripts are NOT the active theme scripts — they are backups of upstream theme entry points before local customization. The active scripts live in `../` (the parent `tmux/scripts/` directory).

Both scripts source a `utils.sh` from their `current_dir`, which does not exist in this backup directory. Running either script directly will fail because `utils.sh` is missing.

## Gotchas

`catppuccin.sh` defines Dracula-named semantic aliases (`white`, `gray`, `dark_purple`, etc.) that map to Catppuccin colors — color variable names do NOT match their visual appearance. For example, `cyan` resolves to Catppuccin `sapphire` (#7dc4e4).

Both scripts use `eval "$colors"` to apply user-overridden colors from the `@dracula-colors` tmux option, which allows arbitrary code execution via tmux config.
