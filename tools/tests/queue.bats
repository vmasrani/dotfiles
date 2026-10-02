#!/usr/bin/env bats
# Behaviour tests for `queue`, the flock slot gate (tools/queue, Python).
#
# Hermetic: every test gets private QUEUE_DIR / QUEUE_STATE_DIR under a
# per-test temp dir, so the live /tmp/queue-$UID gate is never touched.
# Jobs are sleep/echo stand-ins; timing margins are generous (>= 0.5 s).
#
#   Run:  bats tools/tests/queue.bats

setup() {
    QUEUE="${QUEUE_BIN:-${BATS_TEST_DIRNAME}/../queue}"
    [ -x "$QUEUE" ] || { echo "queue not executable at $QUEUE" >&2; return 1; }
    # BATS_TEST_TMPDIR needs bats >= 1.4; Ubuntu 22.04 ships 1.2.1.
    T="${BATS_TEST_TMPDIR:-$(mktemp -d)}"
    export QUEUE_DIR="$T/q"
    export QUEUE_STATE_DIR="$T/state"
    export QUEUE_QUIET=1
    export QUEUE_POLL=0.05
    export QUEUE_SLOTS=1
    unset QUEUE_ACTIVE QUEUE_SESSION
    D="$T/w"
    mkdir -p "$D"
}

teardown() {
    # reap anything a test left running (queue processes and leaked sleepers)
    local p
    for p in $(jobs -p) $(cat "$D"/*.pid 2>/dev/null); do kill -9 "$p" 2>/dev/null || true; done
    [ -n "${BATS_TEST_TMPDIR:-}" ] || rm -rf "$T"
    return 0
}

@test "job's exact exit code is returned" {
    run "$QUEUE" sh -c 'exit 7'
    [ "$status" -eq 7 ]
}

@test "stdout and stderr pass through separately" {
    "$QUEUE" sh -c 'echo OUT; echo ERR >&2' >"$D/out" 2>"$D/err"
    [ "$(cat "$D/out")" = "OUT" ]
    [ "$(cat "$D/err")" = "ERR" ]
}

@test "stdout is live, not held until the job ends" {
    "$QUEUE" sh -c 'echo first; sleep 2; echo second' >"$D/out" &
    sleep 1
    [ "$(cat "$D/out")" = "first" ]
    wait
}

@test "cwd and environment reach the job; a single string runs via zsh -c" {
    mkdir -p "$D/sub"
    cd "$D/sub"
    run env FOO=bar "$QUEUE" sh -c 'pwd -P; echo $FOO'
    [ "${lines[0]}" = "$(pwd -P)" ]
    [ "${lines[1]}" = "bar" ]
    run "$QUEUE" 'cd / && pwd'
    [ "$output" = "/" ]
}

@test "N slots admit exactly N concurrent jobs; the N+1th waits" {
    "$QUEUE" --slots 2 >/dev/null
    for i in 1 2 3; do
        "$QUEUE" sh -c "echo $i >> '$D/started'; sleep 2" &
    done
    sleep 1
    [ "$(wc -l <"$D/started")" -eq 2 ]
    wait
    [ "$(wc -l <"$D/started")" -eq 3 ]
}

@test "--solo waits for running jobs and holds back new ones while it runs" {
    "$QUEUE" --slots 2 >/dev/null
    "$QUEUE" sh -c "echo A-start >> '$D/log'; sleep 1.5; echo A-end >> '$D/log'" &
    sleep 0.5
    "$QUEUE" --solo sh -c "echo S-start >> '$D/log'; sleep 1; echo S-end >> '$D/log'" &
    sleep 0.5
    "$QUEUE" sh -c "echo C-start >> '$D/log'" &
    wait
    [ "$(tr '\n' ' ' <"$D/log")" = "A-start A-end S-start S-end C-start " ]
}

@test "a background process left by a job does not keep its slot" {
    "$QUEUE" sh -c "sleep 30 >/dev/null 2>&1 & echo \$! > '$D/leak.pid'"
    "$QUEUE" true &
    sleep 1.5
    ! kill -0 $! 2>/dev/null   # second job already finished
    kill -0 "$(cat "$D/leak.pid")"  # and the leaked sleeper is still alive
    wait
}

@test "kill -9 of a slot holder frees its slot" {
    "$QUEUE" sh -c "echo \$PPID > '$D/holder.pid'; sleep 30" &
    until [ -s "$D/holder.pid" ]; do sleep 0.1; done
    "$QUEUE" true &
    waiter=$!
    sleep 0.5
    kill -0 "$waiter"          # blocked behind the holder
    kill -9 "$(cat "$D/holder.pid")"
    sleep 1
    ! kill -0 "$waiter" 2>/dev/null
}

@test "--exit-code --last reports the last job's rc per QUEUE_SESSION" {
    QUEUE_SESSION=a "$QUEUE" sh -c 'exit 3' || true
    QUEUE_SESSION=b "$QUEUE" sh -c 'exit 5' || true
    run env QUEUE_SESSION=a "$QUEUE" --exit-code --last
    [ "$status" -eq 3 ]
    [ "$output" = "3" ]
    run env QUEUE_SESSION=b "$QUEUE" --exit-code --last
    [ "$status" -eq 5 ]
}

@test "removed flags exit 2 with a message" {
    for f in --cancel --triage --ahead --depth --budget -C; do
        run "$QUEUE" "$f"
        [ "$status" -eq 2 ]
        [[ "$output" == *"removed"* ]]
    done
}

@test "QUEUE_ACTIVE runs the command directly without taking a slot" {
    "$QUEUE" sh -c "echo \$PPID > '$D/holder.pid'; sleep 30" &
    until [ -s "$D/holder.pid" ]; do sleep 0.1; done
    run env QUEUE_ACTIVE=1 "$QUEUE" sh -c 'echo direct'
    [ "$status" -eq 0 ]
    [ "$output" = "direct" ]
}

@test "a command with 3 quick runs goes express and is not blocked by a running main job" {
    for i in 1 2 3; do "$QUEUE" echo fast >/dev/null; done
    "$QUEUE" sh -c "echo \$PPID > '$D/holder.pid'; sleep 4" &
    until [ -s "$D/holder.pid" ]; do sleep 0.1; done
    run timeout 3 "$QUEUE" echo fast
    [ "$status" -eq 0 ]
    grep -q '^lane=express' "$QUEUE_STATE_DIR"/last/*
}

@test "a command with no quick history stays in the main lane and waits" {
    "$QUEUE" sh -c "echo \$PPID > '$D/holder.pid'; sleep 3" &
    until [ -s "$D/holder.pid" ]; do sleep 0.1; done
    run timeout 1 "$QUEUE" echo fresh
    [ "$status" -ne 0 ]
}

@test "--solo blocks the express lane while it runs" {
    for i in 1 2 3; do "$QUEUE" echo fast >/dev/null; done
    "$QUEUE" --solo sh -c "echo \$PPID > '$D/holder.pid'; sleep 3" &
    until [ -s "$D/holder.pid" ]; do sleep 0.1; done
    run timeout 1 "$QUEUE" echo fast
    [ "$status" -ne 0 ]
}

@test "a job killed by a signal returns 128+signal" {
    run "$QUEUE" sh -c 'kill -TERM $$'
    [ "$status" -eq 143 ]
    run "$QUEUE" sh -c 'kill -KILL $$'
    [ "$status" -eq 137 ]
}

@test "-l drops wait files of dead pids and keeps live ones" {
    "$QUEUE" true
    sleep 30 & live=$!
    echo "pid=999999 dead" > "$QUEUE_DIR/wait.999999"
    echo "pid=$live live" > "$QUEUE_DIR/wait.$live"
    run "$QUEUE" -l
    [ ! -e "$QUEUE_DIR/wait.999999" ]
    [ -e "$QUEUE_DIR/wait.$live" ]
    [[ "$output" == *"waiting: 1"* ]]
}
