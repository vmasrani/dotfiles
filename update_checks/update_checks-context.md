# update_checks
> Shell library for checking outdated packages across brew, apt, cargo, npm, uv, and pip with file-based caching.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `update_config.sh` | Defines all config vars (`UPDATE_CACHE_DIR`, timeouts, startup flags) — sourced first by `update_functions.sh` |
| `update_functions.sh` | All check logic; entry points are `check_all_updates`, `show_update_commands`, `refresh_update_cache` |

<!-- peek -->

## Conventions
- `update_functions.sh` sources `update_config.sh` via hardcoded absolute path `~/dotfiles/update_checks/update_config.sh`, not relative — do not move files independently.
- Cache files are written to `~/.cache/dotfiles_updates/` as hidden files named `.{pm}_updates` (e.g., `.brew_updates`). Cache is invalidated by age only, not by content change.
- All config vars in `update_config.sh` support env var override (e.g., `UPDATE_CACHE_TIMEOUT=${UPDATE_CACHE_TIMEOUT:-10800}`), so they can be tuned per-machine in `local/.local_env.sh` without editing tracked files.

## Gotchas
- `check_uv_updates` counts all installed uv tools as "needing attention" — it does not actually detect outdated tools. It only prints a reminder to run `uv tool list`, making the count meaningless for upgrade decisions.
- `stat` cross-platform fallback in `is_cache_valid` uses `-f %m` (macOS) then `-c %Y` (Linux) with `||`; if both fail it returns `0`, treating the cache as always-expired rather than always-valid.
- `check_all_updates` returns `$updates_found` (a boolean string, not an integer), which means `return $updates_found` always returns exit code 0 when false and a non-zero when true — the opposite of normal shell conventions.
- `cargo-install-update` (external binary from `cargo-update` crate) must be installed separately; the check silently skips if missing.
