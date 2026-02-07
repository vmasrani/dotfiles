# maintained_global_claude

## Purpose

Central repository of Claude Code configuration and automation, symlinked to `~/.claude/` during dotfiles setup. Provides agent definitions, CLI commands, system hooks, and skills for spec-driven development workflows using Claude AI.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| settings.json | Global Claude Code configuration | Permissions, hooks, plugins, environment settings |
| agents/structural-completeness-reviewer.md | Technical lead agent for reviewing code changes | Structural integrity review methodology |
| agents/spec-interviewer.md | Product engineer agent for feature interviews | Requirements extraction, success criteria generation |
| agents/codebase-researcher.md | Research agent for codebase exploration | Progressive disclosure strategy via context files |
| agents/plan-writer.md | Architect agent for implementation planning | Detailed subtask breakdown with code snippets |
| agents/context-researcher.md | Analysis agent for directory context generation | Context file output format and methodology |
| commands/arewedone.md | Structural completeness review workflow | Command entry point invoking reviewer agent |
| commands/research.md | Context file generation and refresh workflow | Discovery, generation, and batching of context files |
| commands/ocr.md | (Moved to ~/dotfiles/prompt_bank/ocr.md) | OCR-to-markdown conversion master prompt |
| commands/process-parallel.md | Parallel processing pipeline template | Worker/runner/system-prompt pattern |
| hooks/notification.py | Session notification handler with TTS | API key-based TTS selection (ElevenLabs > OpenAI > pyttsx3) |
| hooks/post_tool_use.py | Logs tool execution events | JSON logging to `.claude/logs/post_tool_use.json` |
| hooks/session_start.py | Session initialization hook | Detects stale context files on startup |
| hooks/stop.py | Session completion handler | Announcement via TTS when work completes |
| hooks/subagent_stop.py | Subagent completion handler | Similar to stop.py but for subagent threads |
| hooks/pre_compact.py | Pre-compaction snapshot generator | Maintains rolling snapshots before context compaction |
| hooks/refresh_context.py | Automated context file refresh | Calls Anthropic API to regenerate stale context files |

## Patterns

- **Agent-based workflows**: Spec-interviewer → plan-writer → structural-completeness-reviewer orchestration for feature delivery
- **Progressive disclosure**: Context files enable agents to avoid reading entire codebases; start with `*-context.md` summaries
- **Spec-driven development (RPI)**: Structured phases (interview, success criteria, tests, research, plan, implementation)
- **Hook-based automation**: System hooks trigger at SessionStart, PostToolUse, Stop, PreCompact to log and notify
- **TTS priority fallback**: ElevenLabs → OpenAI → pyttsx3 based on available API keys
- **JSON event logging**: All hooks output JSON to `.claude/logs/` for audit trails
- **Markdown-based prompts**: Agent definitions use frontmatter (YAML) + markdown instructions for clarity

## Dependencies

- **External:**
  - Anthropic API (for refresh_context.py)
  - OpenAI API (optional, for stop.py and subagent_stop.py TTS)
  - ElevenLabs API (optional, for notification.py and stop.py TTS)
  - python-dotenv (for loading environment variables)
  - `uv` (universal Python package manager for all scripts)

- **Internal:**
  - Symlinked to `~/.claude/` during dotfiles setup via install_dotfiles() in install/install_functions.sh
  - Referenced by dotfiles/.zshrc and shell configurations

## Entry Points

- **settings.json**: Initial configuration loaded by Claude Code UI; defines permissions, enabled plugins, and hook registration
- **hooks/session_start.py**: Auto-triggered on each Claude session start; detects stale context files
- **commands/arewedone.md**: Invoked via `/arewedone` slash command; launches structural-completeness-reviewer agent
- **commands/research.md**: Invoked via `/research` slash command; discovers and generates context files
- **skills/create-plan/SKILL.md**: Invoked via `/create-plan` slash command; orchestrates RPI workflow phases

## Subdirectories

| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| agents | Agent definitions for spec interview, research, planning, review | no |
| commands | CLI commands invoking agents or workflows | no |
| hooks | System event handlers (session start, tool use, completion, compaction) | no |
| skills | Complex skill definitions like create-plan with multi-phase orchestration | no |
| hooks/utils/llm | LLM API wrappers (Anthropic, OpenAI) for hook scripts | no |
| hooks/utils/tts | Text-to-speech implementations (ElevenLabs, OpenAI, pyttsx3) | no |
| .claude | Logs directory for JSON event audit trails | no |
| archive, debug, downloads, file-history, ide, plans, projects, session-env, shell-snapshots, statsig, telemetry, todos | Git-ignored directories for Claude internal state | no |
