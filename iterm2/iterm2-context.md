# iterm2
> iTerm2 profiles, keybindings, window arrangements, and SSH theme switcher for macOS terminal configuration.
`4 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `iTerm2-profile-Hotkey Window.json` | Master terminal profile — defines fonts (MesloLGS-NF-Regular 14), colors, hotkey (Tab), and all base settings inherited by SSH themes |
| `iterm2-keybindings.itermkeymap` | Custom key bindings export — must be manually imported in iTerm2 Preferences → Keys |
| `LOCAL-AGENTS-BRAIN.iterm2arrangement` | Saved window arrangement (binary plist) for restoring a specific tmux/agents session layout |
| **ssh-themes/** | iTerm2 Dynamic Profile themes that visually distinguish SSH sessions; activated via symlink into iTerm2's DynamicProfiles dir. |

<!-- peek -->

## Conventions
- These files are NOT auto-symlinked into iTerm2 by `setup.sh` (except `switch-ssh-theme` → `~/bin/`). Profile JSON and keybindings must be manually imported via iTerm2 Preferences.
- The "Hotkey Window" profile is the parent for all SSH themes — it must exist in iTerm2 before SSH themes display correctly.
- The `.iterm2arrangement` file is a binary plist, not human-editable. Save/restore via iTerm2 → Window → Save/Restore Window Arrangement.

## Gotchas
- Importing a new `iTerm2-profile-Hotkey Window.json` overwrites the existing profile in iTerm2 — any manual edits made inside iTerm2 will be lost. Edit the JSON file here first, then re-import.
- The hotkey trigger character is a Tab (`\t`) — check for conflicts if Tab-based shortcuts stop working.
- `iterm2-keybindings.itermkeymap` is a separate import from the profile JSON; both must be imported independently.
