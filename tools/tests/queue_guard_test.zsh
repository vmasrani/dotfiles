#!/usr/bin/env zsh
# Self-test for queue's hang guard (state_of_id / guard_follow / hung_exit_code).
# No real queue daemon: `ts` is a stub on PATH, driven by env vars. Each case
# runs in its own process under a hard 10 s timeout; every verdict is recorded,
# then the run asserts once.
#
#   zsh ~/dotfiles/tools/tests/queue_guard_test.zsh

emulate -L zsh
setopt no_monitor

readonly QUEUE_SCRIPT="${0:A:h:h}/queue"
readonly CASE_TIMEOUT=10

# Source only the introspection + guard section of the script: from the query
# timeout up to the end of hung_exit_code.
load_guard() {
  local src
  src=$(awk '
    /^readonly TS_QUERY_TIMEOUT=/ {on=1}
    on {print}
    on && /^hung_exit_code\(\) *\{/ {last=1}
    last && /^\}/ {exit}
  ' "$QUEUE_SCRIPT")
  [[ "$src" == *"hung_exit_code()"* ]] \
    || { print -u2 "could not extract the guard section from $QUEUE_SCRIPT"; exit 2 }
  # `readonly` inside a function is local in zsh; make the constants global.
  eval "${src//readonly /typeset -gr }"
}

# A stub `ts`: STUB_TS_RC is `ts -s`'s exit code, STUB_TS_STATE its output,
# STUB_TS_SLEEP makes it hang. `ts -l` prints only the header (no jobs, so no
# E-Level), matching a daemon whose job list was cleared.
make_stub() {
  local dir="$1"
  mkdir -p "$dir/bin"
  cat >"$dir/bin/ts" <<'EOF'
#!/usr/bin/env zsh
case "$1" in
  -s) (( ${STUB_TS_SLEEP:-0} > 0 )) && sleep "$STUB_TS_SLEEP"
      [[ -n "$STUB_TS_STATE" ]] && print -r -- "$STUB_TS_STATE"
      exit ${STUB_TS_RC:-0} ;;
  -l) print "ID   State      Output               E-Level  Time   Command"; exit 0 ;;
esac
exit 0
EOF
  chmod +x "$dir/bin/ts"
}

setup() {
  T=$(mktemp -d)
  make_stub "$T"
  path=("$T/bin" $path)
  SELF=queue
  RECORD="$T/record"
  print "id=215" >"$RECORD"
  rec_get() { awk -F= -v k="$2" '$1==k {print substr($0, length(k)+2); f=1} END{exit !f}' "$1" }
  load_guard
}

# (a) rc 0 -> state, rc 124 (query timed out) -> "", other nonzero -> gone.
case_state_mapping() {
  local got
  got=$(STUB_TS_RC=0 STUB_TS_STATE=running state_of_id 215)
  [[ "$got" == running ]] || { print "rc 0: want 'running', got '$got'"; return 1 }
  got=$(STUB_TS_RC=255 state_of_id 215)
  [[ "$got" == gone ]] || { print "rc 255: want 'gone', got '$got'"; return 1 }
  got=$(STUB_TS_RC=1 state_of_id 215)
  [[ "$got" == gone ]] || { print "rc 1: want 'gone', got '$got'"; return 1 }
  got=$(STUB_TS_SLEEP=5 state_of_id 215)
  [[ -z "$got" ]] || { print "timeout (124): want '', got '$got'"; return 1 }
  return 0
}

# (b) daemon says gone, .rc says 0, the watched pid (stand-in for a leaked pipe
# holder) never dies: the guard must return within grace + a few seconds, kill
# the holder and the .err tee, and the exit code must come from .rc.
case_gone_with_rc() {
  local holder errtee t0 rc
  export STUB_TS_RC=255
  print 0 >"$T/job.rc"
  sleep 1000 & holder=$!
  sleep 1000 | tee "$T/job.err" >/dev/null &
  errtee=$!
  t0=$SECONDS
  guard_follow "$holder" "" "$T/job.rc" 2>"$T/stderr"
  local took=$(( SECONDS - t0 ))
  local fail=""
  (( took <= FOLLOW_HANG_GRACE + 3 )) || fail+="took ${took}s (grace ${FOLLOW_HANG_GRACE}s); "
  (( HANG_DECLARED )) || fail+="HANG_DECLARED not set; "
  sleep 0.2
  kill -0 "$holder" 2>/dev/null && fail+="watched pid still alive; "
  kill -0 "$errtee" 2>/dev/null && fail+=".err tee still alive; "
  rc=$(hung_exit_code 215 2>>"$T/stderr")
  [[ "$rc" == 0 ]] || fail+="exit code: want 0 (from .rc), got '$rc'; "
  rg -q 'job 215 is over.*daemon state: gone.*rc file: 0.*leaked child' "$T/stderr" \
    || fail+="guard message missing/wrong: $(<"$T/stderr"); "
  pkill -P $$ sleep 2>/dev/null
  [[ -z "$fail" ]] || { print -r -- "$fail"; return 1 }
}

# (c) gone and an empty .rc (no E-Level either): exit code must be nonzero with
# a message saying the result is lost.
case_gone_without_rc() {
  local holder rc
  export STUB_TS_RC=255
  : >"$T/job.rc"
  sleep 1000 & holder=$!
  guard_follow "$holder" "" "$T/job.rc" 2>"$T/stderr"
  rc=$(hung_exit_code 215 2>>"$T/stderr")
  local fail=""
  (( HANG_DECLARED )) || fail+="HANG_DECLARED not set; "
  [[ -n "$rc" && "$rc" != 0 ]] || fail+="exit code: want nonzero, got '$rc'; "
  rg -q 'job 215 ended \(daemon state: gone\) with no exit code on record.*LOST' "$T/stderr" \
    || fail+="lost-result message missing: $(<"$T/stderr"); "
  kill -9 "$holder" 2>/dev/null
  [[ -z "$fail" ]] || { print -r -- "$fail"; return 1 }
}

# A job that is genuinely still running must NOT be reaped.
case_running_not_reaped() {
  local holder
  export STUB_TS_RC=0 STUB_TS_STATE=running
  : >"$T/job.rc"
  sleep 4 & holder=$!
  guard_follow "$holder" "" "$T/job.rc" 2>"$T/stderr"
  (( HANG_DECLARED )) && { print "running job was reaped: $(<"$T/stderr")"; return 1 }
  return 0
}

run_case() {
  export QUEUE_FOLLOW_HANG_GRACE=2 QUEUE_QUERY_TIMEOUT=1
  setup
  "$1"; local rc=$?
  rm -rf "$T"
  return $rc
}

if [[ "$1" == --case ]]; then
  run_case "$2"
  exit $?
fi

cases=(case_state_mapping case_gone_with_rc case_gone_without_rc case_running_not_reaped)
failed=()
for c in $cases; do
  t0=$SECONDS
  out=$(timeout -k 1 "$CASE_TIMEOUT" zsh "$0" --case "$c" 2>&1)
  rc=$?
  (( rc == 124 || rc == 137 )) && out="TIMED OUT after ${CASE_TIMEOUT}s"
  if (( rc == 0 )); then
    print "PASS $c ($(( SECONDS - t0 ))s)"
  else
    print "FAIL $c ($(( SECONDS - t0 ))s): $out"
    failed+=("$c")
  fi
done
print "${#cases} cases, $(( ${#cases} - ${#failed} )) passed, ${#failed} failed"
(( ${#failed} == 0 ))
