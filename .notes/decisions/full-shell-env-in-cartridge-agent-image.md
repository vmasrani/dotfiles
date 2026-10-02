---
id: full-shell-env-in-cartridge-agent-image
title: Cartridge CI agent image stays slim; the full zsh/tmux dotfiles bake was built, measured and rejected
category: decisions
created: 2026-09-18
updated: 2026-09-18
tags: [github-actions, docker, ci, cartridge, measured, reversed]
source: conversation
confidence: high
related: []
---

## Decision

`ghcr.io/sophiaconsulting/cartridge-agent` is a **slim toolchain image**: ubuntu:24.04,
pinned Rust, prebuilt `cargo-nextest`/`just`/`eza`/`fd`, `rg`, `uv`, plus the narrow
dotfiles slice (`maintained_global_claude/` → `/root/.claude`, six `tools/ctx-*` →
`/usr/local/bin`). It does **not** run dotfiles' `setup.sh` and does not contain
zprezto, p10k, tmux plugins, helix, node, go or bun. SSH access (tmate) gives a plain
terminal. The image is used through cloud agent sessions, not lived in.

## Why the full bake was reversed (all measured 2026-09-18)

The full bake was implemented and proven (cartridge PR #1022: `./setup.sh` at build
time, sanity layer incl. per-plugin tmux checks, green build, published once). It was
dropped because:

- **Pull cost:** the multi-GB image took **94 s** to pull on a cold GitHub-hosted
  runner ("Initialize containers"); hosted runners pull on every job.
- **Disk:** the first full build died at buildkit export on the ~14 GB runner disk and
  needed a ~25 GB "free disk" step to pass.
- **No CI speed payoff:** toolchain/setup steps in cartridge CI are **24–90 s per job**
  against **12–38 min** of compile + test (1–5 %). A 94 s pull is a net loss.
- **The heavy gates cannot be container jobs anyway:** ci.yml `checks` and
  bump-core-impl `bump` delete 20–30 GB of host disk before building (a container job
  cannot), and client-build / release-rehearsal run nested `docker run` musl-cross
  builds (no daemon in a container job).
- **Usage:** the owner only interacts through cloud sessions, so a p10k/tmux shell in
  the container has no audience.

## Where CI time actually goes (the real lever)

The same `just ci-fast` measured 12m34s with a warm Rust cache (ci.yml `checks`) and
37m57s cold (agent-fast `chokepoints`, the pre-dev gate). Compile reuse — cache key
alignment between those jobs, then nextest archive/partitioning or sccache depending
on the compile-vs-test split — is where minutes are, not the container.

## What survives from the attempt

- dotfiles `setup.sh` overhaul (PR #4): prebuilt binaries instead of source builds,
  helix builds only custom grammars, loud/verified tmux plugin install, resumable
  installs with a kill-and-resume CI job, per-tool timing table. First-run install
  went from 7–10 min to 3.5–5 min on all three CI platforms. Independent of the image.
- `tools/agent-ssh` (dotfiles PR #7): gum tool to check/publish the image, start a
  timed job inside it, and SSH in.
- A workflow that has only a `workflow_dispatch` trigger cannot be dispatched until it
  exists on the default branch (or has run once): give it a `push` trigger on its own
  path with `if: github.event_name == 'workflow_dispatch'` on the job to register it.
- In `container:` jobs GitHub forces `HOME=/github/home`; pin `HOME=/root` when the
  image's config lives in /root.

## Implications

- `notify-cartridge-agent-image.yml` only needs to fire on `maintained_global_claude/**`
  and the six `tools/ctx-*` files (narrowed back after the reversal).
- If an interactive full-shell container is ever wanted again, PR #1022's branch
  (`agent-image-full-shell`) is the working reference; build it as a separate tag,
  never as the image CI or agents pull.
