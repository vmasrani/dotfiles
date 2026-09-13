#!/usr/bin/env bats
# Hermetic preflight coverage for setup-omp. The explicit identity stop seam ends
# before downloads, services, or builds; PATH fakes and HOME keep every test local.

setup() {
    SETUP_OMP="${BATS_TEST_DIRNAME}/../setup-omp"
    [ -x "$SETUP_OMP" ] || {
        echo "setup-omp not executable at $SETUP_OMP" >&2
        return 1
    }
    export HOME="${BATS_TEST_TMPDIR}/home"
    export PATH="${BATS_TEST_TMPDIR}/bin:$PATH"
    mkdir -p "$HOME" "${BATS_TEST_TMPDIR}/bin"
    export TAILSCALE_JSON='{"BackendState":"Running","TUN":true,"Self":{"DNSName":"vadens-mac-mini.tail3b5dad.ts.net.","UserID":42},"User":{"42":{"LoginName":"vmasrani@sophiaconsulting.ai"}}}'
    export FAKE_SYSTEM="Darwin"
    export FAKE_ARCH="arm64"
    write_fake_uname
    write_fake_tailscale
}

write_fake_uname() {
    cat >"${BATS_TEST_TMPDIR}/bin/uname" <<'EOF'
#!/usr/bin/env bash
case "$1" in
  -s) printf '%s\n' "$FAKE_SYSTEM" ;;
  -m) printf '%s\n' "$FAKE_ARCH" ;;
  *) exit 64 ;;
esac
EOF
    chmod +x "${BATS_TEST_TMPDIR}/bin/uname"
}

write_fake_tailscale() {
    cat >"${BATS_TEST_TMPDIR}/bin/tailscale" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"${BATS_TEST_TMPDIR}/tailscale-trace"
if [[ "$1 $2 $3" == "status --json " ]]; then
  printf '%s\n' "$TAILSCALE_JSON"
  exit 0
fi
exit 64
EOF
    chmod +x "${BATS_TEST_TMPDIR}/bin/tailscale"
}

@test "derives MagicDNS origin and owning Tailscale login without arguments" {
    run env SETUP_OMP_TEST_STOP_AFTER=identity "$SETUP_OMP"
    [ "$status" -eq 0 ]
    [[ "$output" == *"origin=https://vadens-mac-mini.tail3b5dad.ts.net"* ]]
    [[ "$output" == *"allow=vmasrani@sophiaconsulting.ai"* ]]
}

@test "rejects an unsupported platform before consulting Tailscale" {
    export FAKE_SYSTEM="Linux"
    export FAKE_ARCH="s390x"
    run "$SETUP_OMP"
    [ "$status" -ne 0 ]
    [[ "$output" == *"unsupported host Linux-s390x"* ]]
    [ ! -e "${BATS_TEST_TMPDIR}/tailscale-trace" ]
}

@test "refuses a logged-in userspace Tailscale client" {
    export TAILSCALE_JSON='{"BackendState":"Running","TUN":false,"Self":{"DNSName":"host.tail.ts.net.","UserID":1},"User":{"1":{"LoginName":"person@example.com"}}}'
    run env SETUP_OMP_TEST_STOP_AFTER=identity "$SETUP_OMP"
    [ "$status" -ne 0 ]
    [[ "$output" == *"running in TUN mode"* ]]
}

@test "refuses an unverified retained Bun artifact before any download" {
    mkdir -p "${HOME}/.cache/omp-session-gateway/bun/1.4.0"
    printf 'not the pinned archive\n' >"${HOME}/.cache/omp-session-gateway/bun/1.4.0/bun-darwin-aarch64.zip"
    run "$SETUP_OMP"
    [ "$status" -ne 0 ]
    [[ "$output" == *"checksum refusal"* ]]
    [[ "$output" == *"bun-darwin-aarch64.zip"* ]]
}

@test "identity preflight is safely rerunnable without mutating state" {
    run env SETUP_OMP_TEST_STOP_AFTER=identity "$SETUP_OMP"
    [ "$status" -eq 0 ]
    first="$output"
    run env SETUP_OMP_TEST_STOP_AFTER=identity "$SETUP_OMP"
    [ "$status" -eq 0 ]
    [ "$output" = "$first" ]
    [ ! -d "${HOME}/.local/lib/omp-session-gateway" ]
}

@test "extracts the release top-level directory and detects retained payload changes" {
    local fixture_root fixture_archive target
    SETUP_OMP_LIB_ONLY=1 source "$SETUP_OMP"
    fixture_root="${BATS_TEST_TMPDIR}/fixture/omp-session-gateway-${GATEWAY_VERSION}-bun"
    fixture_archive="${BATS_TEST_TMPDIR}/gateway.tar"
    target="${HOME}/gateway"
    mkdir -p "${fixture_root}/apps/gateway/src" "${fixture_root}/apps/gateway/dist"
    printf 'cli\n' >"${fixture_root}/apps/gateway/src/cli.js"
    printf 'static\n' >"${fixture_root}/apps/gateway/dist/index.html"
    (cd "${BATS_TEST_TMPDIR}/fixture" && tar -cf "$fixture_archive" "omp-session-gateway-${GATEWAY_VERSION}-bun")

    extract_gateway_archive "$fixture_archive" "$target"
    [ -f "${target}/apps/gateway/src/cli.js" ]
    [ -f "${target}/gateway.payload.sha256" ]

    printf 'modified static payload\n' >"${target}/apps/gateway/dist/index.html"
    if (verify_gateway_source "$target"); then
        false
    fi
}
