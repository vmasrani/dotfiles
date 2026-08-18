#!/usr/bin/env bash
# Install (or re-sync) the CI kit into this repo. Idempotent -- this is also the
# resync path after the canonical kit changes.
#
# It does exactly four things:
#   1. copy .ci/ci.yml -> .github/workflows/ci.yml
#   2. git config core.hooksPath .githooks
#   3. verify the justfile defines `ci-fast`, `ci-deep` and `pre-push` -- FAIL
#      LOUD, printing the exact recipes to paste, if not
#   4. re-run safely
#
# It does NOT install a pre-push hook. The drafted kit shipped one; parot-core
# already has an equivalent `.githooks/pre-push` (installed by
# `just install-hooks`) that additionally fails loud when the `pre-push` recipe
# is missing. Overwriting a working hook is churn this change does not need --
# this kit is about the required-status-check contract, not hooks.
#
# Step 3 is the load-bearing one. It is the only place the kit/project contract
# is checked, and it fails at SETUP rather than silently in CI weeks later.
#
# On the copy: GitHub Actions requires workflow files to be real files under
# .github/workflows/. They cannot be symlinks back to .ci/. So a copy plus a
# drift check is unavoidable -- there is no filesystem trick that yields a
# single source of truth on disk. That is precisely why this script must stay
# re-runnable.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

say()  { printf '  %s\n' "$*"; }
fail() { printf 'init.sh: %s\n' "$*" >&2; exit 1; }

[ -f .ci/ci.yml ]   || fail "no .ci/ci.yml here -- run this from a repo with the kit vendored."
[ -f justfile ]     || fail "no justfile -- the kit drives everything through just recipes."

# ── 3 first: verify the contract BEFORE installing anything ────────────────
# Validating up front means a repo is never left half-kitted with a workflow
# that would red on its first PR.
missing=()
for recipe in ci-fast ci-deep pre-push; do
  # `just --summary` lists recipe NAMES only, so this cannot be fooled by the
  # word appearing in a comment or inside another recipe's body.
  if ! just --summary 2>/dev/null | tr ' ' '\n' | grep -qx "$recipe"; then
    missing+=("$recipe")
  fi
done

if [ ${#missing[@]} -gt 0 ]; then
  printf 'init.sh: justfile is missing %d required recipe(s): %s\n\n' \
    "${#missing[@]}" "${missing[*]}" >&2
  cat >&2 <<'EOF'
The kit runs everything through three recipe names. Add the missing ones and
re-run. What they DO is entirely yours; only the names are contract.

    # what a PR into dev must pass
    ci: lint test

    # what a PR into main must pass -- override if the release gate is heavier
    ci-deep: ci-fast

    # the local hook: fast, no tests
    pre-push: lint

To fan a gate out across parallel CI jobs, add .ci/recipes.json:

    { "ci-fast": ["ci-fast"], "ci-deep": ["ci-fast", "test-perf"] }

EOF
  exit 1
fi
say "justfile defines ci-fast, ci-deep, pre-push"

# ── 1. install the two managed files ───────────────────────────────────────
mkdir -p .github/workflows .githooks

report_copy() {
  local src=$1 dst=$2
  if [ -f "$dst" ] && cmp -s "$src" "$dst"; then
    say "$dst already current"
  else
    cp "$src" "$dst"
    say "wrote $dst"
  fi
}

report_copy .ci/ci.yml   .github/workflows/ci.yml

# ── 2. point git at the tracked hooks dir ──────────────────────────────────
# core.hooksPath is per-clone local config, so this must run in every worktree
# and every fresh clone -- another reason it is re-runnable by design.
current=$(git config --get core.hooksPath || true)
if [ "$current" = .githooks ]; then
  say "core.hooksPath already .githooks"
else
  git config core.hooksPath .githooks
  say "set core.hooksPath = .githooks"
fi

# ── 4. done ────────────────────────────────────────────────────────────────
cat <<'EOF'

Kit installed. The required status check is the job named exactly:

    CI

Nothing else in the workflow should ever be named in a branch rule -- that
coupling is what silently orphans rulesets when a job gets renamed.
EOF
