#!/usr/bin/env bats
# Behaviour tests for `agent-ssh`, the tool that SSHes into a fresh agent-image
# job and opens a plain terminal.
#
# HERMETIC BY CONSTRUCTION
#   The tests exercise factored-out helpers through hidden dispatch hooks, so
#   nothing here touches the network or GitHub. Fake `gh` programs are placed
#   first on PATH and return only the exact API state under test.
#
#   ZDOTDIR points at an empty dir so the tool's zsh skips the user's ~/.zshenv
#   (which, among other things, does a macOS keychain lookup on every start and
#   prepends dirs to PATH) — that keeps the fake `gh` first on PATH and the run
#   fast and deterministic. NO_GUM=1 forces plain-text output.
#
#   Run:  bats tools/tests/agent-ssh.bats

setup() {
    AGENT_SSH="${BATS_TEST_DIRNAME}/../agent-ssh"
    [ -x "$AGENT_SSH" ] || {
        echo "agent-ssh not executable at $AGENT_SSH" >&2
        return 1
    }

    BIN="${BATS_TEST_TMPDIR}/bin"
    mkdir -p "$BIN"
    export PATH="$BIN:$PATH"

    # Empty startup dir → tool's zsh reads no user rc files.
    export ZDOTDIR="${BATS_TEST_TMPDIR}/zdot"
    mkdir -p "$ZDOTDIR"

    export NO_GUM=1
}

# A fake `gh` whose `api .../contents/...?ref=<ref>` succeeds only when <ref>
# equals $GH_OK_REF. Everything else exits non-zero. Records nothing else.
write_fake_gh() {
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
if [[ "$*" == *"ref=${GH_OK_REF:-__none__}"* ]]; then
    exit 0
fi
exit 1
EOF
    chmod +x "$BIN/gh"
}

# A fake `gh` that satisfies preflight and returns a chosen response for the
# packages-versions endpoint. $GH_PKG_MODE picks 403 | 404 | ok | empty so the
# status command's case discrimination can be exercised without the network.
write_fake_gh_pkgs() {
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$args" in
    "auth status"*) exit 0 ;;
    *packages/container*versions*)
        case "${GH_PKG_MODE:-empty}" in
            403) echo '{"message":"You need at least read:packages scope.","status":"403"}'
                 echo "gh: You need at least read:packages scope to get a package's versions. (HTTP 403)" >&2
                 exit 1 ;;
            404) echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
            ok)  echo '[{"metadata":{"container":{"tags":["latest","15116e78"]}},"created_at":"2026-09-18T06:34:00Z"}]'; exit 0 ;;
            *)   echo '[]'; exit 0 ;;
        esac ;;
    "api repos/"*) echo '{}'; exit 0 ;;
    "run list"*)   echo '[]'; exit 0 ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$BIN/gh"
}

# A fake `gh` for the in-progress check-annotation protocol. It models a job
# appearing after GH_READY_AFTER polls, then returns the annotation selected by
# the real command's --jq expression. GH_ANNOTATION_MODE picks success | missing
# | malformed | completed | jobs-error | annotations-error.
write_fake_gh_annotations() {
    export GH_ANNOTATION_STATE="${BATS_TEST_TMPDIR}/annotation-state"
    : >"$GH_ANNOTATION_STATE"
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
args="$*"
case "$args" in
    *"/actions/runs/"*"/jobs"*)
        if [[ "${GH_ANNOTATION_MODE:-success}" == "jobs-error" ]]; then
            echo "gh: API unavailable (HTTP 503)" >&2
            exit 1
        fi
        count="$(wc -l <"$GH_ANNOTATION_STATE" | tr -d ' ')"
        printf 'poll\n' >>"$GH_ANNOTATION_STATE"
        if (( count < ${GH_READY_AFTER:-0} )); then
            exit 0
        fi
        echo "https://api.github.com/repos/test/repo/check-runs/777"
        ;;
    *"check-runs/777/annotations"*)
        case "${GH_ANNOTATION_MODE:-success}" in
            success) echo "ssh Ready_9@uptermd.upterm.dev" ;;
            missing|completed) ;;
            malformed) echo "connect at https://upterm.dev/not-an-ssh-command" ;;
            annotations-error)
                echo "gh: annotation API forbidden (HTTP 403)" >&2
                exit 1
                ;;
        esac
        ;;
    *"/actions/runs/"*)
        if [[ "${GH_ANNOTATION_MODE:-success}" == "completed" ]]; then
            printf 'completed\tfailure\n'
        else
            printf 'in_progress\t\n'
        fi
        ;;
    *) echo "unexpected gh call: $args" >&2; exit 99 ;;
esac
EOF
    chmod +x "$BIN/gh"

    cat >"$BIN/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$BIN/sleep"
}

# ── help / usage ──────────────────────────────────────────────────────────────

@test "help: prints usage and describes the plain terminal" {
    run "$AGENT_SSH" help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
    [[ "$output" == *"plain terminal"* ]]
    [[ "$output" != *"tmux attach"* ]]
}

@test "help: unknown command fails loud" {
    run "$AGENT_SSH" frobnicate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command"* ]]
}

# ── ssh-address extraction ────────────────────────────────────────────────────

@test "extract: pulls the ssh address out of a log line" {
    run "$AGENT_SSH" __extract-ssh "::notice::SSH: ssh aB3xZ9qPkL7@uptermd.upterm.dev"
    [ "$status" -eq 0 ]
    [ "$output" = "ssh aB3xZ9qPkL7@uptermd.upterm.dev" ]
}

@test "extract: picks the SSH command, not an Upterm web URL, and tolerates _/- tokens" {
    local log="Service: https://upterm.dev
SSH: ssh To_ken-9@uptermd.upterm.dev"
    run "$AGENT_SSH" __extract-ssh "$log"
    [ "$status" -eq 0 ]
    [ "$output" = "ssh To_ken-9@uptermd.upterm.dev" ]
}

@test "extract: reads from stdin when given no argument" {
    run bash -c 'printf "noise\nSSH: ssh Zz9@uptermd.upterm.dev\n" | "'"$AGENT_SSH"'" __extract-ssh'
    [ "$status" -eq 0 ]
    [ "$output" = "ssh Zz9@uptermd.upterm.dev" ]
}

@test "extract: no address present returns non-zero and prints nothing" {
    run "$AGENT_SSH" __extract-ssh "nothing to see here"
    [ "$status" -eq 1 ]
    [ -z "$output" ]
}

# ── live check-annotation address protocol (stubbed gh) ──────────────────────

@test "annotation: returns a valid SSH command from the titled check annotation" {
    write_fake_gh_annotations
    export GH_ANNOTATION_MODE="success"
    run "$AGENT_SSH" __fetch-annotation 12345
    [ "$status" -eq 0 ]
    [ "$output" = "ssh Ready_9@uptermd.upterm.dev" ]
}

@test "annotation: waits while the job is absent, then returns its address" {
    write_fake_gh_annotations
    export GH_ANNOTATION_MODE="success"
    export GH_READY_AFTER=2
    run "$AGENT_SSH" __wait-annotation 12345 5 1
    [ "$status" -eq 0 ]
    [ "$output" = "ssh Ready_9@uptermd.upterm.dev" ]
    [ "$(wc -l <"$GH_ANNOTATION_STATE" | tr -d ' ')" -eq 3 ]
}

@test "annotation: times out when the address annotation stays missing" {
    write_fake_gh_annotations
    export GH_ANNOTATION_MODE="missing"
    run "$AGENT_SSH" __wait-annotation 12345 2 1
    [ "$status" -eq 1 ]
    [ -z "$output" ]
}

@test "annotation: stops immediately when the run completes without an address" {
    write_fake_gh_annotations
    export GH_ANNOTATION_MODE="completed"
    run "$AGENT_SSH" __wait-annotation 12345 8 1
    [ "$status" -eq 3 ]
    [[ "$output" == *"completed"* ]]
    [[ "$output" == *"failure"* ]]
    [ "$(wc -l <"$GH_ANNOTATION_STATE" | tr -d ' ')" -eq 1 ]
}

@test "annotation: rejects malformed and missing annotation messages" {
    write_fake_gh_annotations
    for mode in malformed missing; do
        export GH_ANNOTATION_MODE="$mode"
        run "$AGENT_SSH" __fetch-annotation 12345
        [ "$status" -eq 1 ]
        [ -z "$output" ]
    done
}

@test "annotation: fails loud when either GitHub API request errors" {
    write_fake_gh_annotations
    for mode in jobs-error annotations-error; do
        export GH_ANNOTATION_MODE="$mode"
        run "$AGENT_SSH" __fetch-annotation 12345
        [ "$status" -eq 2 ]
        [[ "$output" == *"GitHub API failed"* ]]
        [[ "$output" == *"HTTP"* ]]
    done
}

# ── minutes validation ────────────────────────────────────────────────────────

@test "minutes: accepts 5, 15 and 360" {
    for m in 5 15 360; do
        run "$AGENT_SSH" __valid-minutes "$m"
        [ "$status" -eq 0 ] || {
            echo "expected $m to be valid" >&2
            return 1
        }
    done
}

@test "minutes: rejects out-of-range, non-integer and empty" {
    for m in 4 361 0 -5 abc 20.5 ""; do
        run "$AGENT_SSH" __valid-minutes "$m"
        [ "$status" -eq 1 ] || {
            echo "expected '$m' to be rejected" >&2
            return 1
        }
    done
}

# ── workflow-ref resolution (stubbed gh) ──────────────────────────────────────

@test "resolve: returns the first candidate ref that exists" {
    write_fake_gh
    export GH_OK_REF="agent-image-full-shell"
    run "$AGENT_SSH" __resolve-ref some/repo path/to/wf.yml dev agent-image-full-shell agent-image-ssh-workflow
    [ "$status" -eq 0 ]
    [ "$output" = "agent-image-full-shell" ]
}

@test "resolve: prefers the earliest candidate when several would match" {
    write_fake_gh
    export GH_OK_REF="dev"   # dev is tried first, so it wins
    run "$AGENT_SSH" __resolve-ref some/repo path/to/wf.yml dev agent-image-full-shell
    [ "$status" -eq 0 ]
    [ "$output" = "dev" ]
}

@test "resolve: returns non-zero when no candidate has the workflow" {
    write_fake_gh
    export GH_OK_REF="__none__"
    run "$AGENT_SSH" __resolve-ref some/repo path/to/wf.yml dev agent-image-full-shell agent-image-ssh-workflow
    [ "$status" -eq 1 ]
    [ -z "$output" ]
}

# ── status: 403 / 404 / 200 discrimination ────────────────────────────────────

@test "status: a packages 403 names the read:packages fix and fails loud" {
    write_fake_gh_pkgs
    export GH_PKG_MODE="403"
    run "$AGENT_SSH" status
    [ "$status" -eq 1 ]
    [[ "$output" == *"read:packages"* ]]
    [[ "$output" == *"gh auth refresh"* ]]
}

@test "status: a packages 404 tells you to build an image" {
    write_fake_gh_pkgs
    export GH_PKG_MODE="404"
    run "$AGENT_SSH" status
    [ "$status" -eq 1 ]
    [[ "$output" == *"No image is published yet"* ]]
    [[ "$output" == *"agent-ssh build"* ]]
}

@test "status: a 200 with versions shows the published tags" {
    write_fake_gh_pkgs
    export GH_PKG_MODE="ok"
    run "$AGENT_SSH" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"latest"* ]]
    [[ "$output" == *"15116e78"* ]]
}

# ── agent mode: dispatch an agent on an issue, attach to it ───────────────────
#
# A recording fake `gh`. Every call is appended to $GH_LOG; state is chosen by:
#   GH_RUNS_JSON       file with the `gh run list` JSON (default: no runs)
#   GH_SECRET_MODE     ok | missing | error
#   GH_ISSUE_STATE     state returned for every issue (default OPEN)
#   GH_CLOSED_ISSUES   space-separated issue numbers that report CLOSED
#   GH_MISSING_ISSUES  space-separated issue numbers that do not exist
# The run JSON carries createdAt in year 2999 so every run is "newer than since".
write_fake_gh_agent() {
    export GH_LOG="${BATS_TEST_TMPDIR}/gh.log"
    export GH_RUNS_JSON="${BATS_TEST_TMPDIR}/runs.json"
    export GH_DISPATCHED_JSON="${BATS_TEST_TMPDIR}/dispatched.json"
    : >"$GH_LOG"
    [ -f "$GH_RUNS_JSON" ] || echo '[]' >"$GH_RUNS_JSON"
    [ -f "$GH_DISPATCHED_JSON" ] || echo '[]' >"$GH_DISPATCHED_JSON"
    export AGENT_SSH_REPO="test/repo" AGENT_SSH_REF="dev"
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$GH_LOG"
case "$*" in
    "auth status"*) exit 0 ;;
    "api repos/test/repo") echo '{}'; exit 0 ;;
    "secret list"*)
        case "${GH_SECRET_MODE:-ok}" in
            error)   echo "gh: Resource not accessible (HTTP 403)" >&2; exit 1 ;;
            missing) echo "SOME_OTHER_SECRET"; exit 0 ;;
            *)       printf 'SOME_OTHER_SECRET\nCLAUDE_CODE_OAUTH_TOKEN\n'; exit 0 ;;
        esac ;;
    "issue view "*)
        n="$3"
        for m in ${GH_MISSING_ISSUES:-}; do
            [[ "$m" == "$n" ]] && { echo "gh: Could not resolve to an issue (HTTP 404)" >&2; exit 1; }
        done
        for c in ${GH_CLOSED_ISSUES:-}; do
            [[ "$c" == "$n" ]] && { echo CLOSED; exit 0; }
        done
        echo "${GH_ISSUE_STATE:-OPEN}"; exit 0 ;;
    "workflow run"*) exit 0 ;;
    "run cancel"*)   exit 0 ;;
    "run list"*)
        if grep -q '^workflow run' "$GH_LOG"; then jq -s add "$GH_RUNS_JSON" "$GH_DISPATCHED_JSON"; else cat "$GH_RUNS_JSON"; fi
        exit 0 ;;
    *"/actions/runs/"*"/jobs"*) echo "https://api.github.com/repos/test/repo/check-runs/777"; exit 0 ;;
    *"check-runs/777/annotations"*) echo "ssh Ready_9@uptermd.upterm.dev"; exit 0 ;;
    *"/actions/runs/"*) printf 'in_progress\t\n'; exit 0 ;;
    *) echo "unexpected gh call: $*" >&2; exit 99 ;;
esac
EOF
    chmod +x "$BIN/gh"

    cat >"$BIN/sleep" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
    chmod +x "$BIN/sleep"

    export SSH_LOG="${BATS_TEST_TMPDIR}/ssh.log"
    : >"$SSH_LOG"
    cat >"$BIN/ssh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$SSH_LOG"
EOF
    chmod +x "$BIN/ssh"
}

# Rows: "<id>:<issue>:<status>" -> agent runs, "<id>:box:<status>" -> plain box.
# write_runs = runs that already exist; write_dispatched = runs that only appear
# once the tool has dispatched (the fake gh checks its own log for `workflow run`).
write_runs() { write_run_rows "$GH_RUNS_JSON" "$@"; }
write_dispatched() { write_run_rows "$GH_DISPATCHED_JSON" "$@"; }
write_run_rows() {
    local target="$1"; shift
    local row id issue status title out=()
    for row in "$@"; do
        IFS=: read -r id issue status <<<"$row"
        if [[ "$issue" == box ]]; then title="ssh box"; else title="agent issue #${issue}"; fi
        out+=("{\"databaseId\":${id},\"displayTitle\":\"${title}\",\"status\":\"${status}\",\"createdAt\":\"2999-01-01T00:00:00Z\"}")
    done
    local IFS=,
    echo "[${out[*]}]" >"$target"
}

# Run the command with stdin/stdout on a pty, so the tool's tty check passes.
with_tty() {
    if [[ "$(uname)" == Darwin ]]; then
        script -q /dev/null "$@" </dev/null
    else
        script -qec "$(printf '%q ' "$@")" /dev/null  </dev/null
    fi
}

@test "help: documents agent dispatch, attach and the one-time secret setup" {
    run "$AGENT_SSH" help
    [ "$status" -eq 0 ]
    [[ "$output" == *"agent-ssh 12"* ]]
    [[ "$output" == *"attach"* ]]
    [[ "$output" == *"CLAUDE_CODE_OAUTH_TOKEN"* ]]
}

@test "issue number: only positive integers without leading zeros" {
    run "$AGENT_SSH" __is-issue 12;  [ "$status" -eq 0 ]
    run "$AGENT_SSH" __is-issue 7;   [ "$status" -eq 0 ]
    for bad in 0 012 abc "" -3 1.5 "12 13"; do
        run "$AGENT_SSH" __is-issue "$bad"
        [ "$status" -ne 0 ] || { echo "accepted '$bad'" >&2; return 1; }
    done
}

@test "agent title: exact wording the workflow's run-name must match" {
    run "$AGENT_SSH" __agent-title 12
    [ "$output" = "agent issue #12" ]
}

@test "args: flags are accepted in any position next to issue numbers" {
    run "$AGENT_SSH" __parse-args 12 -m 30 --model claude-sonnet-5 --no-attach 13
    [ "$status" -eq 0 ]
    [ "$output" = "minutes=30 model=claude-sonnet-5 no_attach=1 positional=12,13" ]
    run "$AGENT_SSH" __parse-args --minutes 45 attach 12
    [ "$output" = "minutes=45 model= no_attach= positional=attach,12" ]
}

@test "args: a flag missing its value or an unknown flag fails loud" {
    run "$AGENT_SSH" __parse-args 12 -m
    [ "$status" -eq 1 ]
    [[ "$output" == *"needs a value"* ]]
    run "$AGENT_SSH" __parse-args 12 --frobnicate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown flag"* ]]
}

@test "find-run: matches the exact title, so #1 never returns the run for #12" {
    write_fake_gh_agent
    write_runs 111:12:in_progress 222:1:in_progress
    run "$AGENT_SSH" __find-run ssh-into-agent-image.yml 2000-01-01T00:00:00Z "agent issue #1"
    [ "$status" -eq 0 ]
    [ "$output" = "222" ]
    run "$AGENT_SSH" __find-run ssh-into-agent-image.yml 2000-01-01T00:00:00Z "agent issue #12"
    [ "$output" = "111" ]
}

@test "find-run: without a title the newest run after <since> wins; older runs are ignored" {
    write_fake_gh_agent
    write_runs 111:box:in_progress
    run "$AGENT_SSH" __find-run ssh-into-agent-image.yml 2000-01-01T00:00:00Z
    [ "$output" = "111" ]
    run "$AGENT_SSH" __find-run ssh-into-agent-image.yml 2999-06-01T00:00:00Z
    [ "$status" -eq 1 ]
}

@test "agent: one issue with --no-attach dispatches the workflow with the frozen inputs" {
    write_fake_gh_agent
    write_dispatched 555:12:queued
    run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 0 ]
    grep -qx "workflow run ssh-into-agent-image.yml --repo test/repo --ref dev -f issue=12 -f minutes=120 -f model=claude-opus-4-8 -f image_tag=latest" "$GH_LOG"
    [[ "$output" == *"agent-ssh attach 12"* ]]
    [ ! -s "$SSH_LOG" ]
}

@test "agent: --minutes and --model override the defaults" {
    write_fake_gh_agent
    write_dispatched 555:12:queued
    run "$AGENT_SSH" 12 --no-attach -m 30 --model claude-sonnet-5
    [ "$status" -eq 0 ]
    grep -q -- "-f issue=12 -f minutes=30 -f model=claude-sonnet-5 " "$GH_LOG"
}

@test "agent: several issues each get their own dispatch, and none is attached" {
    write_fake_gh_agent
    write_dispatched 555:12:queued 556:13:queued
    run "$AGENT_SSH" 12 13
    [ "$status" -eq 0 ]
    [ "$(grep -c '^workflow run' "$GH_LOG")" -eq 2 ]
    grep -q -- "-f issue=12 " "$GH_LOG"
    grep -q -- "-f issue=13 " "$GH_LOG"
    [[ "$output" == *"agent-ssh attach 12"* ]]
    [[ "$output" == *"agent-ssh attach 13"* ]]
    [ ! -s "$SSH_LOG" ]
}

@test "agent: a single issue attaches straight into the session over ssh" {
    write_fake_gh_agent
    write_dispatched 555:12:in_progress
    run with_tty "$AGENT_SSH" 12
    [ "$status" -eq 0 ]
    grep -q -- "-f issue=12 " "$GH_LOG"
    [ "$(cat "$SSH_LOG")" = "-o StrictHostKeyChecking=accept-new Ready_9@uptermd.upterm.dev" ]
}

@test "agent: attaching without a terminal fails before anything is dispatched" {
    write_fake_gh_agent
    run "$AGENT_SSH" 12
    [ "$status" -eq 1 ]
    [[ "$output" == *"interactive terminal"* ]]
    [[ "$output" == *"--no-attach"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: a missing CLAUDE_CODE_OAUTH_TOKEN secret names the fix and dispatches nothing" {
    write_fake_gh_agent
    GH_SECRET_MODE=missing run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"claude setup-token"* ]]
    [[ "$output" == *"gh secret set CLAUDE_CODE_OAUTH_TOKEN --repo test/repo"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: an unreadable secrets API is reported as such, not as a missing secret" {
    write_fake_gh_agent
    GH_SECRET_MODE=error run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"Cannot read the secrets"* ]]
    [[ "$output" != *"claude setup-token"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: a closed or missing issue is refused" {
    write_fake_gh_agent
    GH_CLOSED_ISSUES="12" run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"Issue #12 is closed"* ]]
    GH_MISSING_ISSUES="12" run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"Cannot read issue #12"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: one bad issue in a batch stops the whole batch before any dispatch" {
    write_fake_gh_agent
    GH_CLOSED_ISSUES="13" run "$AGENT_SSH" 12 13 14
    [ "$status" -eq 1 ]
    [[ "$output" == *"Issue #13 is closed"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: a second agent on the same issue is refused and points at attach" {
    write_fake_gh_agent
    write_runs 555:12:in_progress
    run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"already running on issue #12"* ]]
    [[ "$output" == *"agent-ssh attach 12"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "agent: a queued run counts as running; a completed one does not" {
    write_fake_gh_agent
    write_runs 555:12:queued
    run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 1 ]
    ! grep -q '^workflow run' "$GH_LOG"
    write_runs 555:12:completed
    write_dispatched 556:12:queued
    run "$AGENT_SSH" 12 --no-attach
    [ "$status" -eq 0 ]
    grep -q '^workflow run' "$GH_LOG"
}

@test "agent: bad arguments fail loud (minutes range, duplicate issue, non-issue word)" {
    write_fake_gh_agent
    run "$AGENT_SSH" 12 --no-attach -m 4
    [ "$status" -eq 1 ]
    [[ "$output" == *"between 5 and 360"* ]]
    run "$AGENT_SSH" 12 12 --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"listed twice"* ]]
    run "$AGENT_SSH" 12 foo --no-attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"'foo' is not an issue number"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "attach: joins the running agent for the given issue" {
    write_fake_gh_agent
    write_runs 555:12:in_progress 556:13:in_progress
    run with_tty "$AGENT_SSH" attach 13
    [ "$status" -eq 0 ]
    grep -q "actions/runs/556/jobs" "$GH_LOG"
    [ "$(cat "$SSH_LOG")" = "-o StrictHostKeyChecking=accept-new Ready_9@uptermd.upterm.dev" ]
}

@test "attach: no agent for that issue says how to start one" {
    write_fake_gh_agent
    write_runs 555:12:in_progress
    run with_tty "$AGENT_SSH" attach 99
    [ "$status" -eq 1 ]
    [[ "$output" == *"No agent is running on issue #99"* ]]
    [[ "$output" == *"agent-ssh 99"* ]]
    [ ! -s "$SSH_LOG" ]
}

@test "attach: with no issue and no running agents fails loud" {
    write_fake_gh_agent
    write_runs 555:12:completed 556:box:in_progress
    run with_tty "$AGENT_SSH" attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"No agents are running"* ]]
}

@test "attach: with no issue and exactly one agent joins it; plain boxes are ignored" {
    write_fake_gh_agent
    write_runs 556:box:in_progress 555:12:in_progress
    run with_tty "$AGENT_SSH" attach
    [ "$status" -eq 0 ]
    grep -q "actions/runs/555/jobs" "$GH_LOG"
    [ -s "$SSH_LOG" ]
}

@test "attach: with several agents and no menu available it refuses instead of guessing" {
    write_fake_gh_agent
    write_runs 555:12:in_progress 556:13:in_progress
    run with_tty "$AGENT_SSH" attach
    [ "$status" -eq 1 ]
    [[ "$output" == *"attach <issue>"* ]]
    [ ! -s "$SSH_LOG" ]
}

@test "kill: with no issue and no menu available it cancels nothing" {
    write_fake_gh_agent
    cat >"$BIN/gh" <<'EOF2'
#!/usr/bin/env bash
echo "$*" >>"$GH_LOG"
case "$*" in
    "auth status"*|"api repos/test/repo") exit 0 ;;
    "run list"*) printf '7  agent issue #12  (2999-01-01T00:00:00Z)\n8  agent issue #13  (2999-01-01T00:00:00Z)\n' ;;
    *) exit 0 ;;
esac
EOF2
    chmod +x "$BIN/gh"
    run "$AGENT_SSH" kill
    [ "$status" -eq 1 ]
    [[ "$output" == *"kill <issue>"* ]]
    ! grep -q '^run cancel' "$GH_LOG"
}

@test "menu: with no terminal or gum the bare command prints usage instead of prompting" {
    run "$AGENT_SSH"
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
}

@test "attach: refuses without a terminal" {
    write_fake_gh_agent
    write_runs 555:12:in_progress
    run "$AGENT_SSH" attach 12
    [ "$status" -eq 1 ]
    [[ "$output" == *"interactive terminal"* ]]
    [ ! -s "$SSH_LOG" ]
}

@test "attach: a GitHub API failure is not reported as 'no agent running'" {
    write_fake_gh_agent
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
case "$*" in
    "auth status"*|"api repos/test/repo") exit 0 ;;
    "run list"*) echo "gh: API unavailable (HTTP 503)" >&2; exit 1 ;;
    *) exit 0 ;;
esac
EOF
    run with_tty "$AGENT_SSH" attach 12
    [ "$status" -eq 1 ]
    [[ "$output" == *"GitHub's API failed"* ]]
    [[ "$output" != *"No agent is running"* ]]
}

@test "kill: with an issue cancels exactly that agent's run" {
    write_fake_gh_agent
    write_runs 555:12:in_progress 556:13:in_progress
    run "$AGENT_SSH" kill 13
    [ "$status" -eq 0 ]
    grep -qx "run cancel 556 --repo test/repo" "$GH_LOG"
    ! grep -q "run cancel 555" "$GH_LOG"
}

@test "kill: an issue with no running agent fails loud and cancels nothing" {
    write_fake_gh_agent
    write_runs 555:12:completed
    run "$AGENT_SSH" kill 12
    [ "$status" -eq 1 ]
    [[ "$output" == *"No agent is running on issue #12"* ]]
    ! grep -q '^run cancel' "$GH_LOG"
}

@test "kill: a non-numeric target is refused" {
    write_fake_gh_agent
    run "$AGENT_SSH" kill twelve
    [ "$status" -eq 1 ]
    [[ "$output" == *"not an issue number"* ]]
}

@test "attach: a run that fails before publishing an address shows the job's own FAIL reason" {
    write_fake_gh_agent
    write_runs 555:12:in_progress
    cat >"$BIN/gh" <<'EOF2'
#!/usr/bin/env bash
case "$*" in
    "auth status"*|"api repos/test/repo") exit 0 ;;
    "run list"*) echo '[{"databaseId":555,"displayTitle":"agent issue #12","status":"in_progress","createdAt":"2999-01-01T00:00:00Z"}]' ;;
    *"/actions/runs/"*"/jobs"*) exit 0 ;;
    "run view 555 --repo test/repo --log-failed")
        printf 'ssh\tValidate\t2026-09-19T06:36:53.2Z \033[36;1m|| { echo "FAIL: script text, not output" >&2; }\033[0m\n'
        printf 'ssh\tValidate\t2026-09-19T06:36:53.2Z FAIL: no CLAUDE_CODE_OAUTH_TOKEN secret. Run: claude setup-token\n' ;;
    *"/actions/runs/"*) printf 'completed\tfailure\n' ;;
    *) exit 0 ;;
esac
EOF2
    chmod +x "$BIN/gh"
    run with_tty "$AGENT_SSH" attach 12
    [ "$status" -eq 1 ]
    [[ "$output" == *"FAIL: no CLAUDE_CODE_OAUTH_TOKEN secret"* ]]
    [[ "$output" != *"script text"* ]]
    [ ! -s "$SSH_LOG" ]
}
