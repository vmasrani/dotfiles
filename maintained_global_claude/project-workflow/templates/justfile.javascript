# Starter justfile. This project owns it -- edit freely.
#
# The CI contract is only the two aggregates at the bottom. Every other recipe
# here is convention: rename, split, or delete them as the project grows, as
# long as `ci-fast` and `ci-deep` keep running real checks.

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

ci-fast: fmt-check lint typecheck test build

# Grow this as real integration/e2e suites appear.
ci-deep: ci-fast
