# GitHub / CI operational lore (cross-repo)

Overflow from `~/.claude/CLAUDE.md` — read on demand when debugging CI or workflow problems in kitted repos. Kit policy itself lives in each repo's `.agent-workflow/AGENT_WORKFLOW.md` (canonical kit: `~/dotfiles/maintained_global_claude/project-workflow/`).

## Measured state of dev-branch CI (2026-08)

- dev PRs run ONLY Secret scan + Workflow lint (~2 min). **Neither is actually REQUIRED** — measured 2026-08-12: `gh api repos/<o>/<r>/branches/dev/protection` returns "Branch not protected"; the only rules touching dev are `deletion`/`non_fast_forward` from the baseline ruleset. "Merge once every required check passes" is therefore vacuous on dev — deliberate: dev stays advisory-only, all enforcement lives at dev→main.
  - DISCREPANCY: the kit README still *describes* Secret scan/Workflow lint as "required status-check contexts" (README.md:158-160). The measurement above disagrees; trust the measurement, and reconcile the README via a kit change (then `sync-policy`) if this bites.
- No Linux test job on dev PRs and no CI at all on dev pushes — `Project checks` and `ci-deep`'s `push: [dev]` trigger were removed 2026-08-03 to cut Actions spend, which had reached ~2846 wall-clock min/30d across 8 repos. The full suite runs only at dev→main; `just ci-fast` in the worktree is the only gate before dev.

## A CI job that has never gone green is a bug, not a gate

Before trusting *or* deleting a job, measure it: `gh run list --workflow=<f> --limit 20 --json conclusion,createdAt,updatedAt`. A wall of `cancelled` at exactly `timeout-minutes` means the job cannot finish, not that it's flaky — zero signal at full runner billing. This went unnoticed for months in parot-core (0 success / 14 timeout / 1 fail) and cartridge. Fix the timeout (split the recipe into parallel jobs) or remove the trigger; never leave it running.

## gh token vs .github/workflows/

`gh`'s default `repo`-scoped token cannot write `.github/workflows/` — the Contents API returns 403. Push workflow changes over SSH with git, or `gh auth refresh -s workflow`.

## Related

- Environment reproduction (npm lockfile pinning, runner shells): `notes/ci-environment.md`
- Unpinned `uvx` in CI recipes: recorded in auto-memory (`uvx-unpinned-ci-reproducibility-trap`)
- Private-repo git-URL dependency hazard: kit README.md ("CI hazards")
