# Bootstrap failure log

Every time `./setup.sh` dies on a fresh machine, the failure gets an entry here
and a permanent fix in the repo. The goal is that a headless Ubuntu box built by
`tools/hetzner-vm create` (cloud-init, no terminal, no stdin) finishes `setup.sh`
unattended with exit 0.

Rules for the fix, not the workaround:

- Fix the installer function in `install/install_functions.sh`, never the box.
- Anything that can prompt must be told the answer up front (`-y`,
  `DEBIAN_FRONTEND=noninteractive`, `--no-input`, and so on).
- `setup.sh` runs with `set -e`, so any non-zero step kills the whole run. A step
  that is allowed to fail must say so explicitly and visibly.
- Reproduce on a real box before closing an entry: `hetzner-vm create <name>`
  checks `/root/dotfiles-setup.exit` and prints the log tail on failure.

## Entries

### 1. apt prompts for confirmation and aborts (2026-09-04)

- **Symptom:** setup log ends with `Do you want to continue? [Y/n] Abort.` right
  after "Linking tools to /root/tools". zsh, gum, and tmux are installed; uv,
  fzf, ripgrep, fd, eza, and zprezto are missing.
- **Cause:** `install_meslo_font` ran `sudo apt install fontconfig` without `-y`.
  With no stdin, apt reads EOF as "no" and exits non-zero, and `set -e` stops
  the script. cloud-init still reports "done", so `hetzner-vm create` used to
  print success over a half-built box.
- **Fix:** `-y` on that call (the only apt call in the repo missing it);
  `setup.sh` exports `DEBIAN_FRONTEND=noninteractive` on Linux so dpkg
  configuration prompts are auto-answered too; `hetzner-vm create` records the
  `setup.sh` exit status on the box and fails loudly with the log tail when it
  is non-zero.

### 2. Helix grammar fetch dies on a dead upstream repo (2026-09-04)

- **Symptom:** after every other grammar reports `now on <sha>`, the log ends
  with `Failure 1/1: gotmpl Git command failed.` and
  `fatal: could not read Username for 'https://github.com'`. Everything after
  `install_helix` in `setup.sh` is skipped.
- **Cause:** Helix's built-in grammar list sources `gotmpl` from a GitHub repo
  that now returns 404. Git treats the 404 as "maybe private" and tries to
  prompt for a username; with no terminal that fails, and `install_helix` ran
  `hx --grammar fetch` unguarded under `set -e`.
- **Fix:** `editors/hx_languages.toml` overrides the gotmpl grammar source (or
  excludes it if the fork is unreachable); both grammar steps run with
  `GIT_TERMINAL_PROMPT=0` so a dead repo fails fast; and a grammar failure is a
  visible warning rather than a fatal stop, matching `update_helix_grammars`.
  An editor grammar is not something a worker box needs to boot.
