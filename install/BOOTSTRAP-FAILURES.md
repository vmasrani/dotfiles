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

### 3. apt package name differs from Homebrew (2026-09-04)

- **Symptom:** `E: Unable to locate package bats-core`, setup exits 100 right
  after the Rust and Go tool installs. Everything from `install_bats` onward in
  `setup.sh` is skipped (ruff, biome, shfmt, the language servers, and more).
- **Cause:** `install_bats` passed the Homebrew name `bats-core` to
  `install_on_brew_or_mac`, which uses its first argument as the apt name. On
  Ubuntu the package is `bats`.
- **Fix:** `install_on_brew_or_mac "bats" "bats-core"`. Every other package that
  goes through that helper (bfs, csvkit, isync, msmtp, neomutt, notmuch,
  sccache, shellcheck, urlscan, unzip) was checked against apt on Ubuntu 24.04
  and resolves under the same name.

### 4. Shell startup errors on env files that may not exist (2026-09-04)

- **Symptom:** not fatal, but every zsh start on the fresh box printed
  `.zshenv:32: no such file or directory: /root/.cargo/env` before Rust was
  installed and `.zshrc:113: no such file or directory: /root/.local/bin/env`
  afterwards. The second one persists because uv on this box was not installed
  by the standalone installer that writes that file.
- **Cause:** both files were sourced unconditionally.
- **Fix:** guard each with `[[ -f ... ]] &&`, the pattern `.zshrc` already used
  for cargo on line 89.

### 5. debconf dialog hangs the run because sudo drops the env (2026-09-04)

- **Symptom:** a from-scratch `hetzner-vm create` never finished. On the box,
  `sudo apt -y install msmtp` had been sitting for 17 minutes on a whiptail
  dialog asking about AppArmor support, with `cloud-init status` still
  "running". Entry 1's export of `DEBIAN_FRONTEND=noninteractive` was in place
  and did nothing.
- **Cause:** every apt call runs under `sudo`, and Ubuntu's default sudoers has
  `env_reset`, which strips `DEBIAN_FRONTEND` before apt sees it. Verified with
  `sudo env | grep -c DEBIAN_FRONTEND` printing 0. Entry 1 only covered
  prompts from apt itself, not from package configuration scripts.
- **Fix:** two layers. `setup.sh` persists the choice inside debconf with
  `debconf-set-selections` so it survives any env reset, and every apt install
  in `install/install_functions.sh` goes through one `apt_install` helper that
  passes `DEBIAN_FRONTEND=noninteractive` through `sudo env` explicitly.

### 6. pm2 cannot find the mail sync script (2026-09-04)

- **Symptom:** the very last step, `install_neomutt`, ends with
  `[PM2][ERROR] Script not found: /root/dotfiles/mailsync-daemon` and setup
  exits 1. Found by the first from-scratch `hetzner-vm create` after entries
  1 to 5 were fixed; the tool's new exit-status check caught it and printed the
  log tail, which is exactly what it is for.
- **Cause:** `pm2 start mailsync-daemon` uses a bare name, which pm2 resolves
  against the current directory rather than PATH. The script lives at
  `mutt/scripts/mailsync-daemon`. The step passed on worker1 only because that
  run went over a non-login ssh shell where nvm, and therefore pm2, was not on
  PATH, so the branch was skipped with an info line.
- **Fix:** start pm2 with the absolute path
  `$HOME/dotfiles/mutt/scripts/mailsync-daemon`.
- **Open question, not a bootstrap bug:** a worker box has no
  `~/.mutt_secrets`, so the mail sync daemon it now starts will fail on every
  tick until one is added. Harmless, but noisy in `pm2 logs`.

## Verified unattended run

Re-verify after any change to `setup.sh` or `install/install_functions.sh`
that touches Linux: `hetzner-vm create <name>` on a fresh box must print its
success box, which only happens when it reads exit 0 from
`/root/dotfiles-setup.exit`.

- **2026-09-04, entries 1 to 6:** `hetzner-vm create worker2` on a fresh
  Ubuntu 24.04 ccx53 in nbg1 finished with setup exit 0 on the first attempt
  after fix 6 landed. All expected tools were on PATH afterwards. The run still
  spent most of its time compiling Rust crates (1015 `Compiling` lines), which
  the installer tightening that followed removes.
