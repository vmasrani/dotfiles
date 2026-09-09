# hooks
> Codex harness lifecycle hooks: safety guards on tool use, TTS completion announcements, and JSON event logging to `.codex/logs/`.
`12 scripts | 2026-09-07`

| Entry | Purpose |
|-------|---------|
| `bash_footgun_guard.py` | PreToolUse **deny** guard for Bash commands that fabricate evidence: `rg -r` (silent --replace), piped test runs (exit code laundered by `tail`), unconditional success markers after `git commit`, destructive git (branch/worktree deletion over uncommitted work, remote-branch deletion), and committing a manifest whose dep is swapped to a local `path =` source |
| `unqueued_heavy_guard.py` | PreToolUse **deny** guard: refuses a `cargo test\|nextest\|bench\|miri` or `just test*\|bench*\|ci-fast\|ci-deep` that was not prefixed with `queue`, the machine-wide job queue — including `queue cd /repo && cargo test`, where the shell queues only the `cd` and this hook is the only component that can still see it. Also enforces "Concurrent work = pre-dev integration" (AGENTS.md): while any local branch matching `^pre-dev[0-9]*$` exists in the command's repo (numbered concurrent waves: `pre-dev`, `pre-dev2`, ...), denies these same heavy gates — even correctly `queue`d — from any branch but one of those integration branches. Replaces `test_queue_guard.py`, which silently rewrote such commands into `testq` instead; `cargo check\|clippy\|build\|install` and `just lint*` are deliberately not flagged, since staying unqueued is what keeps them instant |
| `test_count_guard.py` | PostToolUse: records each suite's test COUNT and reconciles the next run against it — a count that rises unexplained (or drops without deletions) surfaces a stale-binary warning |
| `hooks_selftest.py` | Behavioural tests for all three guards, including the false-positive shapes that must keep passing. Run `./hooks_selftest.py`; exits nonzero on any failure |
| `pre_tool_use.py` | Blocks `rm -rf` patterns and `.env` file access (exit code 2 = hard block shown to Claude); also appends every tool call to `.codex/logs/pre_tool_use.json` |
| `post_tool_use.py` | Appends every tool result to `.codex/logs/post_tool_use.json` — pure logging, no blocking |
| `stop.py` | On session end: logs to `stop.json`, optionally copies transcript to `chat.json` (via `--chat` flag), then fires TTS completion announcement |
| `subagent_stop.py` | Same as `stop.py` but for subagent sessions; announces "Subagent Complete" via TTS instead of LLM-generated message |
| `notification.py` | Fires TTS "your agent needs input" alert (only when `--notify` flag set and message isn't the generic waiting message) |
| `pre_compact.py` | On context compaction: appends a markdown snapshot to `.codex/logs/compact_summary.md`, keeping only the last 5 snapshots |
| **utils/** | TTS backends (ElevenLabs/OpenAI/pyttsx3) and LLM message generators (oai.py/anth.py) |

<!-- peek -->

## Conventions

- All hooks are standalone `uv run --script` executables — no shared virtualenv. Each declares its own inline dependencies in the `# /// script` block.
- Hooks read the harness JSON event contract from stdin and log to `.codex/logs/` relative to `cwd`, not relative to the hook file.
- Exit code semantics for `pre_tool_use.py`: `0` = allow, `2` = block and surface the error to the caller. Any other exit or exception allows while surfacing a hook error.
- TTS priority order used by `stop.py`, `subagent_stop.py`, and `notification.py`: ElevenLabs > OpenAI > pyttsx3. Selection is runtime, based on which env vars are set.
- LLM-generated completion messages (in `stop.py`) use OpenAI first, Anthropic second, random fallback third — with a 10-second subprocess timeout each.
- `notification.py` has a 30% random chance to prepend `$ENGINEER_NAME` to the notification message if that env var is set.

## Gotchas

- Hooks write logs to `Path.cwd() / '.codex/logs'` — this is the project CWD when Codex runs, not `~/.codex/`. Each project gets its own log directory.
- `pre_tool_use.py` blocks `.env` file access for `Read`, `Edit`, `MultiEdit`, `Write`, and `Bash` tools but allows `.env.sample`. The Bash pattern matching is regex-based and may miss obfuscated commands.
- `notification.py` skips TTS for the exact string `'Claude is waiting for your input'` — other notification messages do trigger TTS when `--notify` is passed.
- `pre_compact.py` splits on `"## Compact Snapshot"` as a delimiter — any existing content using that exact heading will be treated as a snapshot boundary.
- Hook scripts are symlinked into `~/.codex/hooks/` and registered by `~/.codex/hooks.json`; both links are managed by `setup.sh`. Make changes in `codex/`, never in the symlink targets.
- The three guards fail **open but never silently**: an unexpected error exits 1 (non-blocking) so a hook-error line appears rather than the guard quietly disarming. A rule that needs to consult git and gets no answer ABSTAINS — it returns no decision, leaving the normal permission flow intact, rather than inventing a verdict from missing data.
- Emitting nothing is deliberately NOT the same as `permissionDecision: allow` — allow would auto-approve the command and bypass the user's own permission rules. `bash_footgun_guard.py` only ever says "no" or says nothing.
- Guards run with `/usr/bin/python3` from `codex/hooks.json`, not through their `uv run` shebangs, so guard code must remain stdlib-only. Run `hooks_selftest.py` after any change.
