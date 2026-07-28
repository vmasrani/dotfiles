# Starter justfile. This project owns it -- edit freely.
#
# The CI contract is only the two aggregates at the bottom. Every other recipe
# here is convention: rename, split, or delete them as the project grows, as
# long as `ci-fast` and `ci-deep` keep running real checks.

# Called by ci-fast.yml and ci-deep.yml before any check runs, gated there on a
# committed package-lock.json. setup-node installs a node RUNTIME only, and the
# checks below refuse to install for themselves -- they fail loud on a missing
# tree instead. `npm ci` needs the lockfile and errors without one; that is the
# intended failure, not a case to paper over with `npm install`.
install-js:
    npm ci

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

ci-fast: fmt-check lint typecheck test build

# Grow this as real integration/e2e suites appear.
ci-deep: ci-fast
