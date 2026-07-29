# Project workflow kit

This directory is the reusable, Claude-first project workflow: Issue → worktree
→ PR into `dev` → CI. It targets repositories that use GitHub, GitHub Actions,
and the GitHub CLI (`gh`). It does not create or configure remote GitHub state
until its operator runs an explicit `gh` command.

## Use on a project

For the guided setup of either a new private repository or an existing one,
run this single command from anywhere (both scripts are symlinked into
`~/dotfiles/tools`, which is on `PATH`):

```bash
setup-project
```

For non-interactive use (agents, CI, scripts), pass a subcommand and flags — the
TUI prompts are skipped entirely:

```bash
setup-project new --name my-project --language rust   # --dir defaults to $PWD/my-project
setup-project migrate --dir /path/to/existing/repo    # --dir defaults to $PWD
```

`--language` is one of `rust`, `python`, `javascript`. Run `setup-project --help`
for the full usage. Any missing required flag, unknown flag, or unknown
subcommand fails loudly instead of falling back to a prompt.

**New project**: creates the private `sophiaconsulting` repository, installs the
workflow, a per-language starter `justfile` and the `.githooks/pre-push` gate,
pushes `main` and `dev`, and opts the repo into the strict `main` ruleset. A
fresh repo with real starter recipes is green by construction.

Branch rules are **not** applied per repository any more. They live once as org
rulesets (see `rulesets/`), already cover every repo including ones that do not
exist yet, and the only per-repo step is flipping the `agent-workflow` custom
property. `dev` intentionally carries no required checks so direct pushes keep
working; `.githooks/pre-push` is the gate on that path, and it runs
`just pre-push` (format + lint, never tests).

**Existing project**: creates `dev` when needed, installs the workflow files,
runs `check`, and stops at a report. It never commits, pushes, or opens a PR —
that goes through the normal Issue/worktree/`/open-pr` flow, which already gates
a PR on a green `just ci-fast`. Never opening a red PR is achieved by never
opening one from setup. Both `init` and `check` are idempotent, so re-running
`setup-project` is safe.

For scripting or advanced use:

```bash
project-workflow init        --dir /absolute/path/to/project
project-workflow check       --dir /absolute/path/to/project
project-workflow sync-policy --dir /absolute/path/to/project
```

`init` never replaces an existing instruction, workflow, or `justfile`. It adds
a short managed policy link to an existing `CLAUDE.md` and uses its own
`agent-fast.yml`/`agent-deep.yml` workflow names, so existing project automation
is preserved.

## Keeping existing projects in sync

`init` copies kit files once; without a sync mechanism, existing projects stay
frozen on whatever policy text they were born with. `project-workflow
sync-policy --dir <repo>` byte-compares every verbatim-managed file (the
vendored policy, workflow files, pre-push hook, PR/issue templates) against the
kit's canonical copies. If everything matches it reports up to date and exits;
otherwise it opens a `chore/policy-sync` PR into `dev` carrying exactly the
changed managed files. It never touches merged or generated files (`justfile`,
the project `CLAUDE.md`), never pushes to `dev` directly, and never merges its
own PR. The canonical policy carries a `<!-- policy-version: N -->` stamp so a
repo's vintage is greppable; byte-comparison, not the stamp, decides whether a
sync is needed. After any change to `policy/` or `templates/` in this kit, run
`sync-policy` across the active repos.

A repo can keep a deliberate divergence in a managed file by putting the exact
substring `kit-sync: project-owned` in that file (conventionally in a comment,
next to the rationale for the divergence). `sync-policy` never copies over a
marker-carrying file — it reports `skipped (project-owned)` and lists the file
in the PR body — and `check` shows it as `ok (project-owned)`. The trade is
explicit: that file stops receiving upstream template fixes until the marker is
removed. Two failure modes taught us both sides of this line: a deliberately
trimmed job clobbered back in (→ mark the file project-owned) and a live CI fix
that never reached the template (→ upstream the fix into `templates/`, don't
mark). If the change is right for every repo, it belongs in the kit; the marker
is only for divergences that are right for one repo.

## Three lanes: strict, fast, chore

The default lifecycle is **strict**: one issue, one branch, one worktree, one
PR, merged by a separate review agent.

The **fast lane** batches 2–4 issues labeled `fast-lane` into one branch/PR:
claim by assignment plus one comment on the lead issue, one commit per issue so
revert/bisect stay per-issue, one `Closes #<n>` line per issue in the PR body,
author self-merges on green.

The label is granted at **triage — a separate act** (`gh-setup` creates the
label; a triage pass over 2+ already-filed issues applies it, before any branch
exists for them). Never label an issue whose branch you already hold, and never
label a lone issue to lighten ceremony for work already underway. Eligibility
is a four-part predicate, recorded on the issue: ≤3 files known before any code
is written; no new interface, schema, or dependency; acceptance is an existing
check or one assertion; independent of the filing session's design work.

The **chore lane** drops the issue for work that records no decision — a
formatter run, a lockfile regen, a comment typo, a dependency repin: branch
`chore/<slug>`, green `ci-fast`, PR into `dev`, author self-merges. It drops
the issue, never the branch, the gate, or the PR — `dev` is what every
in-flight worktree branches from.

Green `ci-fast` and green PR checks gate all three lanes, and `main` remains
the user's alone. Full rules live in `policy/AGENT_WORKFLOW.md`.

## CI contract

**The contract is what CI executes: two recipes.**

| Recipe | Purpose |
| --- | --- |
| `ci-fast` | Everything that must pass before a PR into `dev` is opened. Runs on every PR into `dev`. |
| `ci-deep` | The slower gate. Runs on `dev` pushes, on the `dev` → `main` PR, and on `workflow_dispatch`. |

Nothing else is required. `fmt-check`, `lint`, `test`, and friends are project
convention — useful decomposition, not contract. A mature repository adopts the
kit by writing two aggregates over recipes it already has:

```just
ci-fast: fmt lint test
ci-deep: ci-fast gauntlet-all
```

The minimum honest `ci-deep` is `ci-deep: ci-fast`; grow it as real integration
and end-to-end suites appear. Never add a recipe that passes while doing
nothing (`echo "not applicable"`) — a check that cannot run must be visibly
absent, not silently green.

## Workflows

`init` vendors two placeholder-free workflow files into the project. There is no
shared workflow repository and no templating: toolchain setup keys off what is
actually in the tree (`hashFiles('**/Cargo.toml')`, `pyproject.toml`,
`package.json`), so one template serves every project. Updating projects later
is a `copy_missing` re-run after deleting the old file.

The secret-scan job installs the raw `gitleaks` CLI (version-pinned, checksum
verified) rather than `gitleaks-action`, deliberately: the action demands a
`GITLEAKS_LICENSE` secret for organization-owned repositories, the raw CLI does
not. It scans full history and hard-fails on any finding. The escape hatch for
a confirmed false positive is a fingerprint entry in `.gitleaksignore` — never
a `.gitleaks.toml` path allowlist, which silently swallows real keys repo-wide.

## GitHub setup

The bootstrap intentionally does not mutate remote settings for existing
projects. After the migration PR merges, configure labels and branch rules with
the commands printed by `project-workflow gh-setup`; `--apply` runs them. The
required status-check contexts are the job names in the vendored workflows:
`Project checks`, `Secret scan`, `Workflow lint`, `Deep integration checks`.

## Known CI hazard: private git dependencies

A manifest that pins another **private** repository by git URL (e.g. a
`Cargo.toml` `git = "https://github.com/owner/private-repo"`) fails CI during
dependency resolution: the workflow's `GITHUB_TOKEN` is scoped to this
repository only and cannot clone another private one. Fix it by feature-gating
the dependency out of the CI path (`--no-default-features` in the affected
recipe) or by adding a deploy key. Diagnosing reds like this is what
`/check-pr` is for; the kit does not ship a generic manifest scanner.
