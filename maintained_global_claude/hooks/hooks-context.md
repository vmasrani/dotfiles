# hooks
> Claude Code lifecycle hooks: safety guards on tool use, TTS completion announcements, and JSON event logging to `.claude/logs/`.
`6 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
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
