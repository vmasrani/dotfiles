#!/usr/bin/env bats
# Behaviour tests for `agent-ssh`, the dispatcher for the headless Claude agent
# workflow (claude-agent.yml).
#
# HERMETIC BY CONSTRUCTION
#   Pure helpers are exercised through hidden dispatch hooks; the gh-backed
#   commands run against a fake `gh` placed first on PATH that records its
#   arguments. Nothing touches the network or GitHub, and no workflow is
#   dispatched.
#
#   ZDOTDIR points at an empty dir so the tool's zsh skips the user's ~/.zshenv
#   (keeps the fake `gh` first on PATH and the run fast). NO_GUM=1 forces
#   plain-text output.
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

    export ZDOTDIR="${BATS_TEST_TMPDIR}/zdot"
    mkdir -p "$ZDOTDIR"

    export NO_GUM=1
    export GH_LOG="${BATS_TEST_TMPDIR}/gh.log"
    : >"$GH_LOG"

    # sleep is a no-op so polling loops are instant.
    printf '#!/usr/bin/env bash\nexit 0\n' >"$BIN/sleep"
    chmod +x "$BIN/sleep"
}

RUNS_JSON='[
 {"databaseId":300,"displayTitle":"agent issue #1932","status":"completed","conclusion":"success"},
 {"databaseId":299,"displayTitle":"agent issue #1900","status":"in_progress","conclusion":""},
 {"databaseId":298,"displayTitle":"agent issue #1932","status":"completed","conclusion":"failure"}]'

# Fake gh: records every call to $GH_LOG; `run list` answers by --json fields.
write_fake_gh() {
    cat >"$BIN/gh" <<'EOF'
#!/usr/bin/env bash
echo "$*" >>"$GH_LOG"
case "$*" in
    "auth status"*|"api repos/"*) exit 0 ;;
    "workflow run"*) exit "${GH_DISPATCH_RC:-0}" ;;
    "run list"*"createdAt"*)
        if [[ "${GH_NO_NEW_RUN:-}" == 1 ]]; then echo null; else echo '{"createdAt":"2999-01-01T00:00:00Z","databaseId":4242}'; fi ;;
    "run list"*) printf '%s\n' "$GH_RUNS_JSON" ;;
    "pr list"*) printf '%s\n' "${GH_PR_ROWS:-}" ;;
    "run cancel"*) exit "${GH_CANCEL_RC:-0}" ;;
    "run watch"*) exit 0 ;;
    *) echo "unexpected gh call: $*" >&2; exit 99 ;;
esac
EOF
    chmod +x "$BIN/gh"
    export GH_RUNS_JSON="$RUNS_JSON"
}

# ── help ──────────────────────────────────────────────────────────────────────

@test "help: lists every subcommand and the workflow, no ssh connect" {
    run "$AGENT_SSH" help
    [ "$status" -eq 0 ]
    for w in "Usage:" "claude-agent.yml" "run <issue>" "status [issue]" "watch <run-id>" "kill <run-id>"; do
        [[ "$output" == *"$w"* ]] || { echo "missing: $w" >&2; return 1; }
    done
    [[ "$output" != *"upterm"* ]]
    [[ "$output" != *"connect"*"SSH address"* ]]
}

@test "help: unknown command fails loud" {
    run "$AGENT_SSH" frobnicate
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command"* ]]
}

@test "help: the removed connect command is now unknown" {
    run "$AGENT_SSH" connect
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command"* ]]
}

# ── pure helpers ──────────────────────────────────────────────────────────────

@test "issue: accepts whole numbers, rejects the rest" {
    for v in 1 1932 20000; do
        run "$AGENT_SSH" __valid-issue "$v"; [ "$status" -eq 0 ] || { echo "expected $v valid" >&2; return 1; }
    done
    for v in 0 -3 abc 1.5 "#12" ""; do
        run "$AGENT_SSH" __valid-issue "$v"; [ "$status" -eq 1 ] || { echo "expected '$v' rejected" >&2; return 1; }
    done
}

@test "effort: accepts low/medium/high only" {
    for v in low medium high; do
        run "$AGENT_SSH" __valid-effort "$v"; [ "$status" -eq 0 ] || { echo "expected $v valid" >&2; return 1; }
    done
    for v in max Low "" "low medium" xhigh; do
        run "$AGENT_SSH" __valid-effort "$v"; [ "$status" -eq 1 ] || { echo "expected '$v' rejected" >&2; return 1; }
    done
}

@test "title: pulls the issue number out of a run title" {
    run "$AGENT_SSH" __issue-from-title "agent issue #1932"
    [ "$status" -eq 0 ]
    [ "$output" = "1932" ]
}

@test "title: no issue in the title returns non-zero" {
    for t in "Claude agent" "agent issue #" "agent issue #abc" ""; do
        run "$AGENT_SSH" __issue-from-title "$t"
        [ "$status" -eq 1 ] || { echo "expected '$t' rejected" >&2; return 1; }
        [ -z "$output" ]
    done
}

@test "format-runs: one row per run with id, issue, status, conclusion" {
    run bash -c 'printf "%s" "$1" | "$2" __format-runs' _ "$RUNS_JSON" "$AGENT_SSH"
    [ "$status" -eq 0 ]
    [ "${lines[0]}" = "300  #1932  completed  success" ]
    [ "${lines[1]}" = "299  #1900  in_progress  -" ]
    [ "${lines[2]}" = "298  #1932  completed  failure" ]
}

@test "format-runs: filters to one issue; no match prints nothing" {
    run bash -c 'printf "%s" "$1" | "$2" __format-runs 1900' _ "$RUNS_JSON" "$AGENT_SSH"
    [ "$status" -eq 0 ]
    [ "$output" = "299  #1900  in_progress  -" ]
    run bash -c 'printf "%s" "$1" | "$2" __format-runs 7' _ "$RUNS_JSON" "$AGENT_SSH"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "dispatch-fields: always issue/effort/base; brief only when given" {
    run "$AGENT_SSH" __dispatch-fields 12 high dev ""
    [ "$output" = $'-f\nissue=12\n-f\neffort=high\n-f\nbase=dev' ]
    run "$AGENT_SSH" __dispatch-fields 12 low pre-dev "do X, then Y"
    [[ "$output" == *$'-f\nbase=pre-dev\n-f\nbrief=do X, then Y' ]]
}

# ── run ───────────────────────────────────────────────────────────────────────

@test "run: dispatches claude-agent.yml on dev with defaults and prints the URL" {
    write_fake_gh
    run "$AGENT_SSH" run 1932
    [ "$status" -eq 0 ]
    [[ "$output" == *"https://github.com/sophiaconsulting/cartridge/actions/runs/4242"* ]]
    grep -qx 'workflow run claude-agent.yml --repo sophiaconsulting/cartridge --ref dev -f issue=1932 -f effort=medium -f base=dev' "$GH_LOG"
}

@test "run: passes effort, --base and --brief through; AGENT_SSH_REPO is honoured" {
    write_fake_gh
    export AGENT_SSH_REPO="acme/widgets"
    run "$AGENT_SSH" run 7 high --base pre-dev --brief "touch only src/a.rs"
    [ "$status" -eq 0 ]
    grep -qx 'workflow run claude-agent.yml --repo acme/widgets --ref dev -f issue=7 -f effort=high -f base=pre-dev -f brief=touch only src/a.rs' "$GH_LOG"
}

@test "run: bad issue, bad effort, missing issue and unknown flag fail loud before any dispatch" {
    write_fake_gh
    run "$AGENT_SSH" run abc;            [ "$status" -eq 1 ]; [[ "$output" == *"whole number"* ]]
    run "$AGENT_SSH" run 5 extreme;      [ "$status" -eq 1 ]; [[ "$output" == *"low medium high"* ]]
    run "$AGENT_SSH" run;                [ "$status" -eq 1 ]; [[ "$output" == *"Usage"* ]]
    run "$AGENT_SSH" run 5 --bogus;      [ "$status" -eq 1 ]; [[ "$output" == *"Unknown option"* ]]
    run "$AGENT_SSH" run 5 --base;       [ "$status" -eq 1 ]; [[ "$output" == *"--base needs"* ]]
    ! grep -q '^workflow run' "$GH_LOG"
}

@test "run: a refused dispatch and a missing new run both fail loud" {
    write_fake_gh
    GH_DISPATCH_RC=1 run "$AGENT_SSH" run 5
    [ "$status" -eq 1 ]
    [[ "$output" == *"Could not dispatch"* ]]
    GH_NO_NEW_RUN=1 run "$AGENT_SSH" run 5
    [ "$status" -eq 1 ]
    [[ "$output" == *"no run appeared"* ]]
}

# ── status / watch / kill ─────────────────────────────────────────────────────

@test "status: lists the latest runs with issue, status and conclusion" {
    write_fake_gh
    run "$AGENT_SSH" status
    [ "$status" -eq 0 ]
    [[ "$output" == *"300  #1932  completed  success"* ]]
    [[ "$output" == *"299  #1900  in_progress  -"* ]]
    ! grep -q '^pr list' "$GH_LOG"
}

@test "status <issue>: filters runs and shows the linked PR" {
    write_fake_gh
    export GH_PR_ROWS='#1940  OPEN  https://github.com/x/y/pull/1940'
    run "$AGENT_SSH" status 1932
    [ "$status" -eq 0 ]
    [[ "$output" == *"300  #1932"* ]]
    [[ "$output" != *"#1900"* ]]
    [[ "$output" == *"#1940  OPEN  https://github.com/x/y/pull/1940"* ]]
    grep -q 'pr list .*--head issue-1932' "$GH_LOG"
}

@test "status <issue>: no PR yet says so; bad issue fails loud" {
    write_fake_gh
    run "$AGENT_SSH" status 1900
    [ "$status" -eq 0 ]
    [[ "$output" == *"none yet"* ]]
    run "$AGENT_SSH" status abc
    [ "$status" -eq 1 ]
}

@test "watch: runs gh run watch on the id; non-numeric id fails loud" {
    write_fake_gh
    run "$AGENT_SSH" watch 4242
    [ "$status" -eq 0 ]
    grep -qx 'run watch 4242 --repo sophiaconsulting/cartridge' "$GH_LOG"
    run "$AGENT_SSH" watch
    [ "$status" -eq 1 ]
    [[ "$output" == *"numeric run id"* ]]
}

@test "kill: cancels the run; a failed cancel and a bad id fail loud" {
    write_fake_gh
    run "$AGENT_SSH" kill 4242
    [ "$status" -eq 0 ]
    grep -qx 'run cancel 4242 --repo sophiaconsulting/cartridge' "$GH_LOG"
    GH_CANCEL_RC=1 run "$AGENT_SSH" kill 4242
    [ "$status" -eq 1 ]
    [[ "$output" == *"Could not cancel"* ]]
    run "$AGENT_SSH" kill nope
    [ "$status" -eq 1 ]
}
