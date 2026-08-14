#!/usr/bin/env bats
# Behaviour tests for `queue`, the machine-wide build/test queue.
#
# HERMETIC BY CONSTRUCTION
#   Every test runs against its OWN task-spooler socket and its OWN state dir
#   under BATS_TEST_TMPDIR, so the suite never touches -- or is perturbed by --
#   the live queue that real agents are using. Jobs are `sleep`/`exit N`
#   stand-ins; nothing here compiles anything, so the whole file runs in
#   seconds.
#
#   Run:  bats tools/tests/queue.bats
#         bats -f 'position' tools/tests/queue.bats     # one group
#
# THE SCHEDULING MODEL THESE TESTS ENCODE
#   QUEUE_SLOTS (default 1) jobs run at once; every job costs one slot and
#   `--solo` costs all of them. There is no weight table and nothing inspects
#   the command, so most serialization assertions below need no mechanism at
#   all -- the default single slot already serializes everything.

setup() {
    QUEUE="${BATS_TEST_DIRNAME}/../queue"
    [ -x "$QUEUE" ] || {
        echo "queue not executable at $QUEUE" >&2
        return 1
    }

    export QUEUE_SOCKET="${BATS_TEST_TMPDIR}/q.sock"
    export QUEUE_STATE="${BATS_TEST_TMPDIR}/state"
    export QUEUE_HEARTBEAT=0
    export QUEUE_QUIET=1
    # QUEUE_BUDGET/QUEUE_WEIGHT are the obsolete knobs; a stray one in the
    # operator's environment would print a warning into every test's output.
    unset QUEUE_ACTIVE QUEUE_SESSION QUEUE_SLOTS QUEUE_NO_DEDUP \
          QUEUE_BUDGET QUEUE_WEIGHT TESTQ_BUDGET TESTQ_WEIGHT
    export TS_SOCKET="$QUEUE_SOCKET"

    # A shared trace file: jobs append markers so tests can assert on ordering
    # and overlap without sampling the queue.
    TRACE="${BATS_TEST_TMPDIR}/trace"
    : >"$TRACE"
}

teardown() {
    # `drain`, not a bare `ts -K`: several tests below pin fixtures behind a
    # 20-second blocker, and an assertion that fails before the test's own
    # cleanup would otherwise leave that blocker running -- holding bats' output
    # pipe open and hanging the whole FILE on one failed test. Teardown always
    # runs, so the teardown is where this belongs.
    drain
}

# ── position reporting (item 3) ───────────────────────────────────────────

@test "position: reports zero ahead on an empty queue" {
    run "$QUEUE" --ahead
    [ "$status" -eq 0 ]
    [ "$output" = "0" ]
}

@test "position: counts a running job as ahead of a new submission" {
    "$QUEUE" sleep 2 &
    sleep 0.5
    run "$QUEUE" --ahead
    wait 2>/dev/null || true
    [ "$output" = "1" ]
}

@test "position: does not count jobs submitted after us" {
    # THE REPORTED BUG. Occupy the queue, then queue two more. The middle job
    # has exactly ONE job ahead of it -- the runner. The old implementation
    # counted every unfinished job except your own, so the job submitted BEHIND
    # you also incremented your count and the number went backwards.
    #
    # The two followers run DIFFERENT commands on purpose: identical argv
    # against an unchanged tree coalesces, and a coalesced follower never
    # enters the queue at all -- which would make this test vacuously green.
    "$QUEUE" sleep 3 &
    sleep 0.4
    "$QUEUE" sh -c 'exit 0' &      # ours
    "$QUEUE" true &                # submitted BEHIND us
    # Poll rather than sleep: computing a dedup key walks the whole worktree,
    # so how long a submission takes to appear depends on the repo, not on us.
    local queued=0 tries=0
    while (( tries++ < 60 )); do
        queued=$(TS_SOCKET="$QUEUE_SOCKET" ts -l | awk '$2=="queued"{n++} END{print n+0}')
        [ "$queued" -ge 2 ] && break
        sleep 0.2
    done
    [ "$queued" -ge 2 ]
    local mine
    mine=$(TS_SOCKET="$QUEUE_SOCKET" ts -l | awk '$2=="queued"{print $1; exit}')

    run "$QUEUE" --ahead-of "$mine"
    wait 2>/dev/null || true
    [ "$output" = "1" ]
}

@test "position: never increases over the lifetime of a queued job" {
    "$QUEUE" sleep 2 &
    sleep 0.3
    QUEUE_HEARTBEAT=1 "$QUEUE" true 2>"${BATS_TEST_TMPDIR}/hb" &
    sleep 0.3
    "$QUEUE" true &
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
    run "$QUEUE" sh -c 'exit 42'
    [ "$status" -eq 42 ]
}

@test "exit code: recorded in the job record even when the caller pipes output" {
    # The reported failure: `queue cmd | tail` yields tail's status (0), so a
    # suite with failing tests was reported as "exit code 0".
    "$QUEUE" sh -c 'echo hello; exit 7' | tail -1
    run "$QUEUE" --exit-code --last
    [ "$status" -eq 0 ]
    [ "$output" = "7" ]
}

@test "exit code: --status reports the same code as the process returned" {
    run "$QUEUE" sh -c 'exit 3'
    [ "$status" -eq 3 ]
    run "$QUEUE" --status --last
    [[ "$output" == *"exit=3"* ]]
}

@test "status: the record carries cwd, command and slot cost" {
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" true
    run "$QUEUE" --status --last
    [[ "$output" == *"cwd=$BATS_TEST_TMPDIR"* ]]
    [[ "$output" == *"cmd="* ]]
    [[ "$output" == *"cost=1"* ]]
    [[ "$output" == *"slots=1"* ]]
    [[ "$output" == *"solo=0"* ]]
}

@test "status: the record no longer carries a weight or a class" {
    # The weighted-admission fields are gone, not merely unused. A reader that
    # still finds `weight=` would conclude the old model is live.
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" true
    run "$QUEUE" --status --last
    [[ "$output" != *"weight="* ]]
    [[ "$output" != *"class="* ]]
    [[ "$output" != *"budget="* ]]
}

# ── slots: the whole scheduling model ─────────────────────────────────────

@test "slots: the default is one slot, so two jobs never overlap" {
    # No weight, no flag, no env var: one slot IS the serialization mechanism.
    "$QUEUE" sh -c "echo a-start >>$TRACE; sleep 1; echo a-end >>$TRACE" &
    sleep 0.3
    "$QUEUE" sh -c "echo b-start >>$TRACE; sleep 1; echo b-end >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    # Strict bracketing: no interleaving in either order.
    [[ "$output" == "a-start"*"a-end"*"b-start"*"b-end" ]] ||
        [[ "$output" == "b-start"*"b-end"*"a-start"*"a-end" ]]
}

@test "slots: QUEUE_SLOTS=2 lets two jobs overlap" {
    QUEUE_SLOTS=2 "$QUEUE" sh -c "echo long-start >>$TRACE; sleep 2; echo long-end >>$TRACE" &
    sleep 0.5
    QUEUE_SLOTS=2 "$QUEUE" sh -c "echo short >>$TRACE" &
    wait 2>/dev/null || true

    # The short job ran to completion strictly inside the long one's window.
    local short_line long_end_line
    short_line=$(grep -n 'short' "$TRACE" | cut -d: -f1)
    long_end_line=$(grep -n 'long-end' "$TRACE" | cut -d: -f1)
    [ -n "$short_line" ]
    [ "$short_line" -lt "$long_end_line" ]
}

@test "slots: --solo takes every slot, so nothing runs beside it" {
    # Two slots are free, and the second job costs only one -- it still waits,
    # because --solo's cost is the whole slot count.
    QUEUE_SLOTS=2 "$QUEUE" --solo sh -c "echo solo-start >>$TRACE; sleep 2; echo solo-end >>$TRACE" &
    sleep 0.5
    QUEUE_SLOTS=2 "$QUEUE" sh -c "echo other >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == "solo-start"*"solo-end"*"other" ]]
}

@test "slots: --solo is recorded as costing every slot" {
    cd "$BATS_TEST_TMPDIR"
    QUEUE_SLOTS=3 "$QUEUE" --solo true
    run "$QUEUE" --status --last
    [[ "$output" == *"cost=3"* ]]
    [[ "$output" == *"solo=1"* ]]
}

# ── the `&&` trap: one quoted argument is a shell command ─────────────────

@test "args: a single argument containing shell syntax runs as a whole chain" {
    # THE HEADLINE FIX. `queue cd /x && cargo test` splits in the caller's
    # shell, queues only the `cd`, and runs the suite completely unqueued.
    # Quoting the whole thing keeps the operator inside our argv, and a single
    # argument carrying shell syntax is run via `zsh -c`.
    mkdir -p "${BATS_TEST_TMPDIR}/sub"
    cd "$BATS_TEST_TMPDIR"
    run "$QUEUE" "cd ${BATS_TEST_TMPDIR}/sub && echo chained-ran"
    [ "$status" -eq 0 ]
    [[ "$output" == *"chained-ran"* ]]
}

@test "args: the chain's exit code is the chain's, not the cd's" {
    cd "$BATS_TEST_TMPDIR"
    run "$QUEUE" "cd ${BATS_TEST_TMPDIR} && exit 17"
    [ "$status" -eq 17 ]
}

@test "args: a single bare word still execs directly, with no shell wrapper" {
    # The distinction is visible to the caller -- did you type a space or a
    # metacharacter? -- not inferred from what the command means. A bare word
    # must not pay for a shell, so the record shows the argv verbatim.
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" true
    run "$QUEUE" --status --last
    [[ "$output" == *"cmd=true"* ]]
    [[ "$output" != *"cmd=zsh"* ]]
}

# ── obsolete knobs are ignored LOUDLY, never reinterpreted ────────────────

@test "obsolete: QUEUE_BUDGET warns and is ignored, not read as a slot count" {
    # Reading a 12-unit budget AS 12 slots would be a silent 12x
    # over-admission -- the exact disaster the queue exists to prevent.
    cd "$BATS_TEST_TMPDIR"
    run env QUEUE_BUDGET=12 "$QUEUE" true
    [ "$status" -eq 0 ]
    [[ "$output" == *"QUEUE_BUDGET"* ]]
    [[ "$output" == *"IGNORED"* ]]

    run "$QUEUE" --status --last
    [[ "$output" == *"slots=1"* ]]
}

@test "obsolete: QUEUE_WEIGHT warns and is ignored" {
    cd "$BATS_TEST_TMPDIR"
    run env QUEUE_WEIGHT=9 "$QUEUE" true
    [ "$status" -eq 0 ]
    [[ "$output" == *"QUEUE_WEIGHT"* ]]
    [[ "$output" == *"IGNORED"* ]]

    run "$QUEUE" --status --last
    [[ "$output" == *"cost=1"* ]]
}

@test "obsolete: an explicit QUEUE_SLOTS wins over a stray QUEUE_BUDGET" {
    run env QUEUE_BUDGET=12 QUEUE_SLOTS=2 "$QUEUE" --slots
    [ "$status" -eq 0 ]
    [[ "$output" == *"2 slot"* ]]
}

# ── priority lane (item 7) ────────────────────────────────────────────────

@test "priority: a priority job jumps ahead of queued jobs" {
    "$QUEUE" sh -c "echo blocker-end >>$TRACE; sleep 1" &
    sleep 0.3
    "$QUEUE" sh -c "echo normal >>$TRACE" &
    sleep 0.3
    "$QUEUE" --priority sh -c "echo urgent >>$TRACE" &
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == *"urgent"*"normal"* ]]
}

# ── abandon reaping (item 9) ──────────────────────────────────────────────

@test "reap: a queued job whose submitter was SIGKILLed is dropped" {
    "$QUEUE" sleep 3 &
    local blocker=$!
    sleep 0.4

    "$QUEUE" sh -c "echo ghost >>$TRACE" &
    local ghost=$!
    sleep 0.4
    kill -9 $ghost 2>/dev/null || true
    sleep 0.2

    # Submitting anything runs the sweep; the ghost must never execute.
    "$QUEUE" true
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

# NB: never `eval "$QUEUE ..." &` here. Under bats' errexit, a backgrounded
# eval whose command fails reports 1 instead of the command's real status --
# which silently turns an exit-code assertion into a test of bash trivia.
# Invoke queue directly and pass the script body as one argument.

@test "dedup: identical jobs in an unchanged tree coalesce" {
    setup_git_repo
    # The body appends once per REAL execution, so the counter is a direct
    # count of how many times the work actually happened.
    local body="echo ran >>$COUNTER; sleep 1; echo output-line"
    "$QUEUE" sh -c "$body" >"${BATS_TEST_TMPDIR}/o1" &
    sleep 0.3
    "$QUEUE" sh -c "$body" >"${BATS_TEST_TMPDIR}/o2" &
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
    "$QUEUE" sh -c "$body" &
    sleep 0.3
    echo two >>file.txt   # tree moved -- the second job MUST run for real
    "$QUEUE" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: outside a git repo, nothing is ever coalesced" {
    cd "$BATS_TEST_TMPDIR"
    COUNTER="${BATS_TEST_TMPDIR}/counter"
    : >"$COUNTER"
    local body="echo ran >>$COUNTER; sleep 1"
    "$QUEUE" sh -c "$body" &
    sleep 0.3
    "$QUEUE" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: QUEUE_NO_DEDUP=1 forces a real run" {
    setup_git_repo
    local body="echo ran >>$COUNTER; sleep 1"
    QUEUE_NO_DEDUP=1 "$QUEUE" sh -c "$body" &
    sleep 0.3
    QUEUE_NO_DEDUP=1 "$QUEUE" sh -c "$body" &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

@test "dedup: a failing leader propagates its exit code to the follower" {
    setup_git_repo
    local body="sleep 1; exit 9"
    "$QUEUE" sh -c "$body" &
    local a=$!
    sleep 0.3
    local follower_status=0
    "$QUEUE" sh -c "$body" || follower_status=$?
    local leader_status=0
    wait $a || leader_status=$?
    [ "$leader_status" -eq 9 ]
    [ "$follower_status" -eq 9 ]
}

@test "dedup: a trailing 2>&1 does not defeat the coalesce" {
    # OBSERVED IN PRODUCTION: two `just ci-fast` submissions against one tree,
    # one of them written with a trailing `2>&1`. Byte-identity said they were
    # different jobs and both suites ran. Merging the streams changes what the
    # CALLER sees, never what the run produces -- and a follower replays the
    # leader's separately-captured .out/.err either way.
    setup_git_repo
    local body="echo ran >>$COUNTER; sleep 1"
    "$QUEUE" "$body" >/dev/null &
    sleep 0.4
    "$QUEUE" "$body 2>&1" >/dev/null &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "1" ]
    # ...and the follower says so in its own record, not just by not running.
    run "$QUEUE" --status --last
    [[ "$output" == *"deduped_from="* ]]
}

@test "dedup: a trailing 2>/dev/null is NOT normalised away" {
    # The boundary of the normalisation: discarding stderr changes what the
    # command emits, so two jobs differing there are genuinely different work
    # and a follower would be handed output its own redirect said to drop.
    setup_git_repo
    local body="echo ran >>$COUNTER; sleep 1"
    "$QUEUE" "$body" >/dev/null &
    sleep 0.4
    "$QUEUE" "$body 2>/dev/null" >/dev/null &
    wait 2>/dev/null || true

    run wc -l <"$COUNTER"
    [ "$(echo "$output" | tr -d ' ')" = "2" ]
}

# ── transparency contract ─────────────────────────────────────────────────

@test "transparency: the job inherits the caller's cwd" {
    cd "$BATS_TEST_TMPDIR"
    run "$QUEUE" pwd
    [[ "$output" == *"$BATS_TEST_TMPDIR"* ]]
}

@test "transparency: the job inherits exported environment" {
    export QUEUE_CANARY=squirrel
    run "$QUEUE" sh -c 'echo $QUEUE_CANARY'
    [[ "$output" == *"squirrel"* ]]
}

@test "transparency: stdout and stderr stay separate" {
    # The whole point of item 1: a caller must still be able to discard stderr
    # and keep stdout intact.
    run bash -c "'$QUEUE' sh -c 'echo OUT; echo ERR >&2' 2>/dev/null"
    [[ "$output" == *"OUT"* ]]
    [[ "$output" != *"ERR"* ]]
}

@test "transparency: stdin is passed through" {
    run bash -c "echo piped-in | '$QUEUE' cat"
    [[ "$output" == *"piped-in"* ]]
}

@test "transparency: QUEUE_ACTIVE bypasses the queue entirely" {
    run env QUEUE_ACTIVE=1 QUEUE_SOCKET=/nonexistent/nope.sock "$QUEUE" echo direct
    [ "$status" -eq 0 ]
    [[ "$output" == *"direct"* ]]
}

@test "transparency: QUEUE_ACTIVE strips every submission flag, not just one" {
    # The bypass has to consume flags in a LOOP. Shifting exactly once made
    # `--solo --priority cmd` try to exec a binary named `--priority`, which is
    # the one shape a queued job that re-invokes queue is most likely to have.
    run env QUEUE_ACTIVE=1 QUEUE_SOCKET=/nonexistent/nope.sock \
        "$QUEUE" --solo --priority echo nested
    [ "$status" -eq 0 ]
    [[ "$output" == *"nested"* ]]
}

@test "transparency: QUEUE_ACTIVE treats -- as the end of the flags" {
    # Without an explicit `--` arm the bypass would fall through to the queue
    # and deadlock waiting for the capacity its own parent is holding.
    run env QUEUE_ACTIVE=1 QUEUE_SOCKET=/nonexistent/nope.sock \
        "$QUEUE" -- echo after-dashes
    [ "$status" -eq 0 ]
    [[ "$output" == *"after-dashes"* ]]
}

@test "args: -- ends the flags on the normal submission path too" {
    # `--` is how you queue a command whose own first word starts with a dash.
    cd "$BATS_TEST_TMPDIR"
    run "$QUEUE" -- echo queued-after-dashes
    [ "$status" -eq 0 ]
    [[ "$output" == *"queued-after-dashes"* ]]
}

# ── history and ETA (item 8) ──────────────────────────────────────────────

@test "history: a completed job appends a duration record" {
    # Three columns now -- cmdkey, elapsed, rc. The leading weight class went
    # with the classifier, so a 4-column row would mean stale code is writing.
    #
    # KNOWN DEFECT, and why the separator is normalised before counting:
    # history_append() uses `print -r`, which DISABLES zsh's escape handling,
    # so the rows are joined by a literal backslash-t rather than a tab.
    # history_median() reads them with `awk -F'\t'` (a real tab), so it can
    # never match a row and every ETA silently reads as "unknown". Reported,
    # not fixed here. The sed below is a no-op once the writer emits real tabs,
    # so this assertion holds before and after the fix.
    "$QUEUE" sleep 1
    [ -s "$QUEUE_STATE/history.tsv" ]
    local fields
    fields=$(head -1 "$QUEUE_STATE/history.tsv" | sed $'s/\\\\t/\t/g' | awk -F'\t' '{print NF}')
    [ "$fields" = "3" ]
}

@test "eta: the waiting line names the job that is blocking us" {
    "$QUEUE" sleep 2 &
    sleep 0.4
    run env QUEUE_QUIET= bash -c "'$QUEUE' true 2>&1 >/dev/null"
    wait 2>/dev/null || true
    [[ "$output" == *"blocked by"* ]]
}

# ── management surface ────────────────────────────────────────────────────

@test "cli: --slots with no argument reports the count" {
    run "$QUEUE" --slots
    [ "$status" -eq 0 ]
    [[ "$output" == *"1 slot"* ]]
}

@test "cli: --slots N sets the count on the running daemon" {
    run "$QUEUE" --slots 4
    [ "$status" -eq 0 ]
    [[ "$output" == *"4"* ]]
    # Read it back from task-spooler itself, not from queue: a second
    # `queue --slots` would call ensure_server and reset it to QUEUE_SLOTS.
    run env TS_SOCKET="$QUEUE_SOCKET" ts -S
    [[ "$output" == *"4"* ]]
}

@test "cli: --slots 0 fails loudly" {
    run "$QUEUE" --slots 0
    [ "$status" -ne 0 ]
    [[ "$output" == *"positive integer"* ]]
}

@test "cli: --slots with a non-number fails loudly" {
    run "$QUEUE" --slots abc
    [ "$status" -ne 0 ]
    [[ "$output" == *"positive integer"* ]]
}

@test "cli: QUEUE_SLOTS must itself be a positive integer" {
    run env QUEUE_SLOTS=0 "$QUEUE" true
    [ "$status" -ne 0 ]
    [[ "$output" == *"positive integer"* ]]
}

@test "cli: --budget is obsolete and fails loudly" {
    # Not a silent no-op and not an alias for --slots: units and jobs are not
    # the same quantity, so a caller has to re-read what they are asking for.
    run "$QUEUE" --budget
    [ "$status" -ne 0 ]
    [[ "$output" == *"obsolete"* ]]
    [[ "$output" == *"--slots"* ]]
}

@test "cli: running with no command is an error, not a hang" {
    run "$QUEUE"
    [ "$status" -ne 0 ]
}

@test "cli: --help works without a running daemon" {
    TS_SOCKET="$QUEUE_SOCKET" ts -K 2>/dev/null || true
    run "$QUEUE" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"USAGE"* ]]
}

@test "cli: --help strips its comment markers" {
    # The handler slices this script's own header comment. With a BRE `\?`
    # (which BSD sed does not have) the substitution silently matched nothing
    # and every help line printed with a leading `# ` still attached.
    run "$QUEUE" --help
    [ "$status" -eq 0 ]
    [[ "$output" != *"# USAGE"* ]]
    [[ "$output" != *"#   queue"* ]]
}

# ── the old name ──────────────────────────────────────────────────────────

@test "gravestone: testq exits 127 and points at queue" {
    # A loud gravestone rather than a symlink: the rename came with a model
    # change, so a caller still typing `testq` holds stale assumptions about
    # what the queue DOES, and forwarding would hide exactly that.
    run "${BATS_TEST_DIRNAME}/../testq" cargo nextest run
    [ "$status" -eq 127 ]
    [[ "$output" == *"queue"* ]]
}

# ── shared helpers for the scheduling / management groups below ───────────
#
# Poll, never sleep-and-hope: how long a submission takes to reach the daemon
# depends on the tree it has to fingerprint, not on us.

# `</dev/null` on every `ts` here, and never a bare `ts -l` once the daemon is
# gone. A task-spooler CLIENT that finds no server FORKS ONE, and the forked
# daemon inherits the caller's descriptors -- which under bats are the runner's
# own pipes. A daemon leaked that way outlives the whole file and holds the pipe
# open, so bats reports every test passing and then never exits. That is exactly
# how it hung here: teardown's `ts -l` ran after `ts -K` had removed the server,
# forked a replacement, and the second `ts -K` raced its startup.

count_in_state() {
    [ -S "$QUEUE_SOCKET" ] || { echo 0; return 0; }
    TS_SOCKET="$QUEUE_SOCKET" ts -l 2>/dev/null </dev/null | tail -n +2 |
        awk -v s="$1" '$2==s {n++} END{print n+0}'
}

ids_in_state_t() {
    [ -S "$QUEUE_SOCKET" ] || return 0
    TS_SOCKET="$QUEUE_SOCKET" ts -l 2>/dev/null </dev/null | tail -n +2 |
        awk -v s="$1" '$2==s {print $1}'
}

wait_for_state() {   # $1 = state, $2 = how many
    local tries=0 n=0
    while (( tries++ < 150 )); do
        n=$(count_in_state "$1")
        if [ "$n" -ge "$2" ]; then return 0; fi
        sleep 0.1
    done
    echo "timed out waiting for $2 job(s) in state $1 (saw $n)" >&2
    TS_SOCKET="$QUEUE_SOCKET" ts -l >&2
    return 1
}

# Tests below pin fixtures behind a long blocker so they never actually run.
# Tear that down in the right order -- drop the QUEUED jobs first, because
# killing the blocker frees the slot and the fixtures would start. Idempotent:
# teardown calls it for every test, and a test may call it earlier to assert on
# what did NOT run.
drain() {
    local id
    if [ -S "$QUEUE_SOCKET" ]; then
        for id in $(ids_in_state_t queued); do
            TS_SOCKET="$QUEUE_SOCKET" ts -r "$id" >/dev/null 2>&1 </dev/null || true
        done
        for id in $(ids_in_state_t running); do
            TS_SOCKET="$QUEUE_SOCKET" ts -k "$id" >/dev/null 2>&1 </dev/null || true
        done
        TS_SOCKET="$QUEUE_SOCKET" ts -K >/dev/null 2>&1 </dev/null || true
    fi
    # The socket file outlives the daemon often enough that leaving it would let
    # the NEXT `ts` here fork a replacement server.
    rm -f "$QUEUE_SOCKET" 2>/dev/null || true
    wait 2>/dev/null || true
}

distinct_history_keys() {
    awk -F'\t' 'NF>1 {print $1}' "$QUEUE_STATE/history.tsv" | sort -u | wc -l | tr -d ' '
}

# ── duration history is keyed on the REPO, not the submitter's cwd ────────

setup_worktree_repo() {
    # The shape this exists for: one repo, one ephemeral per-issue worktree.
    MAIN="${BATS_TEST_TMPDIR}/main"
    git init -q "$MAIN"
    cd "$MAIN"
    echo one >file.txt
    git add -A
    git -c user.email=t@t -c user.name=t commit -qm init
    WT="${BATS_TEST_TMPDIR}/wt"
    git -c user.email=t@t -c user.name=t worktree add -q -b wt "$WT" >/dev/null 2>&1
}

@test "history key: two worktrees of one repo share one duration key" {
    # Worktrees here are created and destroyed per issue. Keying on the cwd
    # gave every fresh one an empty history, which blanks the heartbeat ETA and
    # starves the shortest-job promotion of the very numbers it decides on.
    export QUEUE_NO_DEDUP=1
    setup_worktree_repo
    cd "$MAIN"; "$QUEUE" true
    cd "$WT";   "$QUEUE" true
    [ "$(distinct_history_keys)" = "1" ]
}

@test "history key: a cd-chain keys the same as running in place" {
    # `queue 'cd /worktree && just ci-fast'` is the supported answer to the
    # `&&` trap, so it is the COMMON shape -- and it used to key on wherever
    # the submitting agent happened to be sitting.
    export QUEUE_NO_DEDUP=1
    setup_worktree_repo
    cd "$MAIN"
    "$QUEUE" sleep 0
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" "cd $MAIN && sleep 0"
    [ "$(distinct_history_keys)" = "1" ]
}

@test "history key: different repos never share a key" {
    export QUEUE_NO_DEDUP=1
    local d
    for d in r1 r2; do
        git init -q "${BATS_TEST_TMPDIR}/$d"
        cd "${BATS_TEST_TMPDIR}/$d"
        echo x >f
        git add -A
        git -c user.email=t@t -c user.name=t commit -qm init
        "$QUEUE" true
    done
    [ "$(distinct_history_keys)" = "2" ]
}

# ── shortest-job-first promotion ──────────────────────────────────────────
#
# The promotion reads MEASURED durations, so every fixture below first RUNS
# each command once to give it a history. Jobs live in two directories on
# purpose: the blocker must not hold the promoted job's target dir, or the
# anti-affinity guard (correctly) refuses to promote.

@test "quick: a job with a short history jumps a queued long one" {
    local A="${BATS_TEST_TMPDIR}/a" B="${BATS_TEST_TMPDIR}/b"
    mkdir -p "$A" "$B"
    local slow="echo slow >>$TRACE; sleep 3"
    local fast="echo fast >>$TRACE"

    cd "$A"
    "$QUEUE" sh -c "$slow" >/dev/null
    "$QUEUE" sh -c "$fast" >/dev/null
    : >"$TRACE"

    cd "$B"
    "$QUEUE" sh -c "sleep 6" >/dev/null 2>&1 &
    wait_for_state running 1

    cd "$A"
    "$QUEUE" sh -c "$slow" >/dev/null 2>&1 &
    wait_for_state queued 1
    # Let the long job take its own one-shot promotion first. Every rule here
    # fires at most once per job and the LAST `ts -u` wins, so without this the
    # test would be measuring which supervisor woke up first.
    sleep 1
    "$QUEUE" sh -c "$fast" >/dev/null 2>&1 &
    wait_for_state queued 2
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == "fast"*"slow"* ]]
}

@test "quick: a job with no history never jumps" {
    # An unseen command is probably a suite. Guessing otherwise would let the
    # promotion do exactly what the deleted weight classifier did.
    local A="${BATS_TEST_TMPDIR}/a" B="${BATS_TEST_TMPDIR}/b"
    mkdir -p "$A" "$B"
    local slow="echo slow >>$TRACE; sleep 3"

    cd "$A"
    "$QUEUE" sh -c "$slow" >/dev/null
    : >"$TRACE"

    cd "$B"
    "$QUEUE" sh -c "sleep 6" >/dev/null 2>&1 &
    wait_for_state running 1

    cd "$A"
    "$QUEUE" sh -c "$slow" >/dev/null 2>&1 &
    wait_for_state queued 1
    sleep 1
    "$QUEUE" sh -c "echo novel >>$TRACE" >/dev/null 2>&1 &
    wait_for_state queued 2
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == "slow"*"novel"* ]]
}

@test "quick: no jump when the job ahead is quick too" {
    # The ratio is the whole point: jumping a job that is barely longer than
    # you buys nothing and costs it its place.
    local A="${BATS_TEST_TMPDIR}/a" B="${BATS_TEST_TMPDIR}/b"
    mkdir -p "$A" "$B"
    local one="echo one >>$TRACE; sleep 1"
    local two="echo two >>$TRACE; sleep 1"

    cd "$A"
    "$QUEUE" sh -c "$one" >/dev/null
    "$QUEUE" sh -c "$two" >/dev/null
    : >"$TRACE"

    cd "$B"
    "$QUEUE" sh -c "sleep 6" >/dev/null 2>&1 &
    wait_for_state running 1

    cd "$A"
    "$QUEUE" sh -c "$one" >/dev/null 2>&1 &
    wait_for_state queued 1
    sleep 1
    "$QUEUE" sh -c "$two" >/dev/null 2>&1 &
    wait_for_state queued 2
    wait 2>/dev/null || true

    run cat "$TRACE"
    [[ "$output" == "one"*"two"* ]]
}

# ── --cancel ──────────────────────────────────────────────────────────────
#
# The incident: agents reach for a bare `ts -r <id>`, which talks to
# task-spooler's DEFAULT socket rather than the queue's, so the removal is
# addressed to a daemon that has never heard of the job and fails with "The job
# cannot be removed" -- which reads as a stuck job, not a misaddressed one.

@test "cancel: removes a queued job" {
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" sh -c "sleep 20" >/dev/null 2>&1 &
    wait_for_state running 1
    "$QUEUE" sh -c "echo victim >>$TRACE" >/dev/null 2>&1 &
    wait_for_state queued 1
    local id
    id=$(ids_in_state_t queued | head -1)

    run "$QUEUE" --cancel "$id"
    [ "$status" -eq 0 ]
    [[ "$output" == *"cancelled"* ]]
    [[ "$output" == *"$id"* ]]

    [ "$(count_in_state queued)" = "0" ]
    drain
    run grep -c victim "$TRACE" 2>/dev/null || true
    [ "${output:-0}" = "0" ]
}

@test "cancel: refuses a running job and names the kill command instead" {
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" sh -c "sleep 20" >/dev/null 2>&1 &
    wait_for_state running 1
    local id
    id=$(ids_in_state_t running | head -1)

    run "$QUEUE" --cancel "$id"
    [ "$status" -ne 0 ]
    [[ "$output" == *"ts -k"* ]]
    [ "$(count_in_state running)" = "1" ]
    drain
}

@test "cancel: an unknown job id is a loud error, not a no-op" {
    run "$QUEUE" --cancel 99999
    [ "$status" -ne 0 ]
    [[ "$output" == *"not queued"* ]]
}

@test "cancel: with no reference at all is an error" {
    run "$QUEUE" --cancel
    [ "$status" -ne 0 ]
}

# ── --triage ──────────────────────────────────────────────────────────────

@test "triage: flags a duplicate pair and suggests cancelling the later one" {
    cd "$BATS_TEST_TMPDIR"
    export QUEUE_NO_DEDUP=1
    "$QUEUE" sh -c "sleep 20" >/dev/null 2>&1 &
    wait_for_state running 1
    "$QUEUE" sh -c "sleep 5" >/dev/null 2>&1 &
    "$QUEUE" sh -c "sleep 5" >/dev/null 2>&1 &
    wait_for_state queued 2

    run "$QUEUE" --triage
    [ "$status" -eq 0 ]
    [[ "$output" == *"duplicate"* ]]
    [[ "$output" == *"--cancel"* ]]
    # REPORT ONLY: nothing was removed.
    [ "$(count_in_state queued)" = "2" ]
    drain
}

@test "triage: flags a queued job that needn't be queued at all" {
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" sh -c "sleep 20" >/dev/null 2>&1 &
    wait_for_state running 1
    "$QUEUE" cargo clippy --version >/dev/null 2>&1 &
    wait_for_state queued 1

    run "$QUEUE" --triage
    [ "$status" -eq 0 ]
    [[ "$output" == *"unqueued"* ]]
    [[ "$output" == *"clippy"* ]]
    drain
}

@test "triage: an env-assignment prefix does not hide a clippy run" {
    cd "$BATS_TEST_TMPDIR"
    "$QUEUE" sh -c "sleep 20" >/dev/null 2>&1 &
    wait_for_state running 1
    "$QUEUE" "RUSTFLAGS=-Awarnings cargo check --workspace" >/dev/null 2>&1 &
    wait_for_state queued 1

    run "$QUEUE" --triage
    [ "$status" -eq 0 ]
    [[ "$output" == *"unqueued"* ]]
    drain
}

@test "triage: a clean queue says so explicitly" {
    # Honest empty state: silence would be indistinguishable from a triage that
    # failed to read the queue at all.
    run "$QUEUE" --triage
    [ "$status" -eq 0 ]
    [[ "$output" == *"nothing to flag"* ]]
}

@test "cli: --help lists the cancel and triage flags" {
    run "$QUEUE" --help
    [ "$status" -eq 0 ]
    [[ "$output" == *"--cancel"* ]]
    [[ "$output" == *"--triage"* ]]
}
