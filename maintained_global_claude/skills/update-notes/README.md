# update-notes — Philosophy

## What this is

A project-scoped **zettelkasten** — a growing, linked set of small, focused notes about one specific codebase. Each note captures one non-obvious engineering finding: an API quirk, a footgun, a convention, a consolidation candidate, a benchmark, a decision and its rationale.

Notes live in `./.notes/` in the project root. The collection grows from project infancy to maturity to release, and outlives any single conversation.

## What this is NOT

Four things look similar to a zettelkasten but aren't this:

1. **Conversation summaries.** Those belong in the transcript or a daily log. They're chronological; notes are topical.
2. **Claude's memory system.** That's under `~/.claude/projects/<proj>/memory/` and captures *user preferences* ("user prefers uv over pip") and *session feedback*. Notes here capture *engineering truths about the code*.
3. **TODO lists.** Tasks are actionable and transient. Notes are knowledge and durable.
4. **Documentation.** Docs describe the intended behavior for users. Notes describe the *non-obvious* reality for maintainers — the sharp edges, the redundancy, the quiet invariants.

## Why zettelkasten, not one big NOTES.md

- **Cross-linkability.** A footgun and a convention often reinforce each other. Small notes with `related:` links form a graph. One big file doesn't.
- **Stable identity.** Each finding has a slug that survives reruns, so the skill can update in place rather than duplicating.
- **Focused reads.** A future Claude landing cold on the project can read `INDEX.md`, pick the 2-3 relevant notes, and skip the rest. A monolithic file forces whole-file reads.
- **Organic category growth.** Directories emerge from the material, not from a pre-imposed taxonomy.

## Why this runs periodically

Engineering insight arrives in bursts. The user doesn't know on day 1 that `BUILD_RAM=0` silently OOMs — they learn it during a debugging session on week 6. The skill is designed to be invoked at those moments: "we just figured something out; save it."

Over months, the `.notes/` folder becomes the project's institutional memory — the thing a new contributor (human or AI) reads first to get to productive-velocity fastest.

## Design constraints baked into the skill

- **Output is always `./.notes/`**, never `~/.claude/...`. This is project-scoped, not global.
- **Idempotent.** Safe to run many times. Same conversation -> same notes, no duplicates.
- **Never deletes.** Pruning is a human decision.
- **Many small notes > one big note.** ~80 lines is a smell; split.
- **Stable slugs.** The filename is the identity.
- **General-purpose.** No assumptions about stack, language, or domain.

## How it differs from Claude memory

| Axis                 | Claude memory                        | `.notes/` zettelkasten                 |
|----------------------|--------------------------------------|----------------------------------------|
| Location             | `~/.claude/projects/<proj>/memory/`  | `./.notes/` in project cwd             |
| Subject              | User preferences, feedback patterns  | Engineering truths about the codebase  |
| Persistence          | Across all sessions for this project | In the repo; travels with the project  |
| Who benefits         | Claude tailoring its behavior        | Any maintainer (Claude or human)       |
| Shape                | Flat bullets                         | Linked markdown notes with frontmatter |
| Pruning              | Automatic / background               | Manual, user-driven                    |

Both are valuable. They don't overlap.

## Usage

Invoke `/update-notes` (or one of the natural-language triggers — see `SKILL.md`) when a session has uncovered something worth saving. The skill will scan the conversation, filter for non-obvious engineering findings, create or update notes in `.notes/`, and regenerate `INDEX.md`. It will report what it did.

Commit `.notes/` to the repo if you want the zettelkasten to travel with the project. Gitignore it if you want a private, machine-local knowledge base. Either works; the skill doesn't care.
