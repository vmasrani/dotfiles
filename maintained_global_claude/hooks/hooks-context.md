# hooks

_Last updated: 2026-01-27_

## Purpose
Claude Code lifecycle hooks for session management, tool execution safeguards, and notifications. Handles pre-/post-tool validation, audio notifications on user input requests, context file auto-refresh, and session lifecycle events with optional TTS announcements.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| pre_tool_use.py | Validates tool calls before execution; blocks dangerous `rm -rf` and `.env` access patterns | Exit code 2 to block dangerous operations |
| post_tool_use.py | Logs tool execution results to JSON for audit trail | Appends to `.claude/logs/post_tool_use.json` |
| notification.py | Announces Claude waiting for user input via TTS (30% chance includes engineer name) | Multiple TTS backend support |
| stop.py | Finalizes session with LLM-generated completion message and optional TTS announcement | Exports chat transcript to `.claude/logs/chat.json` |
| subagent_stop.py | Similar to stop.py but for subagent completion events | Fixed "Subagent Complete" message |
| session_start.py | Logs session initialization events | Records session metadata |
| refresh_context.py | Auto-generates missing/stale context files for directories via Claude API | Runs async via `Popen` |
| pre_compact.py | Records session snapshots in markdown format (keeps last 5) | Appends to `.claude/logs/compact_summary.md` |

## Patterns
- **Defense in depth**: pre_tool_use catches both pattern-matching (rm -rf) and file access violations before execution
- **Graceful degradation**: TTS and LLM calls fail silently; hooks never crash the session
- **API fallback chain**: TTS prioritizes ElevenLabs > OpenAI > pyttsx3; LLM prioritizes OpenAI > Anthropic
- **Background async**: refresh_context spawns subprocess to avoid blocking main agent thread
- **JSON audit logs**: All hooks log to `.claude/logs/` directory for post-session analysis

## Dependencies
- **External:** python-dotenv, anthropic, openai, pyttsx3, elevenlabs
- **Internal:** None (standalone hook scripts)

## Entry Points
- All scripts are executable entry points called by Claude Code lifecycle events
- Main flow: session_start -> [pre_tool_use -> tool execution -> post_tool_use] -> stop/subagent_stop
- Background: pre_compact (on session start), refresh_context (async from pre_compact), notification.py (on input wait)

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| utils/llm | LLM integration utilities (OpenAI, Anthropic completion generators) | Yes |
| utils/tts | TTS backends (ElevenLabs, OpenAI, pyttsx3) | No |