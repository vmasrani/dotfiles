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
