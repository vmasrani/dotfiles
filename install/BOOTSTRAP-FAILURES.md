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

### 7. Re-runs reinstall and recompile tools that are already there (2026-09-04)

- **Symptom:** not a crash, but the dominant cost. Across three re-runs of
  `setup.sh` on one box, fzf was wiped and re-cloned every time, opencode was
  reinstalled twice, and Rust `Compiling` lines went 78, 145, 792 as tools like
  just, taplo, tealdeer, and markdown-oxide were rebuilt from source although
  they were already installed.
- **Cause:** `install_if_missing` skips a step when the command is on PATH, and
  nothing put `~/.cargo/bin`, `~/.local/bin`, `~/go/bin`, `~/.fzf/bin`,
  `~/bin`, or nvm's bin on PATH before those checks. Installers that only
  export PATH for the rest of their own run, or append it to `.zshrc`, are
  invisible to the next invocation. `~/.fzf/bin` was also missing from the
  shell PATH list entirely.
- **Fix:** `bootstrap_path` at the top of `setup.sh` prepends every user bin
  directory before any check; `~/.fzf/bin` added to the shell PATH list; fzf
  no longer deletes and re-clones itself. In the same pass: `cargo-binstall`
  and one `install_github_release` helper replace every compile-from-source
  step that has a prebuilt binary (only simple-completion-language-server
  still builds from git, it publishes no binaries); all apt repositories are
  registered once followed by a single `apt-get update`; helix comes from its
  PPA instead of snap; neomutt was dropped from the installer.
- **Regression check:** a second `setup.sh` run on a finished box must print
  zero lines matching `Installing|Compiling|Downloading|Cloning into`. The CI
  workflow in `.github/workflows/install.yml` asserts exactly that.

### 8. Latent: install_zsh asked a yes/no question (2026-09-04)

- **Symptom:** never fired on Hetzner, because `hetzner-vm` preinstalls zsh
  through cloud-init. Found while writing the CI workflow. On any fresh box
  without zsh, `setup.sh` would have stopped at a `read -p` prompt with no
  terminal, before installing anything.
- **Cause:** `install_zsh` prompted before installing, although it is only ever
  reached through `install_if_missing zsh`, so the answer was always yes. It
  also ran a full `apt-get upgrade` as a side effect.
- **Fix:** no prompt, no upgrade; install the packages through `apt_install`
  and set the login shell. There are no other interactive reads left in the
  installer (`rg 'read -p' install/ setup.sh` is empty).

### 9. Release helper died silently: gh not logged in plus set -e (2026-09-04)

- **Symptom:** the first acceptance run of the tightened installer stopped
  after "Installing markdown-oxide..." with exit code 4 and no error line.
  Everything before it, through the language servers, took 5 minutes instead of
  the previous 20-plus.
- **Cause:** `install_github_release` asked `gh` for the release assets first.
  `gh` was installed by an earlier step but not logged in, and it exits 4 in
  that state. The result was captured with a bare assignment, and under `set -e`
  a failing command substitution in a bare assignment aborts the whole script
  before the curl fallback or any error message runs. Exit code 4 was gh's.
- **Fix:** use `gh` only when `gh auth status` succeeds, otherwise the public
  GitHub API through curl; every command substitution in the helper that can
  fail carries `|| true` followed by an explicit empty check that prints what
  was not found and returns 1; the API calls send `GH_TOKEN` or
  `GITHUB_TOKEN` when present so CI runners stay under the unauthenticated
  rate limit.
- **Rule going forward:** in this codebase `set -e` is on, so
  `x="$(cmd)"` is a hidden exit point. Any substitution whose failure should
  be reported, not fatal, must be written `x="$(cmd || true)"` and checked.

### 10. Found by CI: bun reinstalled every run, pq never installed (2026-09-04)

- **Symptom:** the first CI run's bare `ubuntu:24.04` job failed the
  second-run assertion with `bun is not installed. Installing bun...` and
  `pq is not installed. Installing pq...`. Its raw log also showed
  `install_pq: command not found: wget` immediately followed by
  `✓ pq installed successfully.`
- **Cause:** `bootstrap_path` did not include `~/.bun/bin`, so bun looked
  missing on every re-run. `install_pq` downloaded with wget, which a bare
  image does not have, and printed success regardless of the download's
  exit status, so pq was never installed and reinstalled every time. The
  Hetzner boxes hid both: their image ships wget, and bun was found through a
  PATH line its installer appended to `.zshrc`.
- **Fix:** `~/.bun/bin` added to the PATH bootstrap; `install_pq` uses curl,
  which the installer already relies on everywhere, and fails loudly when the
  download fails. The other two CI failures were workflow bugs: the hosted
  Ubuntu runner has no zsh, and anonymous GitHub API calls from runner IPs
  are rate-limited, so the workflow installs zsh and passes `GH_TOKEN`.

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
- **2026-09-04, after entries 7 to 9 (tightened installer):**
  `hetzner-vm create worker2` from scratch took 359 seconds end to end,
  server creation included, with setup exit 0 and every expected tool on
  PATH. The only compilation left was simple-completion-language-server
  (317 `Compiling` lines). A second `setup.sh` run on the finished box took
  28 seconds and printed zero install, compile, download, or clone lines.
