# llm
> LLM utility scripts for Claude hooks: Anthropic (anth.py) and OpenAI via DSPy (oai.py) wrappers used by hook scripts.
`7 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `anth.py` | Self-contained uv script (inline deps, no pyproject.toml needed) calling claude-3-5-haiku; also generates personalized task-completion messages via `ENGINEER_NAME` env var |
| `oai.py` | OpenAI wrapper using DSPy + gpt-4.1-nano; supports piped stdin as context, `-s` sysprompt file, and `OAI_MAX_CONTEXT_CHARS` env var for truncation |
| `pyproject.toml` | Project-level deps (dspy, typer, etc.) for running scripts via `uv run` within this dir |
| `test.py` | DSPy usage demo (multi-step article drafting with ChainOfThought) — not a test suite, more of a scratch/example file |
| `oai_bkp.py` | Backup of older oai implementation — not active |
| `main.py` | Placeholder entry point (stub only, does nothing useful yet) |

<!-- peek -->

## Conventions

- `anth.py` and `oai.py` are both executable as standalone uv scripts (PEP 723 inline metadata headers) — they do NOT require `pyproject.toml` or a venv. Run directly: `./anth.py 'prompt'` or `uv run anth.py 'prompt'`.
- `oai.py` uses DSPy as the OpenAI client layer rather than calling the OpenAI SDK directly — model is hardcoded to `openai/gpt-4.1-nano`.
- Context is passed via stdin pipe: `echo 'text' | oai.py 'question'` appends piped content under a `Context:` header in the prompt.
- `anth.py` silently returns `None` on any error (try/except swallows exceptions) — callers must handle `None` gracefully; `oai.py` exits with code 1 on error.

## Gotchas

- `anth.py` uses `claude-3-5-haiku-20241022` hardcoded — not the latest model; update manually if speed/quality tradeoff changes.
- `ENGINEER_NAME` env var in `anth.py` triggers personalized completion messages ~30% of the time — must be set in the calling hook environment or `.env` file loaded via `python-dotenv`.
- `OAI_MAX_CONTEXT_CHARS` truncates from the **end** of piped text (keeps the tail), not the beginning — relevant when piping long command outputs.
- `test.py` imports `ipdb` and runs immediately on execution (no `if __name__ == "__main__"` guard around the article draft call) — running it will make live API calls.
