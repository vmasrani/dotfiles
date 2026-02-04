# TTS Utils

_Last updated: 2026-01-27_

## Purpose

Collection of text-to-speech utility scripts supporting multiple TTS backends (OpenAI, ElevenLabs, pyttsx3). Each script is standalone and configured via uv inline dependencies, accepting custom text via command-line arguments with sensible defaults.

## Key Files

| File | Role | Notable Exports |
|------|------|-----------------|
| `openai_tts.py` | OpenAI GPT-4o-mini TTS with streaming and async support | `main()` async function, uses LocalAudioPlayer |
| `elevenlabs_tts.py` | ElevenLabs Turbo v2.5 high-speed TTS synthesis | `main()` with ElevenLabs API integration |
| `pyttsx3_tts.py` | Offline cross-platform TTS (no API required) | `main()` with pyttsx3 engine configuration |

## Patterns

- **CLI argument handling**: Text input via command-line arguments or random/default fallback
- **Environment-based configuration**: API keys loaded from `.env` via `python-dotenv`
- **UV inline dependencies**: Each script declares its own dependencies in PEP 723 format
- **Async support**: OpenAI implementation uses `asyncio` for streaming audio

## Dependencies

- **External:**
  - openai (with voice_helpers)
  - elevenlabs
  - pyttsx3
  - python-dotenv

- **Internal:** None

## Entry Points

- `openai_tts.py` — AsyncOpenAI client with streaming TTS and LocalAudioPlayer playback
- `elevenlabs_tts.py` — ElevenLabs Turbo v2.5 model with cgSgspJ2msm6clMCkdW9 voice
- `pyttsx3_tts.py` — Offline pyttsx3 engine with 180 WPM speech rate

## Features

- **OpenAI**: Async streaming with custom instructions ("Speak in a cheerful, positive yet professional tone")
- **ElevenLabs**: Fast Turbo v2.5 model optimized for real-time use
- **pyttsx3**: Offline operation (no API), random completion messages when no text provided, configurable volume (0.8) and rate (180 WPM)

## Notes

- All scripts follow uv shebang pattern: `#!/usr/bin/env -S uv run --script`
- Error handling includes graceful fallbacks for missing API keys and import errors
- OpenAI and ElevenLabs require environment variables: `OPENAI_API_KEY` and `ELEVENLABS_API_KEY` respectively
- pyttsx3 requires no external authentication
