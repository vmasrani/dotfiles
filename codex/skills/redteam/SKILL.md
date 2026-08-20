---
name: redteam
description: Black-box fuzz / red-team a CLI binary or API surface using only its public --help output (never source code). Use when the user says "redteam", "fuzz this CLI", "try to break my binary", "adversarial test", "find bugs in the API surface", "pretend you're a hostile user", or asks for a black-box test pass against a tool they just built. Produces a triaged findings report with severity, repro steps, and recommended fixes.
---

# redteam — Black-box CLI / API fuzz pass

Hammer a CLI binary (or any tool with a documented surface) from the outside. Pretend to be a hostile but non-malicious user who has only `--help` to go on. The goal is to surface panics, bad UX, undocumented behavior, and mutual-exclusivity gaps before real users find them.

The output is a single triaged report at `./REDTEAM_REPORT.md` plus an inline summary in chat.

## Ground rules

1. **Never read the source.** No `Read`/`grep`/`fd` over the project's source tree. The whole point is a black-box pass — if you peek, you bias toward the implementer's mental model. `--help` is the spec.
2. **Small inputs only.** Every test input is < 1 MB unless you're explicitly testing large-input behavior (and even then, cap at ~10 MB).
3. **Non-destructive.** No `rm` outside the scratch tmpdir. No `kill -9` of arbitrary PIDs (only daemons the target binary itself spawned, and only if you started them this run). No network egress beyond what the binary itself does. No mutation of the project tree (no `cargo build`, `npm install`, `git ...`).
4. **Scratch dir is mandatory.** All inputs live in `/tmp/redteam-<bin>/`. If creating that fails, stop and ask.
5. **Capture verbatim.** Record exit code, full stderr, full stdout (or first 200 lines if huge). Don't paraphrase error messages — quote them.
6. **Stop and report if the binary isn't built.** Don't try to build it. Ask the user.

## Phase 1 — Surface discovery

Run, in this order:

```bash
<bin> --help
<bin> --version
<bin> help                # some tools support this, some don't — try both
```

Then for every subcommand listed, run `<bin> <subcmd> --help`. Prefer parallel `Bash` calls — these are sub-second.

Build a **surface inventory table** in working memory:

| subcommand | positional args | flags | numeric/enum ranges | mutual-exclusivity | file inputs |
|---|---|---|---|---|---|

Note any documented constraints verbatim ("clamped to 64 MiB–1 GiB", "X is mutually exclusive with Y", "must be ≥ 1"). These become test cases later.

## Phase 2 — Build the input zoo

In `/tmp/redteam-<bin>/`, create a standard battery of tiny inputs. The exact set:

| filename | content |
|---|---|
| `empty.txt` | 0 bytes |
| `one_byte.txt` | single `a` |
| `one_line.txt` | `hello\n` |
| `crlf.txt` | mixed `\r\n` line endings |
| `lf.txt` | pure `\n` line endings |
| `bom.txt` | UTF-8 BOM (`\xef\xbb\xbf`) followed by a line |
| `nul.txt` | text with embedded `\0` byte |
| `unicode.txt` | emoji, RTL Arabic, combining marks |
| `huge_line.txt` | 1 line of 1 MB |
| `binary.bin` | 1 KB of `/dev/urandom` |
| `weird name with spaces & $hell.txt` | normal text, weird filename |
| `link.txt` | symlink to `one_line.txt` |
| `a_dir/` | a directory (passed where a file is expected) |
| `noperm.txt` | chmod 000 |

Plus 1–2 **format-specific** inputs depending on what the tool consumes (CSV, JSON, markdown, etc.). Keep them tiny (< 10 rows / < 1 KB).

If the tool builds an index or persistent state, build it ONCE on a known-good input and reuse it for read-only fuzz.

## Phase 3 — Fuzz playbook

For each surface category the binary exposes, run the matching checklist. Use parallel `Bash` calls aggressively — most invocations are sub-second. Always wrap in `timeout 5s` if there's any chance of a hang (regex bombs, daemons, large inputs).

### Numeric flags (`--count`, `--top`, `--jobs`, etc.)

- `0`, `1`, `-1`
- very large: `9223372036854775807` (i64 max), `9223372036854775808` (overflow), `2147483648` (i32 boundary)
- float where int expected: `1.5`, `1e10`
- `NaN`, `Inf`, `-Inf`
- scientific notation: `1e3`
- leading zeros: `007`
- hex: `0x10`
- unicode digits: `１` (full-width), `५` (Devanagari)
- empty string: `--top=`

### Size / duration suffixes (`--shard-size 256MiB`, `--timeout 30s`)

- missing unit: `256`
- unknown unit: `256PB`, `256XB`, `256gigs`
- negative: `-1MiB`
- zero: `0B`, `0`
- fractional: `1.5GiB`
- out-of-clamp: above documented max, below documented min, exactly at each boundary

### Path inputs

- nonexistent: `/does/not/exist.txt`
- directory where file expected: `a_dir/`
- symlink loop: `ln -s a a; ln -s a b` (skip if already covered)
- no-read-perm: `noperm.txt`
- weird name: `weird name with spaces & $hell.txt`
- very long path (> 4096 chars)
- `/dev/null`, `/dev/zero` (ALWAYS bound the read with `timeout` or `head`)
- relative `..` traversal: `../../../etc/passwd` (just to confirm clean refusal, NOT to actually exfil)

### Pattern / regex inputs (`-e`, `-p`, `--pattern`)

- empty pattern: `-e ""`
- catastrophic backtracking: `-e '(a+)+$'` against `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa!` (use `timeout 3s`)
- unbalanced: `-e '('`, `-e '['`
- invalid escape: `-e '\q'`
- NUL byte in pattern (use `printf` and a tempfile)
- very long pattern: 1 MB of `a`s
- repeated flag: `-e a -e b -e c ... ×100`, `×1000`
- pattern from file: file is `/dev/null`, file is binary, file is 10 MB

### Boolean / DSL expressions (`-x "a && b"`)

- unbalanced parens: `((a && b)`, `(a) )`
- double operator: `a && && b`, `a || || b`
- leading operator: `&& a`, `|| a`
- trailing operator: `a &&`
- only operators: `&& ||`
- deeply nested: 1000 levels of `((...))`
- reserved chars in identifiers: `a&&b` (no spaces), `&` alone
- empty: `""`
- whitespace-only: `"   "`

### Enum flags (`--color`, `--format`)

- unknown value: `--color purple`
- mixed case: `--color AUTO`
- with whitespace: `--color " auto "`
- empty: `--color=`

### Mutual-exclusivity violations

For each documented "X is mutually exclusive with Y" pair: pass them together. Assert the error is clean and on stderr, not a panic and not silent. Repeat for triples/quads where applicable.

### Argument repetition / missing

- required positional omitted
- positional given twice
- unknown flag: `--definitely-not-a-flag`
- `--` separator: `<bin> sub -- --top 5` (does it treat `--top` as a positional?)
- `--flag=value` vs `--flag value` parity (clap usually handles this, but worth checking)

### Lifecycle / state machines (daemons, indices, sessions)

- action on non-existent target: `<bin> stop` when nothing is running
- double-init: start, then start again
- action while busy
- interleaved ops from two terminals (use `&` and `wait`)
- target deleted under the tool: build index, `rm -rf` it, then query

### Encoding

- UTF-8 BOM at start of input
- invalid UTF-8 byte sequences (`\xc3\x28`)
- UTF-16 input where UTF-8 expected
- NUL bytes mid-stream
- mixed line endings within one file

### Output / format flags

- `--json` combined with every other flag (especially the ones it's documented incompatible with)
- `-q` / `--quiet` combined with `--verbose` / `--timing` / `--debug`
- redirect stdout to `/dev/full` (write fails — does the tool handle it?)

## Phase 4 — Triage

Every finding gets exactly one severity:

- 🔴 **Crash** — panic, segfault, abort, hang requiring kill, data corruption, double-free, stack trace in user output.
- 🟠 **Bad UX** — confusing error message, silent failure, wrong exit code (e.g. 0 on error), error printed to stdout instead of stderr, empty error message.
- 🟡 **Spec gap** — `--help` says one thing, behavior does another. Or undocumented behavior the user clearly cares about (silently ignored flag, silently truncated input).
- 🟢 **Handled well** — explicit "tried to break it, got a clean error". Include these — the report shows coverage, not just bugs, and they validate the tool's defensive posture.

If a finding is genuinely a non-issue (the input was nonsense and the error is fine), don't include it. The 🟢 bucket is for *interesting* cases where you expected a crash and got a clean error.

## Phase 5 — Report

Write to `./REDTEAM_REPORT.md` (project root, NOT into the scratch tmpdir):

```markdown
# Redteam report — `<bin>` <version>

_Generated: <date>. Black-box pass — no source files were read._

## Summary

- 🔴 Crashes: N
- 🟠 Bad UX: N
- 🟡 Spec gaps: N
- 🟢 Handled well: N
- Total invocations: ~N

Top recommendations:
1. ...
2. ...
3. ...

## Surface inventory

| subcommand | args | flags | constraints | mut-ex | inputs |
|---|---|---|---|---|---|
| ... | ... | ... | ... | ... | ... |

## Input zoo

`/tmp/redteam-<bin>/` contained: ...

## Findings

### 🔴 Crashes

| # | subcommand | input | observed | expected | repro |
|---|---|---|---|---|---|
| C1 | ... | ... | ... | ... | `<bin> ...` |

### 🟠 Bad UX

(same shape)

### 🟡 Spec gaps

(same shape)

### 🟢 Handled well

(same shape)

## Coverage matrix

| | numeric | size-suffix | path | pattern | bool-expr | enum | mut-ex | lifecycle | encoding |
|---|---|---|---|---|---|---|---|---|---|
| subcmd1 | ✅ | ⚠️ | ✅ | n/a | n/a | ✅ | ✅ | n/a | ✅ |

✅ = all checks ran clean · ⚠️ = at least one finding · ❌ = unable to test · n/a = surface doesn't apply
```

Then in chat, give an inline summary: counts by severity, top 5 findings as one-liners with their exact repro commands. The user shouldn't need to open the file to know what's broken.

## Operational notes

- **Parallelize.** When throwing many independent invocations at the same binary, batch them in one message with multiple `Bash` calls. Most fuzz invocations are sub-second; serial execution wastes wall time.
- **Cap effort.** Default budget: ~150 invocations total. If the user wants deeper, they'll say so.
- **Always `timeout 5s`** on anything that could hang: regex bombs, daemon ops, large-input runs. `timeout 5s <bin> ...; echo "exit=$?"`.
- **Capture exit codes.** `<bin> ...; echo "exit=$?"` after every test invocation, or use `&&`/`||` patterns.
- **Cleanup before exit.**
  1. If you started any daemons, stop them via the target binary's own commands (e.g. `<bin> down`). Do NOT `kill -9` arbitrary PIDs.
  2. `rm -rf /tmp/redteam-<bin>/` — the only `rm -rf` allowed.
  3. Verify `git status` shows only the new `REDTEAM_REPORT.md` (plus any pre-existing dirty files unchanged).
- **If the binary isn't built / installed**, stop and tell the user. Don't run `cargo build`, `npm install`, `pip install`, `go build`, etc. — those are mutations.
- **If a destructive subcommand exists** (`<bin> destroy`, `<bin> wipe`, `<bin> drop`), test it ONLY against scratch state inside the tmpdir. Never run it without an explicit target argument that points inside the scratch dir.
- **Don't read source.** This bears repeating. If you find yourself wanting to peek at `src/main.rs` to understand a confusing error — that confusing error IS the finding. Write it up and move on.

## Edge cases

- **Tool has no subcommands** (single-purpose CLI): treat the top-level flags as the surface, skip the per-subcommand loop.
- **Tool requires a config file or env setup**: read `--help` for the requirement, set up the minimum in the scratch dir, document in the report's "Setup" section.
- **Tool is interactive (REPL/TUI)**: this skill is for non-interactive surfaces. Note it in the report and stop, or fuzz only the non-interactive subset (e.g. `--help`, `--version`, command-line args before the REPL starts).
- **Tool requires network**: skip network-dependent surfaces. Note in report.
- **No findings at all**: the report still gets written. Show the surface inventory, the coverage matrix (all ✅), and an explicit "no findings" note. That's a valuable result.
- **Hundreds of subcommands**: pick the highest-surface ~10 (most flags, most input types, most state-altering) and note in the report that the others were not exercised.
