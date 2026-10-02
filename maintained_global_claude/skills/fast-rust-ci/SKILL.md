---
name: fast-rust-ci
description: Bootstraps fast GitHub Actions CI for a Rust project — a prebuilt toolchain container (GHCR) + sccache + the mold linker — from every mistake made wiring this up on cartridge (container default shell, bind-mount rm, git dubious-ownership, SSH host-key verification, sccache/incremental conflict). Load before setting up CI for a new Rust repo, or before adding a container image / sccache / mold to an existing one.
---

# Fast Rust CI: container + sccache + mold

Three independent, stackable layers. Measured on a real compile-heavy gate (cartridge, `just bump-core`, same 184-error stopping point each time):

| Layer | What it removes | Measured effect |
|---|---|---|
| Prebuilt GHCR container (toolchain + CLI tools baked in) | Fixed per-run install cost (`dtolnay/rust-toolchain`, `taiki-e/install-action@nextest`/`@just`, `astral-sh/setup-uv`, apt installs) | ~40–90s flat, so % varies with job length — biggest relative win on short "fast" gates |
| `mold` linker, baked into the image | Link time | ~20% faster, every run, no warmup needed (14m28s → 11m35s) |
| `sccache` + GitHub Actions cache backend | Recompiling unchanged code | ~65 more points once warm (11m35s → 2m38s = **82% faster than baseline**). **Zero** benefit on the very first run that populates the cache — don't judge it from a cold run. |

Do all three. They compose. Order of implementation below builds up in the same order.

## Layer 1 — the container image

Dockerfile: pin Rust via rustup (`rust-toolchain.toml`'s version), pin every CLI tool version as a build ARG, install prebuilt release binaries (not source builds) via a small `dl()` curl+tar+install helper. **Image is toolchain-only** — never bake in project source or a dependency snapshot. Project source comes from `actions/checkout` every run; a private git dependency is fetched fresh by cargo's own git+ssh using whatever rev `Cargo.toml` pins. This means the image never needs rebuilding when the consuming project OR its dependencies change — only when the toolchain itself does (Rust version, Dockerfile edit). Wire the image-build workflow's triggers to those paths only, and make PR-triggered builds build-only (no `:latest` push) — only a push to the default branch or an explicit manual dispatch should publish, or a PR under review can silently become the live image every machine pulls.

**End every Dockerfile with a fail-loud sanity `RUN` gate** checking every tool actually resolves in a plain non-login shell (`rustc --version`, `cargo nextest --version`, `just --version`, `mold --version`, `command -v ssh-agent`, `grep -q github.com /etc/ssh/ssh_known_hosts`, …). This is what caught two of the bugs below at build time instead of at first consumption.

Known gotchas, all hit building this the first time:

- **Container jobs default to `sh`, not `bash`.** `set -euo pipefail` dies with "Illegal option -o pipefail" under dash even though the image has bash. Always add `defaults: run: shell: bash` at job level on any job with a `container:` key.
- **`container.volumes` bind-mounts are literal mountpoints.** `rm -rf $mount` deletes the contents fine, then fails "Device or resource busy" trying to remove the mountpoint itself. Use `find "$mount" -mindepth 1 -delete` and never touch the mountpoint.
- **Git "dubious ownership" inside the container.** Checked-out files' owning UID doesn't match the container's UID, and `actions/checkout`'s own `safe.directory` grant lives in a temporary `$HOME` it discards after its step — it does NOT survive to a later step that shells out to `git` directly. Bake `RUN git config --system --add safe.directory '*'` into the image (system-wide `/etc/gitconfig`, not a per-user file, so it survives every `$HOME` any step runs under).
- **Missing `openssh-client`.** A minimal image has no `ssh-agent` binary, so `webfactory/ssh-agent` (or any deploy-key loading) fails `spawnSync ssh-agent ENOENT`. Add `openssh-client` to the apt install list.
- **Missing SSH host keys for git+ssh cargo dependencies.** `ubuntu-latest` runners pre-seed `~/.ssh/known_hosts`/`/etc/ssh/ssh_known_hosts` with `github.com`; a minimal custom image doesn't. Result: cargo's own `git fetch` over ssh for a private dependency fails `Host key verification failed` — even though the deploy key authenticates fine and `actions/checkout` (which manages its own host-key trust separately) already succeeded earlier in the same job. Fix: hardcode GitHub's officially published, stable SSH host keys (from GitHub's own docs — look them up fresh, don't trust a stale copy) into `/etc/ssh/ssh_known_hosts` at build time. **Do not use `ssh-keyscan` at build time** — Docker's build-sandbox network often can't reach `github.com:22`, and `ssh-keyscan` fails silently (empty output, exit 0), so an unchecked version ships a broken image. The fail-loud sanity gate's `grep` is what catches this.
- **Private GHCR image pulls need explicit auth**: job/workflow `permissions: packages: read` plus `container.credentials: {username: github.actor, password: secrets.GITHUB_TOKEN}`.

## Layer 2 — mold

Ubuntu 24.04+: `apt-get install mold` gets a current-enough version. GCC 13 recognizes `-fuse-ld=mold` by name directly — no clang, no absolute path needed. Bake mold into the image (apt), but set the flag in the **consuming workflow's env**, not in the image or a repo-committed `.cargo/config.toml`:

**mold is Linux-only in practice — don't try to install it locally on macOS.** Homebrew's `mold` formula (checked at 2.42.1) states outright: "Support for Mach-O targets has been removed." Mach-O is macOS's binary format, so a Homebrew-built mold cannot link macOS binaries at all; `-fuse-ld=mold` would just fail on a Mac. The linker speedup is CI-container-only (Linux); local dev on macOS gets no equivalent from mold and needs no workaround — sccache alone still works fine locally, independent of linker choice.

```yaml
env:
  RUSTFLAGS: "-C link-arg=-fuse-ld=mold"
```

Keeping it in workflow env (not `.cargo/config.toml`) keeps it visible to `Swatinem/rust-cache`'s `env-vars` hashing and doesn't silently break local dev machines that don't have mold installed.

## Layer 3 — sccache

Use `mozilla-actions/sccache-action` **per-run**, not a static binary baked into the image. The action is what correctly wires the GitHub Actions cache backend's short-lived tokens (`SCCACHE_GHA_ENABLED`); hand-replicating that token plumbing to save a few seconds of install time is where you'll get it wrong.

```yaml
- uses: mozilla-actions/sccache-action@v0.0.11   # check for a newer tag
  if: hashFiles('**/Cargo.toml') != ''
env:
  RUSTC_WRAPPER: sccache
  SCCACHE_GHA_ENABLED: "true"
  CARGO_INCREMENTAL: "0"    # REQUIRED — sccache flatly rejects incremental compilation
```

Forgetting `CARGO_INCREMENTAL: "0"` fails the compile immediately with "incremental compilation is prohibited." This is not optional.

`sccache` and `Swatinem/rust-cache` are complementary, keep both: rust-cache caches a whole `target/`+registry blob scoped to one branch lineage (fast for same-branch reruns, cold on any new branch or evicted cache); sccache caches individual compiler invocations by content hash, shared across every branch and job that happens to compile the same code — including matrix legs deliberately siloed from each other by `shared-key`.

## Verifying the speedup — don't trust a fast-failing job

A `workflow_dispatch` that resolves to a gate containing an early, unrelated, already-broken check (a lint/static-analysis step that fails in under a minute) gives **zero timing signal** — it never reaches real compilation. Before trusting any "N% faster" number:

1. Pick (or dispatch) a recipe that reliably burns real compile/link time.
2. Compare against the **same stopping point** both times (identical error count/file if it's expected to fail on unrelated content) — apples to apples.
3. Expect the very first post-sccache run to show `0` cache hits — that run is populating the cache, not benefiting from it. Judge sccache's payoff only from a *second* comparable run.
