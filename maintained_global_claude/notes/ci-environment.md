# Reproduce CI's environment, don't approximate it — full incident record

Split out of the global `CLAUDE.md` (2026-07-27). The three load-bearing rules stayed
inline there; this file holds the evidence behind them. Read it when a CI run is red for
an environment reason and the inline rules aren't enough.

**A fix verified on this Mac with these tool versions is not verified.** Three consecutive
red CI runs (parot-radar #17, 2026-07-24) each came from assuming the local environment
was the CI environment:

- **CI recipes run under the RUNNER's shell, not yours.** `#!/usr/bin/env zsh` in a justfile recipe → `exit 127, zsh: No such file or directory` on ubuntu-latest. Use `#!/usr/bin/env bash` in any recipe CI invokes. This is the one carve-out to the global "always zsh over bash" rule — that rule governs scripts *you* run.
- **Pin the tool version to what CI actually runs, then generate with it.** `npm ci` failed `EBADPLATFORM @esbuild/netbsd-arm64` (27 lockfile entries flagged `"extraneous": true`). I regenerated with local **npm 11** — which prunes nested optional deps that **npm 10** requires — so the next run failed differently: `Missing: @esbuild/win32-x64@0.28.1 from lock file`. The node-22 runner ships npm 10. Fix: `npx npm@10 install --package-lock-only`.
- **Verify the way CI sees it, with CI's flags.** `npx npm@10 ci --os=linux --cpu=x64` (exit 0, `@esbuild/linux-x64` present in the tree) is evidence; `npm ci` passing on darwin-arm64 is not. Same shape for any platform-conditional dep — esbuild, rollup, swc, sharp, playwright.
- **Two red runs in a row on the same file means the DIAGNOSIS is wrong, not the patch.** Stop patching; go read what the runner has (`gh run view --log-failed`, the setup-node step's `npm -v`) before touching it again.
- **Record the version constraint next to the artifact.** A regenerated lockfile carries no memory of which npm produced it — a comment block in the recipe that generates or consumes it is the only thing standing between the next agent and mistake #2.
