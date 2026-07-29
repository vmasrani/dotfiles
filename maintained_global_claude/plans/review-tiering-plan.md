# Review policy v2: give the reviewer a command, aim review at reviewable code, record it honestly

**Status:** rewritten 2026-07-28 after an adversarial three-agent audit of the
original plan. The original's diagnosis (review is mis-aimed, not over-applied)
survived fact-checking; most of its mechanism did not. This version replaces it.

**Audit provenance:** every empirical claim below was independently re-derived
from `sophiaconsulting/parot-radar` (78 merged PRs) via `gh` on 2026-07-28.
Claims the audit killed are listed at the bottom so they don't come back.

---

## What is true (verified)

- **Rule 6 is separation of duties, not cardinality.** One agent reviewing many
  PRs is legal today; nothing organizes it. (`AGENT_WORKFLOW.md`, rule 6.)
- **Zero merged PRs carry a review object** (`reviews.totalCount = 0` on all 78).
  Review lives in ~24 ad-hoc prose comment shapes; only 15 of 78 use the
  "Independent review" header. There is no standard to migrate — only a habit.
- **Reviewable code is buried under generated churn.** Per-PR splits verified
  exactly: #99 = 677 code + 53,395 generated; #95 = 24 + 31,928; #57 = 651 +
  28,084; #116 = 17,281 + 0 (93 files, merged with no review record); #115 =
  3,690 + 0 (same).
- **A PR author CAN post a COMMENT-type review on their own PR.**
  Verified against live self-COMMENT review objects on `cli/cli` (July 2026);
  GitHub blocks only self-APPROVE / self-REQUEST_CHANGES. No throwaway-repo
  test needed.

## What is false (and must stay dead)

- **"The review object gives us enforceable separation of duties."** No. All
  PRs and all reviews come from the same GitHub login. A COMMENT review never
  satisfies branch protection (`reviewDecision` stays `REVIEW_REQUIRED`), and
  no API field distinguishes an author's review from an independent one.
  At a single account, separation of duties is **honor-system, full stop**.
  The review object buys **auditability** — typed, timestamped, queryable —
  and that is the honest sell.
- **"Tier A (zero reviewable churn) needs a provenance-digest gate."** Only
  1 of 78 PRs had zero reviewable churn; even the flagship regeneration PRs
  carried 24–677 lines of code. The digest gate also has five unmet
  prerequisites (artifact→command registry, regen recipe, digest compare,
  byte-determinism, CI budget) — it is a project, not a bullet.
- **"Threshold = recent median reviewable churn."** A percentile is a
  treadmill, not a risk measure: it pins ~half of PRs above the bar forever,
  *rises* when large PRs land, swings 33% by window choice, and the prose
  definition of "reviewable" diverged 22% between two independent readers.
- **"52 of 77 PRs share hot files, so sweeping reuses context."** Inflated
  ~1.6×: the shared files are mostly `justfile`/`.gitignore`/generated JSON.
  The honest figure is 33 of 78 sharing genuinely reviewable hot files —
  still worth sweeping, at the honest number.

## The structural finding the original missed

**The reviewer role has no command.** `/start-task`, `/open-pr`, `/check-pr`,
`/finish-task`, `/triage` all serve the author. The role the entire policy
depends on — "a separate review agent" — has zero tooling, no defined
procedure, and no output format. That is the same "rule with no actor" hole
the original plan diagnosed in fast-lane and triage, one level up. Fixing it
comes before any tiering.

---

# The changes, in dependency order

## 1. `commands/review.md` — the missing actor (new, first)

One PR in, one verdict out. The procedure:

1. `gh pr view <n>` + reviewable-churn split via the shared script (change 2).
2. Read the reviewable files only; check hazard paths (change 4's list).
3. Post the verdict as a review object:
   `gh pr review <n> --comment --body-file <verdict.md>` — verified mechanism.
   The body opens with a machine-greppable first line:
   `Review-verdict: approve|block  Tier: B|C  Reviewable-churn: <n>`
   and states plainly: *reviewer shares the author's GitHub account;
   independence is procedural (separate agent session), not enforced by GitHub.*
4. A `block` verdict names the failing invariant and the concrete fix, on the PR.

## 2. One definition of "reviewable" — `.agent-workflow/reviewable.toml` + `tools/reviewable-churn.sh`

The load-bearing term must not live in prose (measured drift: 22% between two
readers of the same sentence). A committed per-repo file:

```toml
# Paths whose churn is NOT reviewable code. Err toward reviewing more.
generated = ["web2/src/data/mined/**", "*.parquet", "*.csv", "*.ndjson",
             "*.lock", "package-lock.json"]
```

read by ONE kit-vendored script that everything else calls (`/review`,
`/review-sweep`, `/open-pr`'s tier stamp). Default when the file is absent:
lockfiles + binary formats only — i.e. almost everything is reviewable, per
the "wrong toward more review" rule. The script prints reviewable/generated
line counts and the file lists; it never silently excludes.

## 3. `commands/review-sweep.md` — one reviewer, many PRs

Organizes what is already legal. Shape: list open PRs → drop any this session
authored → group by touched subsystem → run change 1's procedure per PR while
context is warm → one review object per PR, never a combined one. Cap ~6.

The self-authorship refusal, made mechanical instead of theater:
- refuse any PR whose head branch appears in `git worktree list` on this
  machine (a live worktree means some local session owns it);
- require the invoker to declare the issues/branches it worked on this
  session and refuse those;
- state in each review body that beyond this, separation is honor-system.

## 4. Policy v7 — two review tiers, chosen by content

Replaces the binary (fast-lane/chore self-merge vs. full review). Consolidate
rule 6 to ONE canonical statement in `policy/AGENT_WORKFLOW.md`; mirrors get a
pointer plus one-line summary, not a fourth copy of the tier table.

- **No-diff-review lane (exists today):** chore lane, fast-lane. Unchanged.
  For PRs containing regenerated artifacts, the PR body MUST name the committed
  command that produced them — a statement a reviewer can spot-check, shipping
  today, instead of the digest gate (filed separately, see below).
- **Tier B — targeted review:** everything else below the Tier C bar. One pass
  over the reviewable files only, one review object, author may not merge.
- **Tier C — full independent review:** any of — touches a hazard path (CI
  recipe or gate, data format, export path, public interface, shared test
  fixture); reviewable churn > 500 lines; > 15 reviewable files; large net
  deletions. Absolute numbers, re-derived deliberately at policy-version
  bumps, never self-adjusting. The hazard-path list does the real work:
  #116 and #115 are Tier C on hazard paths alone.

`/open-pr` stamps the computed tier + churn split into the PR body at open
time, so the tier is a recorded fact, not a reviewer's judgment call.

## 5. The merge gate, in the file that actually merges

`/finish-task` only merges fast-lane/chore PRs (gating there is dead code —
audited). The gate belongs where strict-lane merges actually happen: the
*reviewer* merges on an `approve` verdict, so `/review` itself refuses to
merge when `reviews.totalCount == 0` or the newest verdict line isn't
`approve`. Retro query becomes: strict-lane merged PRs with zero review
objects — target 0.

## 6. Provenance digest gate — filed, not built

Its own issue, acceptance criteria = the five prerequisites above. Built only
if the generators prove byte-deterministic; runs in `ci-deep` if ever.

---

## Sequencing constraint

Nothing here lands until the currently-uncommitted kit WIP (policy v6, /triage,
chore lane, adoption manifest, `_require-*`) is repaired, committed, and
`sync-policy`-swept across active repos. A v7 written against an unreviewed v6
tree inherits its defects. (This was the original plan's "committed-pending"
euphemism — the tree was 11 modified + 2 untracked, zero committed.)

## How to tell it worked (re-run in ~2 weeks)

- Zero strict-lane PRs merged with `reviews.totalCount == 0` (baseline: all 78).
- No Tier C-qualifying PR (hazard path or >500 reviewable lines) merges
  without a review object naming its reviewable files (baseline: #116, #115).
- Reviewed reviewable-churn exceeds unreviewed reviewable-churn (baseline:
  inverted, ~54k vs ~161k raw).
- `reviewable-churn.sh` output on any PR matches what a human reads off the
  diff — the definition drift measured at 22% goes to ~0 by construction.
