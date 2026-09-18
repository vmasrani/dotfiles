#!/usr/bin/env bats
# Behaviour tests for `agent-ssh`, the tool that SSHes into a fresh agent-image
# job and attaches its tmux session.
#
# HERMETIC BY CONSTRUCTION
#   The tests exercise the tool's factored-out pure helpers through hidden
#   dispatch hooks (`__extract-ssh`, `__valid-minutes`, `__resolve-ref`) so
#   nothing here touches the network or GitHub. A fake `gh` is placed first on
#   PATH for the ref-resolution tests and answers only which refs "exist".
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

# ── help / usage ──────────────────────────────────────────────────────────────

@test "help: prints usage and the attach hint" {
    run "$AGENT_SSH" help
    [ "$status" -eq 0 ]
    [[ "$output" == *"Usage:"* ]]
    [[ "$output" == *"tmux attach -t agent"* ]]
}

@test "help: unknown command fails loud" {
    run "$AGENT_SSH" frobnicate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command"* ]]
}

# ── ssh-address extraction ────────────────────────────────────────────────────

@test "extract: pulls the ssh address out of a log line" {
    run "$AGENT_SSH" __extract-ssh "::notice::SSH: ssh aB3xZ9qPkL7@nyc1.tmate.io"
    [ "$status" -eq 0 ]
    [ "$output" = "ssh aB3xZ9qPkL7@nyc1.tmate.io" ]
}

@test "extract: picks the ssh line, not the web url, and tolerates _/- tokens" {
    local log="Web shell: https://tmate.io/t/abc
SSH: ssh To_ken-9@sfo2.tmate.io"
    run "$AGENT_SSH" __extract-ssh "$log"
    [ "$status" -eq 0 ]
    [ "$output" = "ssh To_ken-9@sfo2.tmate.io" ]
}

@test "extract: reads from stdin when given no argument" {
    run bash -c 'printf "noise\nSSH: ssh Zz9@lon1.tmate.io\n" | "'"$AGENT_SSH"'" __extract-ssh'
    [ "$status" -eq 0 ]
    [ "$output" = "ssh Zz9@lon1.tmate.io" ]
}

@test "extract: no address present returns non-zero and prints nothing" {
    run "$AGENT_SSH" __extract-ssh "nothing to see here"
    [ "$status" -eq 1 ]
    [ -z "$output" ]
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
