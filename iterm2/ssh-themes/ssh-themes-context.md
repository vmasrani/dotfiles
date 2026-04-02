# ssh-themes
> iTerm2 Dynamic Profile themes that visually distinguish SSH sessions; activated via symlink into iTerm2's DynamicProfiles dir.
`11 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `switch-ssh-theme` | Interactive gum-based selector; symlinks chosen theme JSON to `~/Library/Application Support/iTerm2/DynamicProfiles/ssh-server.json` |
| `01-subtle-tint.json` – `10-red-alert.json` | iTerm2 DynamicProfile JSON snippets — each defines an "SSH-Server" profile that inherits from "Hotkey Window" parent profile |

<!-- peek -->

## Conventions
- Each JSON defines a profile named `"SSH-Server"` with a fixed Guid and `"Dynamic Profile Parent Name": "Hotkey Window"` — the parent profile must exist in iTerm2 or inheritance silently fails.
- Theme activation works by symlinking a file (not copying) — iTerm2 watches DynamicProfiles and reloads live; no iTerm2 restart needed.
- Only one theme is active at a time via a single symlink at `ssh-server.json`; switching replaces the symlink atomically with `ln -sf`.
- Themes only set background/badge/tab color — all other terminal settings (font, cursor, keybindings) come from the parent "Hotkey Window" profile.

## Gotchas
- The "Hotkey Window" parent profile must already exist in iTerm2; if it is missing, the SSH-Server profile loads with no visual styling applied and no error is shown.
- `switch-ssh-theme` reads Guid numbering from filenames (`01-`, `02-`, etc.) — adding a new theme requires keeping zero-padded numeric prefix and updating the `descriptions` array in the script to match.
- The script uses zsh glob qualifier `(N)` for null-glob safety and `(N[1])` for first-match selection — these are zsh-only and will break in bash.
