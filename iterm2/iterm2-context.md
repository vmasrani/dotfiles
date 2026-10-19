# iterm2
> iTerm2 profiles, keybindings, window arrangements, and SSH theme switcher for macOS terminal configuration.
`4 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `iTerm2-profile-Hotkey Window.json` | Master terminal profile — defines fonts (MesloLGS-NF-Regular 14), colors, hotkey (Tab), and all base settings inherited by SSH themes |
| `iterm2-keybindings.itermkeymap` | Custom key bindings export — must be manually imported in iTerm2 Preferences → Keys |
| `LOCAL-AGENTS-BRAIN.iterm2arrangement` | Saved window arrangement (binary plist) for restoring a specific tmux/agents session layout |
| `com.googlecode.iterm2.plist` | Live iTerm2 prefs (XML); includes the Cmd+Shift+L → F11 GlobalKeyMap binding |
| `backgrounds/` | The 4 profile background images (flat), referenced by absolute path from the plist |
| **ssh-themes/** | iTerm2 Dynamic Profile themes that visually distinguish SSH sessions; activated via symlink into iTerm2's DynamicProfiles dir. |

<!-- peek -->

## Conventions
- **Live prefs folder (current):** this directory is iTerm2's "Load settings from a custom folder". `install_iterm2_prefs` (`install/install_iterm2_prefs.sh`) sets `PrefsCustomFolder`, `LoadPrefsFromCustomFolder`, and `NoSyncNeverRemindPrefsChangesLostForFile_selection=2` (auto-save back to the folder) while iTerm2 is quit. iTerm2 reads/writes `com.googlecode.iterm2.plist` here, so the repo is the source of truth; commit what you like.
- `export-prefs` (uv script) is a one-time bootstrap/re-export from `defaults export`; it drops `NoSync*`/`NS*`/`SU*`/`UK*` and the custom-folder keys. After bootstrap, iTerm2 maintains the plist itself.
- The keybindings `.itermkeymap`, profile `.json`, and `.iterm2arrangement` files are now legacy (kept for reference); the plist supersedes them. The note below about manual import applies only to those.
- These files are NOT auto-symlinked into iTerm2 by `setup.sh` (except `switch-ssh-theme` → `~/bin/`). Profile JSON and keybindings must be manually imported via iTerm2 Preferences.
- The "Hotkey Window" profile is the parent for all SSH themes — it must exist in iTerm2 before SSH themes display correctly.
- The `.iterm2arrangement` file is a binary plist, not human-editable. Save/restore via iTerm2 → Window → Save/Restore Window Arrangement.

- **Wired into `setup.sh`** as the last install step (fails loud if iTerm2 is running). No manual key-binding step remains.
- **Fonts:** profiles use `MesloLGS-NF-Regular`; `install_p10k_fonts` installs the four powerlevel10k "MesloLGS NF" TTFs (separate from the Nerd Font Mono family).
- **Home rewrite:** the plist hardcodes `/Users/<name>` (working dirs, background paths). `iterm2_rewrite_home` detects any home differing from `$HOME` and rewrites it in place (then `plutil -lint`), so the committed plist drifts to the last machine's home; harmless.

## Gotchas
- Importing a new `iTerm2-profile-Hotkey Window.json` overwrites the existing profile in iTerm2 — any manual edits made inside iTerm2 will be lost. Edit the JSON file here first, then re-import.
- The hotkey trigger character is a Tab (`\t`) — check for conflicts if Tab-based shortcuts stop working.
- `iterm2-keybindings.itermkeymap` is a separate import from the profile JSON; both must be imported independently.
