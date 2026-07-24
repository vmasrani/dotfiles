#!/usr/bin/env bats
# Behaviour tests for the `project-workflow` kit: the `project-workflow` CLI and
# the `setup-project` guided bootstrap.
#
# HERMETIC BY CONSTRUCTION
#   Every test builds a throwaway git repository plus a LOCAL bare "origin"
#   under BATS_TEST_TMPDIR, and puts fake `gh` and `gum` executables at the head
#   of PATH. Nothing here touches the network, GitHub, or any real repository.
#   The fake `gh` appends its full argv to $GH_TRACE, so tests assert on what
#   would have been sent rather than on side effects.
#
#   Run:  bats tools/tests/project-workflow.bats
#         bats -f 'ensure_dev' tools/tests/project-workflow.bats   # one group

setup() {
    KIT="${BATS_TEST_DIRNAME}/../../maintained_global_claude/project-workflow"
    WORKFLOW="$KIT/bin/project-workflow"
    SETUP="$KIT/bin/setup-project"
    [ -x "$WORKFLOW" ] || {
        echo "project-workflow not executable at $WORKFLOW" >&2
        return 1
    }
    [ -x "$SETUP" ] || {
        echo "setup-project not executable at $SETUP" >&2
        return 1
    }

    BIN="${BATS_TEST_TMPDIR}/bin"
    mkdir -p "$BIN"
    export GH_TRACE="${BATS_TEST_TMPDIR}/gh-trace"
    export GUM_TRACE="${BATS_TEST_TMPDIR}/gum-trace"
    export GUM_ANSWERS="${BATS_TEST_TMPDIR}/gum-answers"
    export GUM_CURSOR="${BATS_TEST_TMPDIR}/gum-cursor"
    : >"$GH_TRACE"
    : >"$GUM_TRACE"
    : >"$GUM_ANSWERS"
    echo 0 >"$GUM_CURSOR"
    write_fake_gh
    write_fake_gum
    export PATH="$BIN:$PATH"

    ORIGIN="${BATS_TEST_TMPDIR}/origin.git"
    REPO="${BATS_TEST_TMPDIR}/project"
    # Mirror the branch name the migration uses (setup-project's CI_SETUP_BRANCH).
    CI_SETUP_BRANCH_NAME="chore/ci-setup"

    export GIT_CONFIG_GLOBAL="${BATS_TEST_TMPDIR}/gitconfig"
    export GIT_CONFIG_NOSYSTEM=1
    : >"$GIT_CONFIG_GLOBAL"
    git config --global user.email tester@example.com
    git config --global user.name Tester
    git config --global init.defaultBranch main
}

# ── fakes ─────────────────────────────────────────────────────────────────

# Records every invocation, then answers only the queries the kit makes. Any
# unrecognised subcommand exits 0 so a test failure reads as a wrong assertion
# rather than a crash inside the fake.
write_fake_gh() {
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GH_TRACE"
case "$*" in
    'auth status') exit 0 ;;
    *'--json defaultBranchRef'*) echo main ;;
    *'--json nameWithOwner --jq'*) echo sophiaconsulting/fixture ;;
    *'--json nameWithOwner'*) echo '{"nameWithOwner":"sophiaconsulting/fixture"}' ;;
    'pr create'*) echo https://github.com/sophiaconsulting/fixture/pull/1 ;;
esac
exit 0
EOF
    chmod +x "$BIN/gh"
}

# `gum input` and `gum choose` pop the next line of $GUM_ANSWERS. `gum style`
# echoes its non-flag arguments so report text stays visible in $output. Every
# invocation records its full argv to $GUM_TRACE so tests can assert that script
# mode never reaches for an interactive prompt (`gum input`/`gum choose`).
write_fake_gum() {
    cat >"$BIN/gum" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$GUM_TRACE"
sub="$1"
shift
case "$sub" in
    input|choose|filter)
        n=$(cat "$GUM_CURSOR")
        n=$((n + 1))
        echo "$n" >"$GUM_CURSOR"
        sed -n "${n}p" "$GUM_ANSWERS"
        ;;
    style|join|format)
        for arg in "$@"; do
            case "$arg" in
                --*) continue ;;
            esac
            printf '%s\n' "$arg"
        done
        ;;
    confirm) exit 0 ;;
esac
exit 0
EOF
    chmod +x "$BIN/gum"
}

answers() {
    printf '%s\n' "$@" >"$GUM_ANSWERS"
    echo 0 >"$GUM_CURSOR"
}

# ── fixtures ──────────────────────────────────────────────────────────────

# A repository with one commit on `main`, pushed to a local bare origin. Callers
# add a justfile and branches to describe the state under test.
make_repo() {
    git init -q --bare -b main "$ORIGIN"
    git init -q -b main "$REPO"
    echo '# fixture' >"$REPO/README.md"
    git -C "$REPO" add -A
    git -C "$REPO" commit -qm 'initial'
    git -C "$REPO" remote add origin "$ORIGIN"
    git -C "$REPO" push -q -u origin main
}

# A bespoke justfile: contract-satisfying, but with none of the old
# fmt-check/typecheck/test-unit vocabulary, which is the whole point of the
# contract shrink.
write_bespoke_justfile() {
    cat >"$REPO/justfile" <<'EOF'
gauntlet:
    @true

polish:
    @true

ci-fast: polish
ci-deep: ci-fast gauntlet
EOF
}

# A justfile that follows the house convention (fmt-check/lint/test/build) but
# has NEITHER aggregate. The migration should append ci-fast/ci-deep and, because
# the sub-recipes exist, pass the local `just ci-fast` gate.
write_convention_justfile() {
    cat >"$REPO/justfile" <<'EOF'
fmt-check:
    @true

lint:
    @true

test:
    @true

build:
    @true
EOF
}

publish_dev() {
    git -C "$REPO" branch dev main
    git -C "$REPO" push -q -u origin dev
}

commit_all() {
    git -C "$REPO" add -A
    git -C "$REPO" commit -qm "${1:-work}"
}

migrate() {
    answers 'Migrate an existing GitHub project' "$REPO"
    run "$SETUP"
}

# ── assertions ────────────────────────────────────────────────────────────

# The reported bug: `gh repo view -R <path>`. -R/--repo take OWNER/REPO and gh
# silently mis-resolves anything else, so no recorded invocation may ever pass a
# filesystem path there.
assert_no_path_repo_flag() {
    local line value
    while read -r line; do
        value="$(printf '%s\n' "$line" | awk '{for (i=1;i<NF;i++) if ($i=="-R" || $i=="--repo") print $(i+1)}')"
        [ -n "$value" ] || continue
        for v in $value; do
            case "$v" in
                */*/* | /*)
                    echo "gh received a path where OWNER/REPO belongs: $line" >&2
                    return 1
                    ;;
            esac
            [[ "$v" =~ ^[[:alnum:]_.-]+/[[:alnum:]_.-]+$ ]] || {
                echo "gh received a non-OWNER/REPO value: $line" >&2
                return 1
            }
        done
    done <"$GH_TRACE"
}

refute_trace() {
    ! grep -q -- "$1" "$GH_TRACE" || {
        echo "unexpected gh invocation matching '$1':" >&2
        cat "$GH_TRACE" >&2
        return 1
    }
}

# Fails if `gum <sub>` was ever invoked. Anchored on the first argv word so a
# subcommand name appearing inside `gum style` report text can't false-positive.
refute_gum() {
    ! grep -qE "^$1( |\$)" "$GUM_TRACE" || {
        echo "unexpected gum invocation of '$1':" >&2
        cat "$GUM_TRACE" >&2
        return 1
    }
}

assert_trace() {
    grep -q -- "$1" "$GH_TRACE" || {
        echo "expected a gh invocation matching '$1', trace was:" >&2
        cat "$GH_TRACE" >&2
        return 1
    }
}

# ── the -R regression ─────────────────────────────────────────────────────

@test "gh -R: gh-setup never passes a filesystem path where OWNER/REPO belongs" {
    make_repo
    run "$WORKFLOW" gh-setup --dir "$REPO" --apply
    [ "$status" -eq 0 ]
    assert_no_path_repo_flag
}

@test "gh -R: gh-setup dry run never passes a filesystem path where OWNER/REPO belongs" {
    make_repo
    run "$WORKFLOW" gh-setup --dir "$REPO"
    [ "$status" -eq 0 ]
    assert_no_path_repo_flag
}

@test "gh -R: the full migration never passes a filesystem path where OWNER/REPO belongs" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    assert_no_path_repo_flag
}

# ── ensure_dev, three states plus the stale-dev refusal ───────────────────

@test "ensure_dev: an existing origin/dev is used as-is" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    local before
    before="$(git -C "$REPO" rev-parse origin/dev)"
    migrate
    [ "$status" -eq 0 ]
    [ "$(git -C "$REPO" rev-parse origin/dev)" = "$before" ]
    refute_trace 'repo view --json defaultBranchRef'
}

@test "ensure_dev: a local-only dev is published rather than re-created" {
    make_repo
    write_bespoke_justfile
    commit_all justfile
    git -C "$REPO" branch dev main
    migrate
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'Published the existing local branch dev'
    [ "$(git -C "$ORIGIN" rev-parse dev)" = "$(git -C "$REPO" rev-parse main)" ]
}

@test "ensure_dev: no dev anywhere creates one from the default branch" {
    make_repo
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'Created integration branch dev from origin/main'
    [ "$(git -C "$ORIGIN" rev-parse dev)" = "$(git -C "$ORIGIN" rev-parse main)" ]
}

@test "ensure_dev: refuses to publish a local dev that is behind the default branch" {
    make_repo
    write_bespoke_justfile
    commit_all justfile
    # dev branches off the current tip, then main moves ahead and is published.
    git -C "$REPO" branch dev main
    echo 'later' >>"$REPO/README.md"
    commit_all 'advance main'
    git -C "$REPO" push -q origin main
    migrate
    [ "$status" -ne 0 ]
    echo "$output" | grep -q 'Local dev is 1 commits behind origin/main'
    ! git -C "$ORIGIN" show-ref --verify --quiet refs/heads/dev
}

# ── init idempotency ──────────────────────────────────────────────────────

@test "init: creates the workflow file set" {
    make_repo
    run "$WORKFLOW" init --dir "$REPO"
    [ "$status" -eq 0 ]
    for f in CLAUDE.md .agent-workflow/AGENT_WORKFLOW.md .github/pull_request_template.md \
        .github/ISSUE_TEMPLATE/agent-task.md .github/workflows/agent-fast.yml \
        .github/workflows/agent-deep.yml; do
        [ -f "$REPO/$f" ] || {
            echo "init did not create $f" >&2
            return 1
        }
    done
}

@test "init: no longer writes the unconsumed .agent-workflow/ci.yml manifest" {
    make_repo
    run "$WORKFLOW" init --dir "$REPO"
    [ "$status" -eq 0 ]
    [ ! -e "$REPO/.agent-workflow/ci.yml" ]
}

@test "init: preserves an existing CLAUDE.md and appends the policy link exactly once" {
    make_repo
    echo '# My project' >"$REPO/CLAUDE.md"
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" init --dir "$REPO"
    [ "$status" -eq 0 ]
    head -1 "$REPO/CLAUDE.md" | grep -q '^# My project$'
    [ "$(grep -c '^# Agent workflow policy$' "$REPO/CLAUDE.md")" -eq 1 ]
}

@test "init: never overwrites an existing justfile or workflow file" {
    make_repo
    write_bespoke_justfile
    mkdir -p "$REPO/.github/workflows"
    echo 'name: mine' >"$REPO/.github/workflows/agent-fast.yml"
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" init --dir "$REPO"
    [ "$status" -eq 0 ]
    grep -q '^gauntlet:$' "$REPO/justfile"
    [ "$(cat "$REPO/.github/workflows/agent-fast.yml")" = 'name: mine' ]
}

@test "init: repeated runs leave the tree byte-identical" {
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    local first
    first="$(cd "$REPO" && find . -path ./.git -prune -o -type f -print | sort | xargs shasum)"
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    local second
    second="$(cd "$REPO" && find . -path ./.git -prune -o -type f -print | sort | xargs shasum)"
    [ "$first" = "$second" ]
}

# ── check: the contract is ci-fast and ci-deep, nothing else ──────────────

@test "check: green on a bespoke justfile that has only the two aggregates" {
    make_repo
    write_bespoke_justfile
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" check --dir "$REPO"
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'ok recipe ci-fast'
    echo "$output" | grep -q 'ok recipe ci-deep'
}

@test "check: does not demand the old seven-recipe vocabulary" {
    make_repo
    write_bespoke_justfile
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" check --dir "$REPO"
    [ "$status" -eq 0 ]
    for stale in fmt-check typecheck test-unit test-integration test-e2e build lint; do
        ! echo "$output" | grep -q "missing recipe $stale" || {
            echo "check still requires $stale" >&2
            return 1
        }
    done
}

@test "check: a missing recipe fails and prints a suggested body" {
    make_repo
    cat >"$REPO/justfile" <<'EOF'
polish:
    @true

ci-fast: polish
EOF
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" check --dir "$REPO"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q 'missing recipe ci-deep'
    echo "$output" | grep -q 'ci-deep: ci-fast'
}

@test "check: a justfile with neither aggregate suggests both bodies" {
    make_repo
    printf 'polish:\n    @true\n' >"$REPO/justfile"
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run "$WORKFLOW" check --dir "$REPO"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q 'ci-fast: fmt-check lint test'
    echo "$output" | grep -q 'ci-deep: ci-fast'
}

@test "check: a missing required file fails" {
    make_repo
    write_bespoke_justfile
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    rm "$REPO/.github/workflows/agent-deep.yml"
    run "$WORKFLOW" check --dir "$REPO"
    [ "$status" -eq 1 ]
    echo "$output" | grep -q 'missing file .github/workflows/agent-deep.yml'
}

# ── the migration bootstraps CI end to end: commit, PR, auto-merge ────────
# This is the ONE sanctioned rule exception (a human's one-time setup), kept
# safe by a local `just ci-fast` gate before any push and GitHub-native
# auto-merge behind the required checks.

@test "migration: commits CI SETUP on a branch and pushes it to origin" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    git -C "$ORIGIN" show-ref --verify --quiet "refs/heads/$CI_SETUP_BRANCH_NAME"
    [ "$(git -C "$ORIGIN" log -1 --format=%s "$CI_SETUP_BRANCH_NAME")" = 'ci: set up agent workflow (CI SETUP)' ]
}

@test "migration: opens a PR into dev and arms squash auto-merge" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    assert_trace 'pr create --base dev'
    assert_trace 'pr merge'
    assert_trace '--auto'
    assert_trace '--squash'
}

@test "migration: appends the missing aggregates without touching existing recipes" {
    make_repo
    publish_dev
    write_convention_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    local jf
    jf="$(git -C "$REPO" show "$CI_SETUP_BRANCH_NAME:justfile")"
    grep -q '^ci-fast: fmt-check lint test$' <<<"$jf"
    grep -q '^ci-deep: ci-fast$' <<<"$jf"
    # nothing the project already had was removed or rewritten
    grep -q '^fmt-check:$' <<<"$jf"
    grep -q '^build:$' <<<"$jf"
}

@test "migration: never pushes when the local just ci-fast gate fails" {
    make_repo
    publish_dev
    # Only `polish` exists, so the appended `ci-fast: fmt-check lint test`
    # references recipes that do not exist and `just ci-fast` fails.
    printf 'polish:\n    @true\n' >"$REPO/justfile"
    commit_all justfile
    migrate
    [ "$status" -ne 0 ]
    refute_trace 'pr create'
    refute_trace 'pr merge'
    ! git -C "$ORIGIN" show-ref --verify --quiet "refs/heads/$CI_SETUP_BRANCH_NAME"
}

@test "migration: is idempotent -- a second run adds no duplicate recipes" {
    make_repo
    publish_dev
    write_convention_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    migrate
    [ "$status" -eq 0 ]
    local jf
    jf="$(git -C "$REPO" show "$CI_SETUP_BRANCH_NAME:justfile")"
    [ "$(grep -c '^ci-fast' <<<"$jf")" -eq 1 ]
    [ "$(grep -c '^ci-deep' <<<"$jf")" -eq 1 ]
}

@test "migration: short-circuits to protection-only when dev already carries CI" {
    make_repo
    # Seed dev with the workflow files and both aggregates already present, as if
    # a prior migration had merged.
    write_bespoke_justfile
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    git -C "$REPO" add -A
    git -C "$REPO" commit -qm 'pre-existing CI'
    git -C "$REPO" branch dev
    git -C "$REPO" push -q -u origin dev
    migrate
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'already set up on dev'
    # No branch, no PR -- just protection re-applied.
    refute_trace 'pr create'
    ! git -C "$ORIGIN" show-ref --verify --quiet "refs/heads/$CI_SETUP_BRANCH_NAME"
}

# ── the vendored workflows are placeholder-free and well-formed ───────────

@test "workflows: installed files contain no unrendered placeholders" {
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    ! grep -rq '__[A-Z_]*__' "$REPO/.github/workflows" || {
        grep -rn '__[A-Z_]*__' "$REPO/.github/workflows" >&2
        return 1
    }
}

@test "workflows: the secret scanner is the unlicensed CLI, pinned by checksum" {
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    local fast="$REPO/.github/workflows/agent-fast.yml"
    # gitleaks-action hard-fails on org repos without a GITLEAKS_LICENSE. The
    # CLI it wraps is MIT and needs no key, so neither the action nor the secret
    # may come back -- either one reintroduces a signup and a red check.
    ! grep -q 'gitleaks-action' "$fast"
    ! grep -q 'GITLEAKS_LICENSE' "$fast"
    grep -q 'gitleaks git' "$fast"
    # A download pinned to a version but not a checksum is an unauthenticated
    # binary running in the job whose whole purpose is finding leaked secrets.
    # Require a literal 64-hex digest -- a placeholder or a stale env ref fails.
    grep -Eq '^\s+SHA256: [0-9a-f]{64}$' "$fast"
    grep -q 'sha256sum -c' "$fast"
}

@test "workflows: installed files reference no shared workflow repository" {
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    ! grep -rq 'agent-workflow/.github/workflows' "$REPO/.github/workflows"
    ! grep -rq 'workflow_call' "$REPO/.github/workflows"
}

@test "workflows: installed files parse as YAML" {
    command -v yq >/dev/null || skip 'yq is not installed'
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run yq -e '.jobs' "$REPO/.github/workflows/agent-fast.yml"
    [ "$status" -eq 0 ]
    run yq -e '.jobs' "$REPO/.github/workflows/agent-deep.yml"
    [ "$status" -eq 0 ]
}

@test "workflows: every required status check has a job that can report it" {
    command -v yq >/dev/null || skip 'yq is not installed'
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    # The invariant is SUBSET, not equality: every context gh-setup marks
    # required must be backed by a real job name, or it becomes a required check
    # that never reports and blocks every PR forever. The reverse is allowed on
    # purpose -- "Project checks" is an advisory job that runs without being
    # required, which is the whole point of the lean posture.
    local job_names context_names missing
    job_names="$( {
        yq -r '.jobs[].name' "$REPO/.github/workflows/agent-fast.yml"
        yq -r '.jobs[].name' "$REPO/.github/workflows/agent-deep.yml"
    } | sort -u)"
    context_names="$(grep -o '"contexts":\[[^]]*\]' "$WORKFLOW" |
        grep -o '"[A-Z][^"]*"' | tr -d '"' | sort -u)"
    [ -n "$context_names" ]
    # Any required context with no matching job is a fatal misconfiguration.
    missing="$(comm -23 <(printf '%s\n' "$context_names") <(printf '%s\n' "$job_names"))"
    [ -z "$missing" ] || {
        printf 'required context with no job to report it: %s\n' "$missing" >&2
        return 1
    }
    # And the lean posture specifically: Project checks RUNS but is NOT required.
    grep -q 'Project checks' <<<"$job_names"
    ! grep -q 'Project checks' <<<"$context_names"
}

@test "workflows: fast runs ci-fast on PRs into dev, deep runs ci-deep" {
    command -v yq >/dev/null || skip 'yq is not installed'
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    run yq -r '.on.pull_request.branches[0]' "$REPO/.github/workflows/agent-fast.yml"
    [ "$output" = dev ]
    grep -q 'just ci-fast' "$REPO/.github/workflows/agent-fast.yml"
    run yq -r '.on.push.branches[0]' "$REPO/.github/workflows/agent-deep.yml"
    [ "$output" = dev ]
    run yq -r '.on.pull_request.branches[0]' "$REPO/.github/workflows/agent-deep.yml"
    [ "$output" = main ]
    grep -q 'just ci-deep' "$REPO/.github/workflows/agent-deep.yml"
}

# ── starter justfiles: real commands, no pass-while-doing-nothing recipes ─

@test "starters: every language starter provides both aggregates" {
    for language in rust python javascript; do
        local starter="$KIT/templates/justfile.$language"
        [ -f "$starter" ] || {
            echo "missing starter $starter" >&2
            return 1
        }
        mkdir -p "$BATS_TEST_TMPDIR/$language"
        cp "$starter" "$BATS_TEST_TMPDIR/$language/justfile"
        local recipes
        recipes="$(cd "$BATS_TEST_TMPDIR/$language" && just --list --unsorted | awk '{print $1}')"
        echo "$recipes" | grep -Fxq ci-fast || {
            echo "$language starter has no ci-fast" >&2
            return 1
        }
        echo "$recipes" | grep -Fxq ci-deep || {
            echo "$language starter has no ci-deep" >&2
            return 1
        }
    done
}

@test "starters: no recipe passes while doing nothing" {
    ! grep -q 'not applicable' "$KIT"/templates/justfile.*
}

@test "starters: the failing-stub justfile is gone" {
    [ ! -e "$KIT/templates/justfile.stub" ]
}

# ── removed surface stays removed ─────────────────────────────────────────

@test "removed: the publish command and the shared workflow repository are gone" {
    run "$WORKFLOW" publish
    [ "$status" -ne 0 ]
    echo "$output" | grep -q 'unknown command: publish'
    [ ! -d "$KIT/repository" ]
}

@test "removed: the codex flags and template are gone" {
    make_repo
    run "$WORKFLOW" init --dir "$REPO" --with-codex
    [ "$status" -ne 0 ]
    run "$WORKFLOW" check --dir "$REPO" --require-codex
    [ "$status" -ne 0 ]
    [ ! -e "$KIT/templates/AGENTS.md" ]
}

@test "removed: the ci manifest template is gone" {
    [ ! -e "$KIT/templates/ci-manifest.yml" ]
}

# ── script mode: non-interactive invocation for agents ────────────────────
# Any argument switches setup-project out of the TUI. The interactive prompts
# (gum input / gum choose) must NEVER fire in this mode; flags carry the answers.

@test "script mode: migrate --dir completes the migration with no interactive prompt" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    run "$SETUP" migrate --dir "$REPO"
    [ "$status" -eq 0 ]
    # The migration actually ran: branch pushed, PR opened, auto-merge armed.
    git -C "$ORIGIN" show-ref --verify --quiet "refs/heads/$CI_SETUP_BRANCH_NAME"
    assert_trace 'pr create --base dev'
    # ...without ever prompting.
    refute_gum input
    refute_gum choose
}

@test "script mode: migrate defaults --dir to the current directory" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    run bash -c "cd '$REPO' && '$SETUP' migrate"
    [ "$status" -eq 0 ]
    git -C "$ORIGIN" show-ref --verify --quiet "refs/heads/$CI_SETUP_BRANCH_NAME"
    refute_gum input
    refute_gum choose
}

@test "script mode: new without --name fails loudly naming --name" {
    run "$SETUP" new --language rust
    [ "$status" -ne 0 ]
    echo "$output" | grep -q -- '--name'
    refute_gum input
    refute_gum choose
}

@test "script mode: new without --language fails loudly naming --language" {
    run "$SETUP" new --name my-project
    [ "$status" -ne 0 ]
    echo "$output" | grep -q -- '--language'
    refute_gum input
    refute_gum choose
}

@test "script mode: new with an invalid --language fails loudly" {
    run "$SETUP" new --name my-project --language cobol
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi 'language'
    refute_gum input
    refute_gum choose
}

@test "script mode: --help prints usage and exits 0" {
    run "$SETUP" --help
    [ "$status" -eq 0 ]
    echo "$output" | grep -qi 'usage'
    echo "$output" | grep -q 'setup-project migrate'
    refute_gum input
    refute_gum choose
}

@test "script mode: an unknown subcommand fails loudly" {
    run "$SETUP" bogus
    [ "$status" -ne 0 ]
    echo "$output" | grep -qi 'unknown'
    refute_gum input
    refute_gum choose
}

@test "script mode: an unknown flag fails loudly" {
    run "$SETUP" migrate --wat
    [ "$status" -ne 0 ]
    refute_gum input
    refute_gum choose
}

# The zero-arg path still drives the interactive TUI (gum choose + gum input).
@test "script mode: zero args still drives the interactive prompt" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    grep -qE '^choose( |$)' "$GUM_TRACE"
    grep -qE '^input( |$)' "$GUM_TRACE"
}
