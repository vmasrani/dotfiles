# Philosophy — why this skill exists and what it is not

## Intent

Build a **project-scoped zettelkasten** of non-obvious engineering truths about one codebase. Grow it from project infancy to release. Each note is one idea, with stable identity (slug = filename), linked into a graph via `related:` frontmatter, and surfaced through a regenerated `INDEX.md`.

Notes are read cold by future Claudes and human maintainers. They exist to compress "I wouldn't have guessed that" into one paragraph the reader can absorb in ten seconds.

## Distinctions the skill must enforce

| This skill (`.notes/`)              | Claude memory                        | Daily log             | TODO tracker         |
|-------------------------------------|--------------------------------------|-----------------------|----------------------|
| `./.notes/` in project cwd          | `~/.claude/projects/<proj>/memory/`  | Dendron daily note    | User's task system   |
| Engineering truths about code       | User preferences, session feedback   | Chronological summary | Actionable work      |
| Topical, linked                     | Flat bullets                         | Time-ordered          | State-machine items  |
| Travels with the repo (user commits)| Machine-local to `~/.claude`         | Separate vault        | Separate system      |
| Curated by this skill               | Curated by Claude between sessions   | Curated by log-to-daily | Curated by the user  |

If the user asks to save something that fits another column, redirect them. If they insist, save it but note the misfit in the body.

## Why many small notes

- **Cross-linkability** — a footgun and a convention reinforce each other through `related:` edges. One big file has no graph.
- **Stable identity** — a slug per finding lets repeated runs update in place rather than duplicating.
- **Focused reads** — cold readers skim `INDEX.md`, pick 2-3 notes, skip the rest. Monolithic files force whole-file reads.
- **Organic taxonomy** — categories emerge from the material; they aren't imposed up front.

## Why periodic, not continuous

Engineering insight arrives in bursts — usually during debugging or refactor sessions. The skill is designed to be invoked at those moments ("we just figured something out; save it"), not on every turn. Over months, the folder becomes the project's institutional memory.

## Invariants

1. Output is always `./.notes/` under cwd, never `~/.claude/...`.
2. Idempotent — rerunning with no new findings is a no-op except for INDEX timestamp.
3. No deletions — pruning is a human decision.
4. Small notes — ~80 lines is a smell; split.
5. Stable slugs — the filename is the identity, survives reruns.
6. General-purpose — no assumptions about stack, language, or project domain.
