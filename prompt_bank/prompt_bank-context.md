# prompt_bank
> Collection of reusable LLM system prompts for specific tasks: file renaming, OCR transcription, and transcript cleanup.
`3 files | 2026-04-02`

| Entry | Purpose |
|-------|---------|
| `file-renamer.md` | Prompt enforcing "Author - Title - Subtitle" filename format; instructs model to return only the filename, no commentary |
| `ocr.md` | Master prompt for converting technical manual images + OCR text into structured Markdown; visual layout overrides OCR reading order |
| `cleanup_transcript.md` | Prompt for cleaning diarized transcripts while preserving timestamps, speaker labels, and segment count exactly |

<!-- peek -->

## Conventions
- Prompts are plain Markdown files containing only the system prompt text — no frontmatter, no metadata, no wrapper format.
- Each prompt explicitly forbids model commentary/explanations in the output; the output format is always raw content only.
- Prompts are intended to be copy-pasted or piped into LLM calls, not executed directly by any script in this repo.

## Gotchas
- `ocr.md` treats visual layout as ground truth over OCR text order — this is intentional and must not be changed; models default to OCR order and produce wrong column mappings without this constraint.
- `cleanup_transcript.md` requires output to begin with `# [Speaker Name] - [Timestamp]` with zero preceding text — any model that adds a preamble violates the contract and breaks downstream parsers.
- `file-renamer.md` ends with a bare `Original filename:` line with no trailing newline content — the caller appends the actual filename before sending; do not add a default value there.
