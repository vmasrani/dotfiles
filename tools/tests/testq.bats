#!/usr/bin/env bats
# Behaviour tests for `testq`, the machine-wide build/test queue.
#
# HERMETIC BY CONSTRUCTION
#   Every test runs against its OWN task-spooler socket and its OWN state dir
#   under BATS_TEST_TMPDIR, so the suite never touches -- or is perturbed by --
#   the live queue that real agents are using. Jobs are `sleep`/`exit N`
#   stand-ins; nothing here compiles anything, so the whole file runs in
#   seconds.
#
#   Run:  bats tools/tests/testq.bats
#         bats -f 'position' tools/tests/testq.bats     # one group

setup() {
    TESTQ="${BATS_TEST_DIRNAME}/../testq"
    [ -x "$TESTQ" ] || {
        echo "testq not executable at $TESTQ" >&2
        return 1
    }

    export TESTQ_SOCKET="${BATS_TEST_TMPDIR}/q.sock"
    export TESTQ_STATE="${BATS_TEST_TMPDIR}/state"
    export TESTQ_BUDGET=12
    export TESTQ_HEARTBEAT=0
    export TESTQ_QUIET=1
    unset TESTQ_ACTIVE TESTQ_WEIGHT TESTQ_SESSION TESTQ_SLOTS TESTQ_NO_DEDUP
    export TS_SOCKET="$TESTQ_SOCKET"

    # A shared trace file: jobs append markers so tests can assert on ordering
    # and overlap without sampling the queue.
    TRACE="${BATS_TEST_TMPDIR}/trace"
    : >"$TRACE"
}

teardown() {
    TS_SOCKET="$TESTQ_SOCKET" ts -K 2>/dev/null || true
}

# A job that brackets a sleep with start/end markers, so overlap is visible in
# the trace as interleaving rather than inferred from timing.
job() {
    local name="$1" secs="${2:-1}"
    echo "sh -c 'echo ${name}-start >>$TRACE; sleep $secs; echo ${name}-end >>$TRACE'"
}

# ── position reporting (item 3) ───────────────────────────────────────────

@test "position: reports zero ahead on an empty queue" {
    run "$TESTQ" --ahead
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
}

@test "position: counts a running job as ahead of a new submission" {
    TESTQ_WEIGHT=12 "$TESTQ" sleep 2 &
    sleep 0.5
    run "$TESTQ" --ahead
    wait 2>/dev/null || true
    [ "$output" = "1" ]
}

@test "position: does not count jobs submitted after us" {
    # THE REPORTED BUG. Occupy the queue, then queue two more. The middle job
    # has exactly ONE job ahead of it -- the runner. The old implementation
    # counted every unfinished job except your own, so the job submitted BEHIND
    # you also incremented your count and the number went backwards.
    TESTQ_WEIGHT=12 "$TESTQ" sleep 3 &
    sleep 0.4
    TESTQ_WEIGHT=12 "$TESTQ" true &
    sleep 0.4
    local mine
    mine=$(TS_SOCKET="$TESTQ_SOCKET" ts -l | awk '$2=="queued"{print $1; exit}')
    TESTQ_WEIGHT=12 "$TESTQ" true &
    sleep 0.4

    run "$TESTQ" --ahead-of "$mine"
    wait 2>/dev/null || true
    [ "$output" = "1" ]
}

@test "position: never increases over the lifetime of a queued job" {
    TESTQ_WEIGHT=12 "$TESTQ" sleep 2 &
    sleep 0.3
    TESTQ_WEIGHT=12 TESTQ_HEARTBEAT=1 "$TESTQ" true 2>"${BATS_TEST_TMPDIR}/hb" &
    local mine=$!
    sleep 0.3
    TESTQ_WEIGHT=12 "$TESTQ" true &
    wait 2>/dev/null || true

    # Extract every "N ahead" the heartbeat printed; the sequence must be
    # monotonically non-increasing.
    local seq
    seq=$(grep -o '[0-9]* ahead' "${BATS_TEST_TMPDIR}/hb" | grep -o '^[0-9]*' || true)
    local prev=999
    for n in $seq; do
        [ "$n" -le "$prev" ] || {
            echo "position went backwards: $seq" >&2
            return 1
        }
        prev=$n
    done
}

# ── exit-code ground truth (item 2) ───────────────────────────────────────

@test "exit code: passes through transparently" {
    run "$TESTQ" sh -c 'exit 42'
    [ "$status" -eq 42 ]
}

@test "exit code: recorded in the job record even when the caller pipes output" {
    # The reported failure: `testq cmd | tail` yields tail's status (0), so a
    # suite with failing tests was reported as "exit code 0".
    "$TESTQ" sh -c 'echo hello; exit 7' | tail -1
    run "$TESTQ" --exit-code --last
    [ "$status" -eq 0 ]
    [ "$output" = "7" ]
}

@test "exit code: --status reports the same code as the process returned" {
    run "$TESTQ" sh -c 'exit 3'
    [ "$status" -eq 3 ]
    run "$TESTQ" --status --last
    [[ "$output" == *"exit=3"* ]]
}

@test "status: record carries cwd, command and weight" {
    cd "$BATS_TEST_TMPDIR"
    "$TESTQ" true
    run "$TESTQ" --status --last
    [[ "$output" == *"cwd=$BATS_TEST_TMPDIR"* ]]
    [[ "$output" == *"weight="* ]]
    [[ "$output" == *"cmd="* ]]
}

# ── weighted admission (item 5) ───────────────────────────────────────────

@test "weights: classifies cargo subcommands by cost" {
    run "$TESTQ" --explain cargo nextest run --workspace
    [[ "$output" == *"weight=9"* ]]

    run "$TESTQ" --explain cargo check --workspace
    [[ "$output" == *"weight=3"* ]]

    run "$TESTQ" --explain cargo bench
    [[ "$output" == *"weight=12"* ]]

    run "$TESTQ" --explain cargo fmt --all
    [[ "$output" == *"weight=1"* ]]
}

@test "weights: skips a +toolchain selector when classifying" {
    run "$TESTQ" --explain cargo +nightly bench
    [[ "$output" == *"weight=12"* ]]
}

@test "weights: a light job runs alongside a heavy one" {
    # 9 + 3 = 12 = budget, so these must overlap. This is the head-of-line
    # blocking fix: a 20-second check no longer waits out a 9-minute suite.
    TESTQ_WEIGHT=9 "$TESTQ" sh -c "echo heavy-start >>$TRACE; sleep 2; echo heavy-end >>$TRACE" &
    sleep 0.5
    TESTQ_WEIGHT=3 "$TESTQ" sh -c "echo light-start >>$TRACE; echo light-end >>$TRACE" &
    wait 2>/dev/null || true

    # light ran to completion strictly inside heavy's window
    run grep -n . "$TRACE"
    [[ "$output" == *"heavy-start"* ]]
    local light_line heavy_end_line
    light_line=$(grep -n 'light-end' "$TRACE" | cut -d: -f1)
    heavy_end_line=$(grep -n 'heavy-end' "$TRACE" | cut -d: -f1)
    [ "$light_line" -lt "$heavy_end_line" ]
}

@test "weights: two heavy jobs never overlap" {
    # 9 + 9 = 18 > 12. The RAM cliff this queue exists to prevent.
    TESTQ_WEIGHT=9 "$TESTQ" sh -c "echo a-start >>$TRACE; sleep 1; echo a-end >>$TRACE" &
    sleep 0.3
    TESTQ_WEIGHT=9 "$TESTQ" sh -c "echo b-start >>$TRACE; sleep 1; echo b-end >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    # Strict bracketing: no interleaving in either order.
    [[ "$output" == "a-start"*"a-end"*"b-start"*"b-end" ]] ||
        [[ "$output" == "b-start"*"b-end"*"a-start"*"a-end" ]]
}

@test "weights: a bench excludes everything, including light jobs" {
    TESTQ_WEIGHT=12 "$TESTQ" sh -c "echo bench-start >>$TRACE; sleep 1; echo bench-end >>$TRACE" &
    sleep 0.3
    TESTQ_WEIGHT=1 "$TESTQ" sh -c "echo tiny >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == "bench-start"*"bench-end"*"tiny" ]]
}

@test "weights: a job heavier than the budget is clamped, not deadlocked" {
    run env TESTQ_WEIGHT=999 timeout 10 "$TESTQ" true
    [ "$status" -eq 0 ]
}

# ── priority lane (item 7) ────────────────────────────────────────────────

@test "priority: a priority job jumps ahead of queued jobs" {
    TESTQ_WEIGHT=12 "$TESTQ" sh -c "echo blocker-end >>$TRACE; sleep 1" &
    sleep 0.3
    TESTQ_WEIGHT=12 "$TESTQ" sh -c "echo normal >>$TRACE" &
    sleep 0.3
    TESTQ_WEIGHT=12 "$TESTQ" --priority sh -c "echo urgent >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == *"urgent"*"normal"* ]]
}

# ── abandon reaping (item 9) ──────────────────────────────────────────────

@test "reap: a queued job whose submitter was SIGKILLed is dropped" {
    TESTQ_WEIGHT=12 "$TESTQ" sleep 3 &
    local blocker=$!
    sleep 0.4

    TESTQ_WEIGHT=12 "$TESTQ" sh -c "echo ghost >>$TRACE" &
    local ghost=$!
    sleep 0.4
    kill -9 $ghost 2>/dev/null || true
    sleep 0.2

    # Submitting anything runs the sweep; the ghost must never execute.
    TESTQ_WEIGHT=12 "$TESTQ" true
    wait $blocker 2>/dev/null || true
    sleep 0.5

    run grep -c ghost "$TRACE" 2>/dev/null || true
    [ "${output:-0}" = "0" ]
}

# ── dedup (item 4) ────────────────────────────────────────────────────────

setup_git_repo() {
    REPO="${BATS_TEST_TMPDIR}/repo"
    mkdir -p "$REPO"
    cd "$REPO"
    git init -q .
    echo one >file.txt
    git add -A
    git -c user.email=t@t -c user.name=t commit -qm init
    COUNTER="${BATS_TEST_TMPDIR}/counter"
    : >"$COUNTER"
}

# NB: never `eval "$TESTQ ..." &` here. Under bats' errexit, a backgrounded
# eval whose command fails reports 1 instead of the command's real status --
# which silently turns an exit-code assertion into a test of bash trivia.
# Invoke testq directly and pass the script body as one argument.

@test "dedup: identical jobs in an unchanged tree coalesce" {
    setup_git_repo
    # The body appends once per REAL execution, so the counter is a direct
    # count of how many times the work actually happened.
    local body="echo ran >>$COUNTER; sleep 1; echo output-line"
    "$TESTQ" sh -c "$body" >"${BATS_TEST_TMPDIR}/o1" &
    sleep 0.3
    "$TESTQ" sh -c "$body" >"${BATS_TEST_TMPDIR}/o2" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "1" ]
    # ...and the follower still receives the leader's output on stdout.
    run cat "${BATS_TEST_TMPDIR}/o2"
    [[ "$output" == *"output-line"* ]]
}

@test "dedup: a dirty working tree breaks the coalesce" {
    setup_git_repo
    local body="echo ran >>$COUNTER; sleep 1"
    "$TESTQ" sh -c "$body" &
    sleep 0.3
    echo two >>file.txt   # tree moved -- the second job MUST run for real
    "$TESTQ" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: outside a git repo, nothing is ever coalesced" {
    cd "$BATS_TEST_TMPDIR"
    COUNTER="${BATS_TEST_TMPDIR}/counter"
    : >"$COUNTER"
    local body="echo ran >>$COUNTER; sleep 1"
    "$TESTQ" sh -c "$body" &
    sleep 0.3
    "$TESTQ" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: TESTQ_NO_DEDUP=1 forces a real run" {
    setup_git_repo
    local body="echo ran >>$COUNTER; sleep 1"
    TESTQ_NO_DEDUP=1 "$TESTQ" sh -c "$body" &
    sleep 0.3
    TESTQ_NO_DEDUP=1 "$TESTQ" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: a failing leader propagates its exit code to the follower" {
    setup_git_repo
    local body="sleep 1; exit 9"
    "$TESTQ" sh -c "$body" &
    local a=$!
    sleep 0.3
    local follower_status=0
    "$TESTQ" sh -c "$body" || follower_status=$?
    local leader_status=0
    wait $a || leader_status=$?
    [ "$leader_status" -eq 9 ]
    [ "$follower_status" -eq 9 ]
}

# ── transparency contract ─────────────────────────────────────────────────

@test "transparency: the job inherits the caller's cwd" {
    cd "$BATS_TEST_TMPDIR"
    run "$TESTQ" pwd
    [[ "$output" == *"$BATS_TEST_TMPDIR"* ]]
}

@test "transparency: the job inherits exported environment" {
    export TESTQ_CANARY=squirrel
    run "$TESTQ" sh -c 'echo $TESTQ_CANARY'
    [[ "$output" == *"squirrel"* ]]
}

@test "transparency: stdout and stderr stay separate" {
    # The whole point of item 1: a caller must still be able to discard stderr
    # and keep stdout intact.
    run bash -c "'$TESTQ' sh -c 'echo OUT; echo ERR >&2' 2>/dev/null"
    [[ "$output" == *"OUT"* ]]
    [[ "$output" != *"ERR"* ]]
}

@test "transparency: stdin is passed through" {
    run bash -c "echo piped-in | '$TESTQ' cat"
    [[ "$output" == *"piped-in"* ]]
}

@test "transparency: TESTQ_ACTIVE bypasses the queue entirely" {
    run env TESTQ_ACTIVE=1 TESTQ_SOCKET=/nonexistent/nope.sock "$TESTQ" echo direct
    [ "$status" -eq 0 ]
    [[ "$output" == *"direct"* ]]
}

# ── history and ETA (item 8) ──────────────────────────────────────────────

@test "history: a completed job appends a duration record" {
    "$TESTQ" sleep 1
    [ -s "$TESTQ_STATE/history.tsv" ]
    run cat "$TESTQ_STATE/history.tsv"
    [ "$status" -eq 0 ]
    [[ "$output" == *"other"* ]]
}

@test "eta: the waiting line names the job that is blocking us" {
    TESTQ_WEIGHT=12 "$TESTQ" sleep 2 &
    sleep 0.4
    run env TESTQ_QUIET= TESTQ_WEIGHT=12 bash -c "'$TESTQ' true 2>&1 >/dev/null"
    wait 2>/dev/null || true
    [[ "$output" == *"blocked by"* ]]
}

# ── management surface ────────────────────────────────────────────────────

@test "cli: --budget reports the configured budget" {
    run "$TESTQ" --budget
    [[ "$output" == *"12"* ]]
}

@test "cli: --slots is still accepted as a deprecated alias" {
    run "$TESTQ" --slots
    [ "$status" -eq 0 ]
}

@test "cli: running with no command is an error, not a hang" {
    run "$TESTQ"
    [ "$status" -ne 0 ]
}

@test "cli: --help works without a running daemon" {
    TS_SOCKET="$TESTQ_SOCKET" ts -K 2>/dev/null || true
    run "$TESTQ" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"USAGE"* ]]
}
