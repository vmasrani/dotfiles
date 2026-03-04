# hooks
> Event-driven lifecycle scripts for Claude Code sessions, including context refresh, safety checks, notifications, and lifecycle management.
`21 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| session_start.py | Detects stale context files and spawns background refresh process |
| pre_tool_use.py | Safety validator blocking dangerous `rm -rf` and `.env` file access |
| post_tool_use.py | Records tool execution results and timing for agent auditing |
| refresh_context.py | Regenerates context files for stale directories via `/research` |
| notification.py | Text-to-speech announcements when agent needs user input |

## Patterns
- **Event hooks**: Session lifecycle management (`session_start`, `stop`, `pre_compact`)
- **Safety gates**: Pre-tool validators preventing destructive operations
- **Async background jobs**: Stale context detection spawns non-blocking refresh
- **Tool auditing**: Post-execution logging for compliance tracking
- **TTS integration**: Modular notification system with multi-provider support (ElevenLabs > OpenAI > pyttsx3)

## Dependencies
- **External:** python-dotenv (optional), standard library (json, subprocess, pathlib, re)
- **Internal:** utils/tts/* (text-to-speech providers), utils/llm/* (LLM integrations)

## Entry Points
- `session_start.py` — Runs on Claude session initialization to detect and refresh stale context
- `pre_tool_use.py` — Pre-execution safety check for all tool calls
- `post_tool_use.py` — Post-execution logging for audit trail
- `notification.py` — Triggered when agent awaits user input

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| utils | yes |
| utils/llm | yes |
| utils/tts | yes |