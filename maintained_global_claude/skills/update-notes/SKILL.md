---
name: update-notes
description: Capture non-obvious engineering insights about the current project into a `.notes/` zettelkasten in the project root. Use this skill when the user types `/update-notes`, says "save this to project notes", "update the notes", "add that to the zettelkasten", "note this finding", "we just learned something worth saving about this project", or signals that a session uncovered an API quirk, footgun, architecture gotcha, redundancy map, consolidation candidate, convention, invariant, benchmark, or decision-with-rationale that will help future iteration on the code. Run periodically across a project's lifetime — designed to be idempotent and run many times. Do NOT use for session summaries, user preferences, task status, or TODO items — those belong elsewhere.
---

# update-notes — Project Engineering Zettelkasten

Curate a durable, navigable knowledge base of **non-obvious engineering insights** about the current project, stored in `./.notes/` relative to the user's working directory. Runs repeatedly over the life of a project — each run updates existing notes or adds new ones, and regenerates `INDEX.md`.

This is **not** a conversation summary, session log, user-preference memory, or TODO list. See the rule-of-thumb below.

## Bundled resources — read on demand, not upfront

- `assets/note-template.md` — copy this when creating a new note; fill every frontmatter field.
- `references/philosophy.md` — read ONCE if you need the rationale for why notes and Claude-memory are separate, or if the user pushes back on a filing decision.
- `references/category-seed.md` — read when you are choosing a category for a finding and want definitions + examples for each seed category, or when deciding whether to introduce a new category.

Do not load the references upfront on every run. The steps below are self-contained for the normal path.

---

## What belongs in `.notes/`

Capture findings that will help a future Claude or human iterate on the code faster:

- **API surface quirks** — "Builder X and helper Y look different but overlap ~80%; prefer X because Z"
- **Redundancy maps** — "Functions A, B, C all do overlapping things; consolidation candidate"
- **Footguns** — "If env var `BUILD_RAM=0` is unset, process silently OOMs at step N"
- **Architecture gotchas** — "Sidecar flow bypasses the main router when flag F is set"
- **Subtle invariants** — "Column order in the Arrow buffer must match schema definition order"
- **Integration pitfalls** — "Library X's async client leaks sockets under concurrency > 8"
- **Convention discoveries** — "Repo uses columnar Arrow format, not row-wise Parquet"
- **Deprecation / consolidation plans** — "Module M slated for removal once callers migrate to N"
- **Decisions with rationale** — "Chose Polars over Pandas because streaming group-by memory profile"
- **Benchmarks** — "Config A is 3.2x faster than config B on workload W; see run-2025-10-02"

## What does NOT belong here

- Conversation or session summaries -> stay in transcript / daily log
- User preferences / feedback ("user prefers X") -> `~/.claude/projects/<proj>/memory/`
- TODO items / task status -> task tracker, not zettelkasten
- One-off debug fixes where the full context lives in the commit message -> commit history
- Restatements of documentation that already exists in the repo -> link to it, don't copy

**Rule of thumb:** if a smart new teammate reading this note 6 months later would say "huh, I wouldn't have guessed that" or "that saved me an afternoon", it belongs. Otherwise skip it.

If the user insists on saving something that clearly belongs elsewhere, push back once and redirect them to the right system (Claude memory for preferences, task tracker for TODOs, commit history for one-off debug fixes). Then, if they still insist, save it — user override wins.

---

## Directory layout created in the project

```
.notes/
  INDEX.md                      # auto-regenerated every run
  api-surface/
  architecture/
  footguns/
  conventions/
  integrations/
  decisions/
  benchmarks/
  gotchas/
```

The seed categories above are a starting set. Create new category directories organically when a finding genuinely does not fit. Do not invent categories gratuitously — reuse existing ones when plausible. See `references/category-seed.md` for definitions.

---

## Note format

Each note is a single markdown file. Filename is the slug plus `.md` (e.g. `builder-redundancy.md`). Frontmatter:

```yaml
---
id: builder-redundancy          # stable slug, matches filename sans .md
title: Builder redundancy between FooBuilder and BarHelper
category: api-surface           # directory name
created: 2026-04-22             # ISO date, never changes after first write
updated: 2026-04-22             # ISO date, bumped on every edit
tags: [builder, consolidation, api]
source: conversation            # conversation | research | interview | code-scan
confidence: high                # high | medium | low
related: [query-primitives, sidecar-flow]
---
```

Body structure (keep it short — aim for under 80 lines; split if longer):

```markdown
## Finding

One-paragraph statement of the insight.

## Evidence

- `src/foo/builder.py:42` — FooBuilder.build()
- `src/bar/helper.py:17` — BarHelper.assemble()

Both produce the same shape via different code paths.

## Implications

What this means for future changes — what to prefer, what to avoid, what to watch for.

## Related

- [[query-primitives]] — shares the same underlying primitive
```

File paths MUST be repo-relative and include line numbers when they point to specific code. Use `[[note-id]]` wiki-link style for cross-references inside the body; the `related:` frontmatter field is the source of truth for the INDEX.

---

## Execution steps when invoked

### Step 1 — Detect project root and ensure `.notes/` exists

Use the current working directory as the project root. Do NOT walk up looking for git or package files — the user is responsible for invoking from the project root.

```bash
pwd                                                    # record project root
mkdir -p .notes                                        # idempotent
```

If `.notes/` was just created, the run is a first-time init — proceed to Step 2 knowing the existing-notes inventory will be empty.

### Step 2 — Inventory existing notes

```bash
fd -e md . .notes 2>/dev/null | sort
```

For each existing note, Read its frontmatter only (first ~15 lines is enough) and build an in-memory map of:

- `id -> { title, category, tags, updated, related, path }`

This inventory is the deduplication basis. Never write a new file whose slug collides with an existing one — instead, update the existing file.

### Step 3 — Mine the current conversation for findings

Scan the current conversation (what the user and you have been discussing this session) for candidate findings. For each candidate, apply the filter:

- Is it **non-obvious** to a smart new teammate? (If obvious, skip.)
- Is it **engineering-flavored**? (Not preference, not task status, not chitchat.)
- Does it help **future iteration speed**? (API quirk, footgun, invariant, consolidation candidate, convention, decision-with-rationale, benchmark.)
- Will it still be true in 3 months? (Transient debug state -> skip.)

If nothing passes the filter, report "no findings worth saving this run" and stop. Do not pad the notes with weak entries.

### Step 4 — For each finding, decide create-or-update

Generate a candidate slug from the finding's essence — kebab-case, 2-5 words, stable across reruns (e.g. `builder-redundancy`, not `builder-redundancy-v2`).

- **Match exists?** If the slug or a very-close semantic twin already exists (similar title, overlapping tags, same category), UPDATE:
  - Bump `updated:` to today
  - Refine/append body content (don't duplicate; integrate)
  - Expand `tags:` and `related:` only if genuinely new
- **No match?** CREATE:
  - Set `created:` and `updated:` to today
  - Choose `category:` from existing dirs, or introduce a new one with justification
  - Fill frontmatter completely — no empty required fields
  - Keep body under ~80 lines; split into two notes if it sprawls

Use the template at `~/.claude/skills/update-notes/assets/note-template.md` as the starting shape. When uncertain which category fits, read `~/.claude/skills/update-notes/references/category-seed.md`.

### Step 5 — Regenerate `INDEX.md`

Walk `.notes/` and build `INDEX.md` with the following shape:

```markdown
# Project Notes Index

_Last regenerated: 2026-04-22 by /update-notes_

Total notes: 14 across 6 categories.

## api-surface

- [builder-redundancy](api-surface/builder-redundancy.md) — FooBuilder and BarHelper produce overlapping shapes; prefer FooBuilder.
- [query-primitives](api-surface/query-primitives.md) — Three query builders share one primitive; surface asymmetry.

## architecture

- [sidecar-flow](architecture/sidecar-flow.md) — Sidecar bypasses main router when `SIDECAR=1`.

## footguns

- [build-ram-env-var](footguns/build-ram-env-var.md) — Unset `BUILD_RAM` silently OOMs at the reduce step.
```

One-line hook per note = first non-empty sentence of the `## Finding` section, trimmed to ~120 chars. Categories are dir names, alphabetized. Notes within a category are alphabetized by id.

Overwrite `INDEX.md` in full each run — it is a derived artifact.

### Step 6 — Report back

Print a compact summary:

```
update-notes: done
  created: 2  (api-surface/builder-redundancy, footguns/build-ram-env-var)
  updated: 1  (architecture/sidecar-flow)
  skipped: 3  (too-obvious: 2, preference-not-insight: 1)
  index:   .notes/INDEX.md  (14 notes, 6 categories)
```

Never delete notes. If a finding becomes obsolete, flag it in the body ("Superseded by X as of YYYY-MM-DD") and leave the file — the user prunes manually.

---

## Invariants & rules

1. **Output path is always `./.notes/`** under the user's cwd. Never `~/.claude/...`.
2. **Idempotent.** Running twice in a row with no new findings is a no-op except for the INDEX timestamp.
3. **No deletions.** The skill never removes notes, even if it thinks they're wrong.
4. **Small notes.** Over ~80 lines is a smell. Split.
5. **Stable slugs.** The slug is the identity — if you re-derive a different slug for the same finding on a rerun, you will duplicate. Check the inventory before naming.
6. **One idea per note.** If the draft body covers two findings, make two notes and cross-link them.
7. **No speculation.** `confidence: high` only when evidence is in the note body. Otherwise `medium` or `low`.
8. **General-purpose.** This skill runs across many projects. Do not bake in assumptions about the current project's stack.

---

## Edge cases

- **First run with no `.notes/`:** create it, proceed normally.
- **Conversation contains only chitchat:** report "no findings" and stop.
- **User explicitly says "save X":** weight toward saving even if borderline — user override wins, but still apply filters and push back if X is clearly preference/TODO/session-summary (redirect them to the right system).
- **Slug collision across categories:** slugs are globally unique across `.notes/` (not per-category). If `api-surface/foo.md` exists, do not also create `gotchas/foo.md`.
- **`INDEX.md` was hand-edited:** overwrite anyway — it's derived. Warn the user in the report if the pre-existing INDEX had obvious manual content (non-standard sections, prose paragraphs).
- **Two conflicting findings:** create both notes, cross-link via `related:`, set `confidence: medium` on both, and surface the conflict in each body.
- **Massive conversation (hundreds of turns):** prefer recent findings; do not try to retroactively mine the entire history unless the user asks.
