# llm

_Last updated: 2026-01-27_

## Purpose
Python utilities for LLM integration, providing command-line interfaces to query OpenAI (via DSPy) and Anthropic APIs. Used as helper scripts within Claude hooks and tools for dynamic LLM-based operations.

## Key Files
| File | Role | Notable Exports |
|------|------|-----------------|
| `anth.py` | Anthropic LLM prompting script | `prompt_llm()`, `generate_completion_message()` |
| `oai.py` | OpenAI/DSPy CLI tool | `prompt_llm()`, `main()` (Typer app) |
| `test.py` | DSPy article drafting prototype | `DraftArticle` (DSPy Module) |
| `pyproject.toml` | Project metadata and dependencies | dspy, typer, pandas, ipdb, python-dotenv |
| `main.py` | Stub entry point | Placeholder |
| `.python-version` | Python version pinning | 3.12 |

## Patterns
- **Modular script design**: Two separate LLM integration paths (Anthropic via `anth.py`, OpenAI via `oai.py`), each with independent CLI
- **DSPy framework**: `oai.py` and `test.py` use DSPy's typed signature system for structured LLM interactions
- **CLI abstraction**: `oai.py` uses Typer for clean argument parsing; supports piped stdin and system prompt files
- **Environment-based config**: Both scripts load from `.env` for API keys and parameters (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OAI_MAX_CONTEXT_CHARS`, `ENGINEER_NAME`)

## Dependencies
- **External:** dspy, typer, pandas, python-dotenv, anthropic, ipdb, rich
- **Internal:** None (standalone utilities)

## Entry Points
- `anth.py` — Direct Anthropic API prompting; supports `--completion` flag for dynamic completion messages
- `oai.py` — OpenAI DSPy wrapper with CLI; accepts prompt arguments, optional system prompt file (`-s/--sysprompt`), piped context, and max context truncation
- `test.py` — Development/testing script demonstrating DSPy's article outline and drafting workflow

## Subdirectories
None
