# tts
> Three interchangeable TTS backends (ElevenLabs, OpenAI, pyttsx3) invoked by hooks to speak notifications aloud.
`3 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `pyttsx3_tts.py` | Offline fallback TTS — no API key needed; randomizes completion phrases when called with no args |
| `elevenlabs_tts.py` | High-quality cloud TTS via ElevenLabs Turbo v2.5; hardcoded voice ID `cgSgspJ2msm6clMCkdW9` |
| `openai_tts.py` | Streaming cloud TTS via `gpt-4o-mini-tts`; uses async `LocalAudioPlayer` for live playback |

<!-- peek -->

## Conventions
- All three scripts share the same CLI interface: text is passed as positional args (`script.py "say this"`), or a default phrase is used when called with no args.
- All use the `#!/usr/bin/env -S uv run --script` shebang with inline `# /// script` dependency blocks — no venv setup required.
- API keys are read from env vars (`ELEVENLABS_API_KEY`, `OPENAI_API_KEY`) loaded via `python-dotenv`; secrets live in `local/.local_env.sh` (git-ignored).

## Gotchas
- `openai_tts.py` is the only async script (`asyncio.run(main())`); the ElevenLabs and pyttsx3 variants are synchronous — mixing them in a hook requires knowing which is called.
- The ElevenLabs voice ID is hardcoded — changing voice requires editing the script directly, not a config.
- `pyttsx3` plays audio synchronously and blocks until done; the OpenAI script streams audio live. Hook callers that care about latency should choose accordingly.
- `openai_tts.py` requires `openai[voice_helpers]` for `LocalAudioPlayer` — the extra bracket syntax matters for the inline dependency declaration.
