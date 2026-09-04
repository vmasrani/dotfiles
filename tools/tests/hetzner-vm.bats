#!/usr/bin/env bats
# Behaviour tests for `hetzner-vm`, the on-demand Hetzner Cloud worker box tool.
#
# HERMETIC BY CONSTRUCTION
#   A fake `hcloud` is placed first on PATH; it records every invocation to
#   $HCLOUD_TRACE and answers only the read-only queries these tests exercise
#   with canned JSON. Nothing here touches the network, a real Hetzner project,
#   or the live `parot` servers. NO_GUM=1 forces plain-text output so assertions
#   match on stable strings. HETZNER_VM_MANIFEST_DIR relocates manifests into
#   BATS_TEST_TMPDIR so the suite never reads or writes ~/.hetzner-vm.
#
#   Run:  bats tools/tests/hetzner-vm.bats

setup() {
    HETZNER="${BATS_TEST_DIRNAME}/../hetzner-vm"
    [ -x "$HETZNER" ] || {
        echo "hetzner-vm not executable at $HETZNER" >&2
        return 1
    }

    BIN="${BATS_TEST_TMPDIR}/bin"
    mkdir -p "$BIN"
    export HCLOUD_TRACE="${BATS_TEST_TMPDIR}/hcloud-trace"
    export HCLOUD_MODE="empty"   # fake hcloud reads this to shape server-list output
    : >"$HCLOUD_TRACE"
    write_fake_hcloud
    export PATH="$BIN:$PATH"

    # Manifests live in the test tmpdir, never in $HOME.
    export HETZNER_VM_MANIFEST_DIR="${BATS_TEST_TMPDIR}/manifests"
    mkdir -p "$HETZNER_VM_MANIFEST_DIR"

    # Plain-text output; a token so ensure_hcloud passes.
    export NO_GUM=1
    export HCLOUD_TOKEN="fake-token"
}

# ── fakes ─────────────────────────────────────────────────────────────────
# Records argv, then answers the read-only queries the tool makes. `server list`
# returns [] by default (HCLOUD_MODE=empty) so no managed server appears. Any
# unrecognised subcommand exits 0 so a test failure reads as a wrong assertion
# rather than a crash inside the fake.
write_fake_hcloud() {
    cat >"$BIN/hcloud" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$HCLOUD_TRACE"
case "$1 $2" in
    "server list")
        if [ "${HCLOUD_MODE:-empty}" = "running" ]; then
            cat <<'JSON'
[{"name":"box1","status":"running","server_type":{"name":"ccx53"},
  "datacenter":{"location":{"name":"nbg1"}},
  "public_net":{"ipv4":{"ip":"5.6.7.8"}},"volumes":[]}]
JSON
        else
            echo '[]'
        fi
        ;;
    "image describe")
        # $3 is the image id; report available for the fixture snapshot 999.
        echo '{"id":999,"status":"available","image_size":50,"description":"box1-snap"}'
        ;;
    "server-type describe")
        echo '{"prices":[{"location":"nbg1","price_hourly":{"net":"1.0088000000"},"price_monthly":{"net":"629.4900000000"}}]}'
        ;;
    *) : ;;
esac
exit 0
EOF
    chmod +x "$BIN/hcloud"
}

# Write a fixture manifest for a given vm name. $2 = snapshot id (empty = none).
write_manifest() {
    local name="$1" snap="$2" size="${3:-50}"
    if [ -n "$snap" ]; then
        cat >"${HETZNER_VM_MANIFEST_DIR}/${name}.json" <<EOF
{"name":"$name","type":"ccx53","location":"nbg1","image":"ubuntu-24.04",
 "sshKey":"vmasrani (macmini)","firewall":"hetzner-vm-fw","ipv4":"5.6.7.8",
 "created":"2026-01-01T00:00:00Z","volumes":[],
 "archive":{"snapshotId":$snap,"snapshotDescription":"${name}-snap","imageSizeGb":$size}}
EOF
    else
        cat >"${HETZNER_VM_MANIFEST_DIR}/${name}.json" <<EOF
{"name":"$name","type":"ccx53","location":"nbg1","image":"ubuntu-24.04",
 "sshKey":"vmasrani (macmini)","firewall":"hetzner-vm-fw","ipv4":"5.6.7.8",
 "created":"2026-01-01T00:00:00Z","volumes":[]}
EOF
    fi
}

# ── usage / argument errors ───────────────────────────────────────────────

@test "usage: no args exits 1 with usage" {
    run "$HETZNER"
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage: hetzner-vm"* ]]
}

@test "usage: command without a name exits 1" {
    run "$HETZNER" status
    [ "$status" -eq 1 ]
    [[ "$output" == *"Usage: hetzner-vm"* ]]
}

@test "usage: unknown command exits 1" {
    run "$HETZNER" frobnicate box1
    [ "$status" -eq 1 ]
    [[ "$output" == *"Unknown command"* ]]
}

# ── missing token ─────────────────────────────────────────────────────────

@test "token: missing HCLOUD_TOKEN fails loud and names the env file" {
    unset HCLOUD_TOKEN
    run "$HETZNER" status box1
    [ "$status" -eq 1 ]
    [[ "$output" == *"HCLOUD_TOKEN"* ]]
    [[ "$output" == *".local_env.sh"* ]]
}

# ── verify ────────────────────────────────────────────────────────────────

@test "verify: passes when manifest has an available snapshot" {
    write_manifest box1 999
    run "$HETZNER" verify box1
    [ "$status" -eq 0 ]
    [[ "$output" == *"Archive verification PASSED"* ]]
}

@test "verify: fails when no manifest exists" {
    run "$HETZNER" verify ghost
    [ "$status" -eq 1 ]
    [[ "$output" == *"No manifest found"* ]]
}

@test "verify: fails when manifest has no snapshot id" {
    write_manifest box1 ""
    run "$HETZNER" verify box1
    [ "$status" -eq 1 ]
    [[ "$output" == *"no archive.snapshotId"* ]]
}

# ── status ────────────────────────────────────────────────────────────────

@test "status: archived box shows snapshot cost from the constant" {
    # 100 GB x 0.0119 EUR/GB/month = 1.19 exactly (no rounding ambiguity).
    write_manifest box1 999 100
    run "$HETZNER" status box1
    [ "$status" -eq 0 ]
    [[ "$output" == *"Archived"* ]]
    [[ "$output" == *"EUR 1.19/month"* ]]
    [[ "$output" == *"100 GB"* ]]
}

@test "status: neither server nor manifest fails loud" {
    run "$HETZNER" status ghost
    [ "$status" -eq 1 ]
    [[ "$output" == *"Nothing exists under this name"* ]]
}

@test "status: running server shows the live API price" {
    export HCLOUD_MODE="running"
    run "$HETZNER" status box1
    [ "$status" -eq 0 ]
    [[ "$output" == *"Running"* ]]
    [[ "$output" == *"EUR 1.0088/hour"* ]]
    [[ "$output" == *"629.49/month"* ]]
}

# ── create refusal ────────────────────────────────────────────────────────

@test "create: refuses when a manifest already exists" {
    write_manifest box1 999
    run "$HETZNER" create box1
    [ "$status" -eq 1 ]
    [[ "$output" == *"manifest already exists"* ]]
    [[ "$output" == *"restore"* ]]
    # It must NOT have attempted to create a server.
    ! grep -q "server create" "$HCLOUD_TRACE"
}
