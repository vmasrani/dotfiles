# commands

_Last updated: 2026-01-27 (verified)_

## Purpose

Custom slash commands for Claude Code that extend its capabilities with specialized workflows. These commands provide structured approaches to code review, document processing, parallel computing, and project analysis.

## Key Files

| File | Role | Purpose |
|------|------|---------|
| `arewedone.md` | Structural completeness review | Verifies code changes are fully integrated with no technical debt via agent workflow |
| `research.md` | Context file generation | Generates or refreshes `*-context.md` files for all project directories using background agents |
| `ocr.md` | Image-to-markdown converter | Master prompt for converting technical manual pages (with OCR text) into structured markdown |
| `process-parallel.md` | Parallel pipeline template | Template and conventions for creating fault-tolerant parallel processing pipelines using uv + pmap |

## Patterns

- **Agent-driven workflows**: Commands delegate complex tasks to background agents (e.g., `structural-completeness-reviewer`, `context-researcher`)
- **Progressive disclosure**: Research command walks directory tree, batches work, and reports summary without reading generated output
- **Self-contained scripts**: Parallel processing command follows uv + pmap conventions with inline dependencies and PEP 723 metadata
- **Master prompts**: OCR command provides comprehensive extraction rules for manual page processing

## Dependencies

- **External (Claude agents)**: `structural-completeness-reviewer`, `context-researcher`
- **External (Python)**: OpenAI API, `machine-learning-helpers` (git-based), `rich` for output
- **Internal**: Follows conventions from `CLAUDE.md` (uv scripts, pathlib, pmap parallelism)

## Entry Points

Commands are invoked via Claude Code slash syntax (e.g., `/arewedone`, `/research`, `/ocr`, `/process-parallel`). Each markdown file serves as the command definition and documentation.

## Usage Patterns

- **`/arewedone`**: Post-development review to verify structural integrity before committing
- **`/research [path]`**: Generate context files for a project directory (respects `.gitignore`, skips up-to-date files)
- **`/ocr`**: Process manual pages (images + OCR text) into lossless markdown tables and sections
- **`/process-parallel`**: Create three-file pipelines (worker, runner, system_prompt) for batch LLM processing with fault tolerance
