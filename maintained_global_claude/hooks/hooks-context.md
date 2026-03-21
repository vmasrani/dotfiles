# hooks
> Event-driven Python scripts that integrate with Claude Code workflow lifecycle (pre/post tool use, notifications, agent shutdown).
`6 files | 2026-03-18`

## Key Files
| File | Purpose |
|------|---------|
| `pre_tool_use.py` | Validates tool inputs before execution—blocks dangerous `rm -rf` patterns and blocks access to `.env` files |
| `stop.py` | Runs when agent completes—announces task completion via TTS and generates final message from LLM |
| `notification.py` | Fires when agent is waiting for user input—announces via TTS (ElevenLabs > OpenAI > pyttsx3) |
| `subagent_stop.py` | Similar to `stop.py` but for subagent shutdown events |
| `post_tool_use.py` | Runs after tool execution—post-processing hook (minimal logic) |
| `utils/` | Supporting modules: `llm/` (OpenAI/Anthropic wrappers), `tts/` (TTS backends) |

## Conventions
- All scripts use `uv run` shebang with inline dependencies—no external `pyproject.toml`
- **TTS priority**: ElevenLabs > OpenAI > pyttsx3 (falls back gracefully if API unavailable)
- **LLM priority**: OpenAI > Anthropic (for generating completion messages)
- All timeouts are 10 seconds; failures are silent (catch-all `pass`)
- Scripts accept both JSON stdin and CLI arguments for flexibility
- `ENGINEER_NAME` env var enables personalized notifications (30% chance to include name)

## Gotchas
- `pre_tool_use.py` blocks `.env` files from read/edit/write BUT allows `.env.sample` (safe fallback)
- `pre_tool_use.py` detection of `rm -rf` is regex-based—catches variations (`-fr`, `-Rf`) and recursive+force combinations
- Both `stop.py` and `notification.py` import TTS/LLM utilities via relative paths from `utils/`—will fail silently if paths don't exist
- Timeouts on subprocess calls suppress all errors—scripts never crash, just degrade gracefully
- **Order matters**: hooks fire in sequence—`pre_tool_use` → tool execution → `post_tool_use` → (on completion) `stop` + `notification`
