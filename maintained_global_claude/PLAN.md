# Simplify the project-workflow CI approach

## Context

The `project-workflow` kit (`maintained_global_claude/project-workflow/`) installs a
Claude-first GitHub workflow — Issue → worktree → PR into `dev` → CI — into a project.
Its first real end-to-end run (parot-core) surfaced five bugs and one design gap.

The five bugs are **already fixed** in the working tree:

| Bug | Fix |
|---|---|
| Scripts not on `PATH` | Symlinked `tools/{setup-project,project-workflow}`; made `SCRIPT_DIR` resolve through symlinks |
| `gh repo view -R <path>` at 4 sites (no such flag; `-R` takes `OWNER/REPO`) | New `gh_in_repo` helper that `cd`s into the repo |
| `stage_workflow` ended in `[[ $codex == true ]] && git add` → returns 1 → `set -e` kills the run when you answer "No" | Codex prompt and all its plumbing removed |
| `ensure_dev` assumed no local `dev` → `fatal: a branch named 'dev' already exists` | Handles all three states; refuses to publish a `dev` that is behind the default branch |
| `\n` rendered literally in `gum style` output | Multiple args instead of escapes |

**The design gap, re-diagnosed.** The original plan treated "mature repos can't satisfy
the contract" as the problem and proposed machinery to close it (`import`ed contract
justfiles, per-language fragments, an `/adopt-ci` command, a two-phase resumable setup).
Review showed the contract itself is the problem: **CI only ever executes two commands —
`just ci-fast` and `just ci-deep`** (`repository/.github/workflows/agent-*.yml`) — while
`check` enforces a 9-recipe vocabulary that nothing in CI consumes. The other seven names
are an internal decomposition convention promoted into a contract. Shrink the contract to
what CI runs and the mature-repo adoption problem disappears: parot-core's entire
migration becomes two aggregate recipes written against recipes it already has.

A second, heavier layer also buys almost nothing: the private
`sophiaconsulting/agent-workflow` reusable-workflow repo — with its `publish` command,
immutable-tag lifecycle, org-level workflow-access API call, sed-rendered wrapper
workflows, and `workflow_call` input threading — centralizes ~40 lines of toolchain
setup. The whole point of a justfile contract is that CI doesn't need project specifics;
the `languages`/`working-directory`/`just-recipe` inputs re-import them.

## Design principles

1. **The contract is what CI executes.** Two recipes: `ci-fast` and `ci-deep`. Nothing
   else is required. Sub-recipes (`fmt`, `lint`, `test`, …) are project convention, not
   contract.
2. **Vendor static workflows; no shared repo, no templating.** Each project gets
   placeholder-free workflow files copied in by `init`. Toolchain setup keys off file
   existence (`hashFiles('**/Cargo.toml')` etc.), so one template serves every project
   and `render_missing`/sed go away. Updating projects later is a `copy_missing` re-run,
   the right trade for a single-owner handful of repos.
3. **Setup installs and reports; it never opens a PR.** Commit/push/PR happen through
   the existing task flow — policy §3 and `/open-pr` already gate PRs on a green
   `just ci-fast`. "Never open a red PR" is achieved by never opening PRs from setup,
   which deletes the resume/phase/`--finish` machinery before it's built.
4. **The project owns its justfile.** Greenfield gets a per-language starter copied in
   once; `init` never manages, imports, or regenerates recipes in an existing justfile.
5. **No check may pass while doing nothing** (fail-loud doctrine). No
   `echo "not applicable"` recipes that read as green: `ci-deep` simply aggregates only
   what exists (minimum: `ci-deep: ci-fast`), and grows when real suites are added.

## Part A — kit changes

### A1. Shrink the contract (`bin/project-workflow check`)

- Required recipes: `ci-fast`, `ci-deep` only.
- Required files: drop `.agent-workflow/ci.yml` (the manifest is written by `init` and
  required by `check`, but consumed by **nothing** — the data lived in the wrapper
  inputs). Keep the rest of the file list, same `agent-fast.yml`/`agent-deep.yml` names.
- When a recipe is missing, print a suggested body, e.g.
  `ci-fast: fmt-check lint test  # aggregate your existing fast checks` — actionable in
  place of the old bare `missing recipe` line. This replaces the planned `/adopt-ci`
  command entirely; Claude (or the operator) writes the two aggregates in-session.

### A2. Vendored static workflows (templates)

Rewrite `templates/ci-fast.yml` and `templates/ci-deep.yml` as complete workflows
(currently they are `workflow_call` wrappers). Content comes from the existing
`repository/.github/workflows/agent-*.yml`, adapted:

- Same job names — `Project checks`, `Secret scan`, `Workflow lint`,
  `Deep integration checks` — so `gh-setup`'s required-status-check contexts still match.
- Toolchain steps conditioned on tree content, not a `languages` input:
  `dtolnay/rust-toolchain@stable` if `hashFiles('**/Cargo.toml') != ''`,
  `astral-sh/setup-uv` if `pyproject.toml`, `setup-node` if `package.json`.
- Same triggers as today: fast on PRs into `dev`; deep on `dev` pushes, PRs into `main`,
  and `workflow_dispatch`.
- Zero placeholders → `init` installs them with `copy_missing`; delete `render_missing`.

Keep the Gitleaks org-license note in the README.

### A3. Deletions

- `publish` command and the `repository/` directory — no shared workflow repo, no tag
  lifecycle, no `actions/permissions/access` API call.
- `templates/ci-manifest.yml` and every reference to `.agent-workflow/ci.yml`.
- `--with-codex`, `--require-codex`, `templates/AGENTS.md` — unreachable since the Codex
  prompt was removed.
- `templates/justfile.stub` (replaced by A5 starters).

### A4. `setup-project` stops at install + report

`existing_project` becomes: preconditions → `ensure_dev` (unchanged, already fixed) →
`project-workflow init` → `project-workflow check` → print the report and next steps
(write the aggregates, then use the normal Issue/`/open-pr` flow). No language prompt
(nothing consumes it for existing repos), no branch creation, no commit, no push, no
`gh pr create` — which also deletes the `bin/setup-project:147` branch-collision
hard-fail and any need for resume logic. `init` and `check` are idempotent, so re-running
`setup-project` is naturally safe.

`new_project` keeps its current shape (create repo → init → commit → push `main`/`dev` →
`gh-setup --apply`): a fresh repo with a real starter justfile is green by construction.
It keeps the language prompt solely to pick which starter justfile to copy, preselected
by detecting `Cargo.toml`/`pyproject.toml`/`package.json` in… nothing yet — greenfield
has no tree, so just ask.

### A5. Per-language starter justfiles (greenfield only)

`templates/justfile.rust`, `templates/justfile.python`, `templates/justfile.javascript`:
plain project-owned starting points with real commands and the two contract aggregates,
e.g. for Rust:

```just
fmt-check:
    cargo fmt --all --check
lint:
    cargo clippy --workspace --all-targets -- -D warnings
test:
    cargo nextest run --workspace
build:
    cargo build --workspace

ci-fast: fmt-check lint test build
ci-deep: ci-fast
```

Copied by `new_project` only when no justfile exists; never touched again. No stub
recipes that fail on purpose, no recipes that pass while doing nothing.

### A6. Documentation

Rewrite the kit `README.md`: the CI-contract table shrinks to `ci-fast`/`ci-deep`,
the publish/tag section goes away, and a short note replaces the planned hazard scanner:
private git dependencies (e.g. a `Cargo.toml` git-pin to another private repo) fail CI at
dependency resolution because `GITHUB_TOKEN` cannot clone other private repos — fix with
`--no-default-features`-style feature gating or a deploy key. Diagnosing such reds is
what `/check-pr` is for; no generic manifest scanner.

## Part B — bats suite

`tools/tests/project-workflow.bats`, following `tools/tests/testq.bats` conventions
(hermetic, `BATS_TEST_TMPDIR`, no network, fake `gh` on `PATH` recording argv to a trace
file). Written against the simplified surface:

- **The `-R` regression**: no recorded `gh` invocation ever passes a filesystem path
  where `OWNER/REPO` belongs.
- `ensure_dev` × three states: `origin/dev` exists; local-only `dev` (publish); neither
  (create). Plus the refusal when local `dev` is behind the default branch.
- `init` idempotency across repeated runs: existing `CLAUDE.md` and justfile preserved;
  policy link appended exactly once; workflow files created once and kept.
- `check`: green when `ci-fast`/`ci-deep` exist (regardless of other recipe names);
  missing recipe → exit 1 and the suggested body appears in output.
- `existing_project` records **no** `git push` and no `gh pr create` in any run.
- Installed workflow templates contain no `__PLACEHOLDER__` tokens and parse as YAML.

## Part C — parot-core, as first customer

Branch `chore/add-agent-workflow` (PR #6) already exists with the old 7-file layout.
Rework it on the simplified kit:

1. Re-run `project-workflow init` after the kit changes; delete `.agent-workflow/ci.yml`
   and replace the wrapper workflows with the vendored static ones.
2. Add the two aggregates to the existing justfile: `ci-fast` mapping onto the existing
   `fmt`/`lint`/`test` (splitting fmt out of `lint` if needed so it isn't run twice);
   `ci-deep: ci-fast gauntlet-all`. The cross-stack e2e suites need the sibling
   `../parot` checkout, so they stay out of `ci-deep` — no placeholder recipe pretends
   otherwise.
3. Resolve the private `parot-web` git dep (`crates/cli/Cargo.toml:39`) for CI:
   build/test with `--no-default-features` in the affected recipes, or add a deploy key.
4. `just ci-fast` green locally → push, get PR #6 green in real CI
   (`gh pr checks --watch`), merge, then `project-workflow gh-setup --dir . --apply`.

## Out of scope (noted for later)

- **Trunk-based vs `dev`/`main`**: dropping `dev` would halve the remaining git
  machinery (protection payloads, PR targets, fast/deep trigger matrix, `ensure_dev`),
  at the cost of deep failures surfacing post-merge. Severable decision; the kit keeps
  `dev`/`main` for now and parot-core PR #6 already targets `dev`.
- No `/adopt-ci` command, no `import`ed contract justfile, no private-dep scanner, no
  two-phase resumable setup — all obsoleted by the contract shrink above.

## Verification

1. `bats tools/tests/project-workflow.bats` — full suite green; note the test count and
   reconcile it on later runs.
2. `shellcheck` clean on both scripts; `bash -n` clean.
3. Dangling-reference sweep over the kit:
   `rg -i 'codex|AGENTS\.md|publish|render_missing|ci-manifest|agent-workflow/\.github|justfile\.stub'`
   returns nothing unexpected.
4. Greenfield end-to-end in a throwaway local repo with the fake `gh`: `new_project` →
   starter justfile in place → `just ci-fast` passes with the starter recipes.
5. Mature-repo end-to-end: `existing_project` on a fixture repo with a bespoke justfile
   stops cleanly at the report, and the report names exactly `ci-fast`/`ci-deep` with
   suggested bodies.
6. parot-core: `just ci-fast` green locally, PR #6 green in real CI, merge, `gh-setup
   --apply` protects `dev`/`main`.
