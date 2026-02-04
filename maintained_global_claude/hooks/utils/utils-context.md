# hooks/utils

_Last updated: 2026-01-27_

## Purpose

Utility modules for Claude hooks, providing LLM integration utilities and text-to-speech implementations. These scripts enable interaction with multiple AI models and voice synthesis services via lightweight, dependency-injected Python scripts using UV for dependency management.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| `llm/anth.py` | Anthropic LLM wrapper | `prompt_llm()`, `generate_completion_message()` |
| `llm/oai.py` | OpenAI LLM integration with DSPy | `prompt_llm()`, typer CLI app |
| `llm/main.py` | Module entry point (stub) | Basic structure |
| `tts/elevenlabs_tts.py` | ElevenLabs TTS script | Turbo v2.5 text-to-speech |
| `tts/openai_tts.py` | OpenAI TTS with streaming | `gpt-4o-mini-tts` model support |
| `tts/pyttsx3_tts.py` | Offline TTS engine | Lightweight local synthesis |
| `llm/pyproject.toml` | Dependency manifest | dspy, typer, pandas, python-dotenv |

## Patterns

- **UV script shebangs** — All Python scripts use `#!/usr/bin/env -S uv run --script` with inline dependency declarations, enabling single-file execution without separate dependency management
- **API-agnostic design** — Multiple TTS backends (ElevenLabs, OpenAI, offline pyttsx3) allow swapping providers based on availability and use case
- **Environment-based configuration** — API keys and settings loaded via `python-dotenv`, supporting `.env` files for local development
- **CLI-first utilities** — Scripts accept command-line arguments with sensible defaults, allowing both interactive and programmatic use

## Dependencies

- **External (LLM):** anthropic, dspy, openai, python-dotenv, typer, pandas, ipdb
- **External (TTS):** elevenlabs, openai[voice_helpers], pyttsx3, python-dotenv
- **Internal:** None (standalone utility modules)

## Entry Points

- `llm/anth.py` — Direct CLI for Anthropic prompting; supports `--completion` flag for dynamic message generation
- `llm/oai.py` — Typer-based CLI for OpenAI integration with system prompts and text sanitization
- `tts/elevenlabs_tts.py` — ElevenLabs Turbo TTS with voice ID and custom text support
- `tts/openai_tts.py` — OpenAI TTS with streaming audio playback via LocalAudioPlayer
- `tts/pyttsx3_tts.py` — Offline TTS with random completion messages as default

## Subdirectories

| Directory | Purpose | Has Context File |
|-----------|---------|-----------------|
| `llm/` | LLM integration utilities (Anthropic, OpenAI, DSPy) | yes |
| `tts/` | Text-to-speech implementations (multiple backends) | no |
