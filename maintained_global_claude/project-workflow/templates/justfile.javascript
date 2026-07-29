# Starter justfile. This project owns it -- edit freely.
#
# The CI contract is only the two aggregates at the bottom. Every other recipe
# here is convention: rename, split, or delete them as the project grows, as
# long as `ci-fast` and `ci-deep` keep running real checks.
#
# ── THE ONE INVARIANT THIS FILE EXISTS TO HOLD ───────────────────────────────
# A check that cannot run must FAIL, never pass. Every recipe with an external
# prerequisite -- a binary, a fixture, a built tree, a credential -- states it
# with `_require-cmd` / `_require-file` FIRST. A recipe that shrugs at a
# missing prerequisite and exits 0 is indistinguishable from one that verified
# the code, and it stays that way until something ships broken.
#
# The same rule downstream: a test runner told to skip when its fixture is
# absent must make the skip VISIBLE and non-zero at the gate. "Skipped" and
# "passed" must never be the same observable state.

# Fail loud when a required command is absent. Usage: `_require-cmd node npm`
_require-cmd +CMDS:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    for c in {{CMDS}}; do command -v "$c" >/dev/null 2>&1 || missing+=("$c"); done
    if ((${#missing[@]})); then
        printf 'MISSING PREREQUISITE: %s\n' "${missing[@]}" >&2
        printf 'These checks cannot run. Install them and re-run -- do not skip past this.\n' >&2
        exit 1
    fi

# Fail loud when a required file or directory is absent. Usage:
# `_require-file dist/bundle.js fixtures/corpus.json`
_require-file +PATHS:
    #!/usr/bin/env bash
    set -euo pipefail
    missing=()
    for p in {{PATHS}}; do [ -e "$p" ] || missing+=("$p"); done
    if ((${#missing[@]})); then
        printf 'MISSING PREREQUISITE: %s\n' "${missing[@]}" >&2
        printf 'The checks that read these would SKIP and still report success. Refusing.\n' >&2
        exit 1
    fi

# Called by ci-fast.yml and ci-deep.yml before any check runs, gated there on a
# committed package-lock.json. setup-node installs a node RUNTIME only, and the
# checks below refuse to install for themselves -- they fail loud on a missing
# tree instead. `npm ci` needs the lockfile and errors without one; that is the
# intended failure, not a case to paper over with `npm install`.
install-js:
    npm ci

# node_modules EXISTING is not node_modules being CURRENT. A tree left over
# from an older lockfile installs no new dependency, so a whole test file can
# fail to load while the run summary still says "passed". Compare the tree
# against the lockfile, not against the void.
#
# Regenerate the lockfile with the npm major that CI runs, not your local one:
# a lockfile written by npm 11 is rejected by the npm 10 on the node-22 runner.
#   npx npm@10 install --package-lock-only && npx npm@10 ci --os=linux --cpu=x64
deps-current:
    #!/usr/bin/env bash
    set -euo pipefail
    if [ ! -d node_modules ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
        echo "node_modules is absent or older than package-lock.json -- running npm ci" >&2
        npm ci
    fi

fmt-check:
    npx prettier --check .

lint:
    npx eslint .

typecheck:
    npx tsc --noEmit

test:
    npm test

build:
    npm run build

# Fast pre-push gate: formatting + lint, NO tests. `.githooks/pre-push` runs
# this, so keep it quick -- a slow gate is a bypassed gate.
pre-push: fmt-check lint

# Install the pre-push gate into this clone. Once per clone, per machine.
install-hooks:
    git config core.hooksPath .githooks
    @echo "git hooks active (core.hooksPath=.githooks); pre-push now runs the lint gate"

ci-fast: (_require-cmd "node" "npm") deps-current fmt-check lint typecheck test build

# Grow this as real integration/e2e suites appear.
ci-deep: ci-fast
