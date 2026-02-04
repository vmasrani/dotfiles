# tabstack_comparison

_Last updated: 2026-01-27_

## Purpose
Benchmark and comparison framework for evaluating LLM performance differences between Tabstack and GPT-4. Contains test infrastructure for running performance evaluations across multiple AI models and storing results.

## Key Files
| File | Role | Notable Info |
|------|------|--------------|
| `.claude/settings.local.json` | Claude Code configuration | Defines API key permissions for OPENAI_API_KEY and TABSTACK_API_KEY |

## Patterns
- **Benchmark Structure**: Modular comparison framework with separate result directories for each model variant (tabstack, gpt41)
- **API Integration**: Multi-model support with API key validation and environment configuration

## Dependencies
- **External**: OpenAI API, Tabstack API
- **Internal**: Parent repo dotfiles configuration

## Entry Points
- Benchmark script (referenced in chat history as `@../benchmark.py`) — main LLM evaluation runner with caching to skip redundant API calls

## Subdirectories
| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| `benchmark_results/` | Stores benchmark execution results for each model | No |
| `benchmark_results/tabstack/` | Tabstack model benchmark results | No |
| `benchmark_results/gpt41/` | GPT-4.1 model benchmark results | No |
| `.claude/` | Claude Code session data and logs | No |
| `__pycache__/` | Python bytecode cache | N/A |

## Notes
- Directory is git-ignored (matches `*-context.md` pattern in root .gitignore)
- Claude Code workspace with session history logged since 2026-01-01
- Benchmark script enhanced to support result caching and conditional LLM calls
