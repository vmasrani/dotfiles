# maintained_global_claude
> Global Claude Code configuration and custom agents/commands/hooks maintained in dotfiles and symlinked to ~/.claude.
`8 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| settings.json | Global Claude Code settings with hooks, permissions, plugins, and statusline configuration |
| CLAUDE.md | Project guidelines for Claude Code development (Python, bash, Pydantic conventions) |
| agents/context-researcher.md | Agent definition for analyzing directories and generating structured context markdown files |
| commands/research.md | Custom /research slash command for discovering and generating/refreshing context files |
| hooks/post_tool_use.py | Logs tool execution events to JSON audit trail |

## Patterns
**Configuration as Code**: Central versionable source of truth for Claude Code config (settings.json), symlinked to ~/.claude/ during dotfiles setup. Subdirectories (agents/, commands/, hooks/, skills/, plugins/) mirror Claude's internal structure.

**Hook-based Automation**: PostToolUse, Stop, SubagentStop, PreCompact hooks implemented as uv-run Python scripts for extensibility and event logging.

**Agent Definitions**: YAML frontmatter + markdown instructions for agent roles (context-researcher, spec-interviewer, plan-writer, etc.).

## Dependencies
- **External:** Claude Code application, uv (package manager), Python 3, Anthropic/OpenAI/ElevenLabs APIs (optional)
- **Internal:** Symlinked from this repo to ~/.claude/ during setup.sh installation; used by all Claude Code sessions

## Entry Points
- `settings.json` — loaded on Claude Code startup; configures permissions, hooks, plugins, statusline
- `agents/` — agent definitions for specialized workflows
- `commands/` — custom slash commands like /research, /arewedone, /generate-tests
- `hooks/` — system event handlers triggering on PostToolUse, Stop, SubagentStop, PreCompact

## Subdirectories
| Directory | Has Context |
|-----------|-------------|
| agents | yes |
| commands | yes |
| hooks | yes |
| skills | yes |
| plugins | no |
| archive | no |
| plans | no |
| debug | no |
| todos | no |
