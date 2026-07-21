# hooks
> Claude Code lifecycle hooks: safety guards on tool use, TTS completion announcements, and JSON event logging to `.claude/logs/`.
`10 files | 2026-07-20`

| Entry | Purpose |
|-------|---------|
| `bash_footgun_guard.py` | PreToolUse **deny** guard for Bash commands that fabricate evidence: `rg -r` (silent --replace), piped test runs (exit code laundered by `tail`), unconditional success markers after `git commit`, destructive git (branch/worktree deletion over uncommitted work, remote-branch deletion), and committing a manifest whose dep is swapped to a local `path =` source |
| `test_queue_guard.py` | PreToolUse **rewrite** hook: routes heavy cargo/just commands through `testq`, the machine-wide job queue. Owns the `HEAVY_CARGO_VERBS` / `JUST_HEAVY_RE` definition that the footgun guard imports |
| `test_count_guard.py` | PostToolUse: records each suite's test COUNT and reconciles the next run against it — a count that rises unexplained (or drops without deletions) surfaces a stale-binary warning |
| `hooks_selftest.py` | Behavioural tests for all three guards, including the false-positive shapes that must keep passing. Run `./hooks_selftest.py`; exits nonzero on any failure |
| `pre_tool_use.py` | Blocks `rm -rf` patterns and `.env` file access (exit code 2 = hard block shown to Claude); also appends every tool call to `.claude/logs/pre_tool_use.json` |
| `post_tool_use.py` | Appends every tool result to `.claude/logs/post_tool_use.json` — pure logging, no blocking |
| `stop.py` | On session end: logs to `stop.json`, optionally copies transcript to `chat.json` (via `--chat` flag), then fires TTS completion announcement |
| `subagent_stop.py` | Same as `stop.py` but for subagent sessions; announces "Subagent Complete" via TTS instead of LLM-generated message |
| `notification.py` | Fires TTS "your agent needs input" alert (only when `--notify` flag set and message isn't the generic waiting message) |
| `pre_compact.py` | On context compaction: appends a markdown snapshot to `.claude/logs/compact_summary.md`, keeping only the last 5 snapshots |
| **utils/** | TTS backends (ElevenLabs/OpenAI/pyttsx3) and LLM message generators (oai.py/anth.py) |

<!-- peek -->

## Conventions

- All hooks are standalone `uv run --script` executables — no shared virtualenv. Each declares its own inline dependencies in the `# /// script` block.
- All hooks read JSON from stdin (Claude SDK contract) and log to `.claude/logs/` relative to `cwd` at time of invocation, not relative to the hook file's location.
- Exit code semantics for `pre_tool_use.py`: `0` = allow, `2` = block and surface error to Claude. Any other exit or exception silently allows (hooks fail open).
- TTS priority order used by `stop.py`, `subagent_stop.py`, and `notification.py`: ElevenLabs > OpenAI > pyttsx3. Selection is runtime, based on which env vars are set.
- LLM-generated completion messages (in `stop.py`) use OpenAI first, Anthropic second, random fallback third — with a 10-second subprocess timeout each.
- `notification.py` has a 30% random chance to prepend `$ENGINEER_NAME` to the notification message if that env var is set.

## Gotchas

- Hooks write logs to `Path.cwd() / '.claude/logs'` — this is the project CWD when Claude runs, not `~/.claude/`. Each project gets its own log directory under its own `.claude/logs/`.
- `pre_tool_use.py` blocks `.env` file access for `Read`, `Edit`, `MultiEdit`, `Write`, and `Bash` tools but allows `.env.sample`. The Bash pattern matching is regex-based and may miss obfuscated commands.
- `notification.py` skips TTS for the exact string `'Claude is waiting for your input'` — other notification messages do trigger TTS when `--notify` is passed.
- `pre_compact.py` splits on `"## Compact Snapshot"` as a delimiter — any existing content using that exact heading will be treated as a snapshot boundary.
- Hook scripts are symlinked into `~/.claude/hooks/` by `setup.sh`; changes must be made here in `maintained_global_claude/hooks/`, never in the symlink targets.
- The three guards fail **open but never silently**: an unexpected error exits 1 (non-blocking) so a hook-error line appears rather than the guard quietly disarming. A rule that needs to consult git and gets no answer ABSTAINS — it returns no decision, leaving the normal permission flow intact, rather than inventing a verdict from missing data.
- Emitting nothing is deliberately NOT the same as `permissionDecision: allow` — allow would auto-approve the command and bypass the user's own permission rules. `bash_footgun_guard.py` only ever says "no" or says nothing.
- Guards are invoked with `/usr/bin/python3` (see `settings.json`), NOT `uv run`, despite the `uv run --script` shebang — so guard code must be **stdlib-only**. A new third-party import will not fail a test; it will fail at hook time, where it fails open and the guard silently stops guarding. Run `hooks_selftest.py` after any change.
