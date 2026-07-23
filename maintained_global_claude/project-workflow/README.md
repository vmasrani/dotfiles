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

**New project**: creates the private `sophiaconsulting` repository, installs the
workflow and a per-language starter `justfile`, pushes `main` and `dev`, and
applies branch protection. A fresh repo with real starter recipes is green by
construction.

**Existing project**: creates `dev` when needed, installs the workflow files,
runs `check`, and stops at a report. It never commits, pushes, or opens a PR —
that goes through the normal Issue/worktree/`/open-pr` flow, which already gates
a PR on a green `just ci-fast`. Never opening a red PR is achieved by never
opening one from setup. Both `init` and `check` are idempotent, so re-running
`setup-project` is safe.

For scripting or advanced use:

```bash
project-workflow init  --dir /absolute/path/to/project
project-workflow check --dir /absolute/path/to/project
```

`init` never replaces an existing instruction, workflow, or `justfile`. It adds
a short managed policy link to an existing `CLAUDE.md` and uses its own
`agent-fast.yml`/`agent-deep.yml` workflow names, so existing project automation
is preserved.

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

The secret-scan job uses Gitleaks Action v2. Before applying the kit to an
organization repository, add the organization-approved `GITLEAKS_LICENSE`
Actions secret (and grant it to the participating repositories); the action
requires it for organization-owned repositories.

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
