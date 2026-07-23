# Project workflow kit

This directory is the reusable, Claude-first project workflow. It is designed
for repositories that use GitHub, GitHub Actions, and the GitHub CLI (`gh`).
It does not create or configure remote GitHub state until its operator runs an
explicit `gh` command.

## Use on a project

For the guided setup of either a new private repository or an existing one,
run this single command:

```bash
./bin/setup-project
```

It creates a new private `sophiaconsulting` repository or opens a migration PR
for an existing project, creates `dev` when needed, installs the workflow, and
applies protection for new repositories. Existing projects are protected only
after their migration PR has merged.

For scripting or advanced use, run:

From this directory, run:

```bash
./bin/project-workflow init --dir /absolute/path/to/project --workflow-ref <immutable-tag>
./bin/project-workflow check --dir /absolute/path/to/project
```

`init` never replaces an existing instruction, workflow, or `justfile`. It adds
a short managed policy link to existing `CLAUDE.md`/`AGENTS.md` files and uses
its own `agent-fast.yml`/`agent-deep.yml` workflow names, so existing project
automation is preserved. Add the required `just` recipes to existing projects,
then rerun `check`.

The generated wrapper workflows call the private `sophiaconsulting/agent-workflow`
repository. Publish it with `project-workflow publish --tag v1` after authenticating
with `gh`; the command verifies it is private before reporting success. Do not leave
projects permanently pinned to a moving branch.

The secret-scan job uses Gitleaks Action v2. Before applying the kit to an
organization repository, add the organization-approved `GITLEAKS_LICENSE`
Actions secret (and grant it to the participating repositories); the action
requires it for organization-owned repositories.

## GitHub setup

The bootstrap intentionally does not mutate remote settings. After reviewing
the generated files, configure labels and branch rules with the commands
printed by `project-workflow gh-setup`. Run those commands through `gh` only.

## CI contract

Every participating project must provide these `just` recipes:

| Recipe | Purpose |
| --- | --- |
| `fmt-check`, `lint`, `typecheck`, `test-unit`, `build` | Fast deterministic checks |
| `test-integration`, `test-e2e` | Service/browser checks; print `not applicable` if absent |
| `ci-fast` | Calls the fast checks only |
| `ci-deep` | Calls `ci-fast` plus integration and end-to-end checks |

The fast wrapper runs on feature PRs into `dev`. The deep wrapper runs on
`dev` changes and on the `dev` to `main` PR. Project commands determine which
test files and services actually apply.
