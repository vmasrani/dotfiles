# themes
> iTerm2 ANSI palette switcher scripts — apply color themes live via OSC escape sequences for visual SSH session distinction.
`2 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `gruvbox-dark.zsh` | Sets all 16 ANSI colors + fg/bg/cursor to Gruvbox Dark; intended as the SSH session theme to visually distinguish remote from local |
| `palenight.zsh` | Restores the Palenight palette; use to revert after an SSH session ends |

<!-- peek -->

## Conventions
- Both scripts silently no-op if not running in iTerm2 (`TERM_PROGRAM != "iTerm.app"` and no `ITERM_SESSION_ID`) — safe to source anywhere but only take effect in iTerm.
- Inside tmux, OSC sequences are wrapped in a tmux passthrough (`\033Ptmux;\033...\033\\`) so they reach the outer terminal. Without this wrapping, iTerm2 ignores the sequences entirely.
- Each script exports `DOTFILES_THEME` so other scripts can branch on the active theme.

## Gotchas
- Sourcing these scripts changes the live terminal palette immediately for the current window/tab only — they do not persist across new tabs or sessions (iTerm2 profile is unchanged).
- The scripts must be `source`d, not executed as subprocesses; running them as a child process means the OSC sequences go to the subshell's stdout but do not affect the parent terminal.
- A related but separate SSH-theme system exists in `iterm2/ssh-themes/` using JSON profiles and `switch-ssh-theme`; that system changes the full iTerm2 profile, while these scripts only patch the ANSI palette.
