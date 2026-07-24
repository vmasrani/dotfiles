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
    export GUM_ANSWERS="${BATS_TEST_TMPDIR}/gum-answers"
    export GUM_CURSOR="${BATS_TEST_TMPDIR}/gum-cursor"
    : >"$GH_TRACE"
    : >"$GUM_ANSWERS"
    echo 0 >"$GUM_CURSOR"
    write_fake_gh
    write_fake_gum
    export PATH="$BIN:$PATH"

    ORIGIN="${BATS_TEST_TMPDIR}/origin.git"
    REPO="${BATS_TEST_TMPDIR}/project"

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
# echoes its non-flag arguments so report text stays visible in $output.
write_fake_gum() {
    cat >"$BIN/gum" <<'EOF'
#!/usr/bin/env bash
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

# ── the migration installs and reports; it never commits, pushes, or PRs ──

@test "existing_project: opens no pull request" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    refute_trace 'pr create'
}

@test "existing_project: commits nothing and pushes nothing" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    local head_before origin_before
    head_before="$(git -C "$REPO" rev-parse HEAD)"
    origin_before="$(git -C "$ORIGIN" for-each-ref --format='%(refname) %(objectname)' | sort)"
    migrate
    [ "$status" -eq 0 ]
    [ "$(git -C "$REPO" rev-parse HEAD)" = "$head_before" ]
    [ "$(git -C "$ORIGIN" for-each-ref --format='%(refname) %(objectname)' | sort)" = "$origin_before" ]
    # The installed files are present but still uncommitted, which is the proof
    # that install-and-report ran and nothing else did.
    git -C "$REPO" status --porcelain | grep -q '^?? .github/'
}

@test "existing_project: creates no chore/add-agent-workflow branch" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    ! git -C "$REPO" show-ref --verify --quiet refs/heads/chore/add-agent-workflow
    ! git -C "$ORIGIN" show-ref --verify --quiet refs/heads/chore/add-agent-workflow
}

@test "existing_project: is safe to run twice" {
    make_repo
    publish_dev
    write_bespoke_justfile
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    migrate
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'The CI contract is already satisfied'
}

@test "existing_project: a repo without the aggregates stops at an actionable report" {
    make_repo
    publish_dev
    printf 'polish:\n    @true\n' >"$REPO/justfile"
    commit_all justfile
    migrate
    [ "$status" -eq 0 ]
    echo "$output" | grep -q 'Nothing has been committed or pushed'
    echo "$output" | grep -q 'missing recipe ci-fast'
    echo "$output" | grep -q 'missing recipe ci-deep'
    refute_trace 'pr create'
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

@test "workflows: job names match the required status checks gh-setup applies" {
    command -v yq >/dev/null || skip 'yq is not installed'
    make_repo
    "$WORKFLOW" init --dir "$REPO" >/dev/null
    # Compare against the contexts gh-setup actually PUTs, not a copy of them:
    # a renamed job that nobody mirrored into the protection payload would leave
    # a required check that can never report.
    local job_names context_names
    job_names="$( {
        yq -r '.jobs[].name' "$REPO/.github/workflows/agent-fast.yml"
        yq -r '.jobs[].name' "$REPO/.github/workflows/agent-deep.yml"
    } | sort -u)"
    context_names="$(grep -o '"contexts":\[[^]]*\]' "$WORKFLOW" |
        grep -o '"[A-Z][^"]*"' | tr -d '"' | sort -u)"
    [ -n "$context_names" ]
    [ "$job_names" = "$context_names" ]
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
