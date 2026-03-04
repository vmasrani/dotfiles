# prompt_bank
> Repository of reusable specialized prompts for text processing and document extraction tasks.
`3 files | 2026-03-03`

## Key Files
| File | Role |
|------|------|
| cleanup_transcript.md | Transcript editor prompt for diarized transcripts with strict structure preservation |
| file-renamer.md | Filename standardization prompt using Author - Title format |
| ocr.md | OCR-to-Markdown conversion prompt for technical manual pages with layout fidelity |

## Patterns
Constraint-based prompts with explicit validation rules and forbidden output formats. Each enforces:
- Immutable structural elements (timestamps, speaker labels, numbering)
- Lossless content preservation with minimal transformation
- No meta-commentary in output
- Clear validation checklist before completion

## Entry Points
All three prompts are templates intended for direct use with Claude API or copy-paste into chat interfaces. No code or execution framework.
