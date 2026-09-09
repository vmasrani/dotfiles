# Editorial stages — mining (2), story editing (3), critique (7)

All three roles are subagents. Model routing comes from `config/models.yaml` — never hard-code a model. Each subagent prompt must be self-contained: paste in the transcript chunk or manifest it needs; subagents do not inherit the orchestrator's context.

## Stage 2 — Candidate mining

Run `scripts/chunk_transcript.py` first; it produces overlapping chunk markdown files plus `coverage.yaml` proving no transcript range is skipped. Dispatch one miner subagent per chunk, in parallel, model = `roles.strong_reasoning`.

### The rubric — rewritten after it failed in the field

The first version of this rubric scored `hook, standalone, central_idea, payoff, edit_boundaries,
visual_potential, missing_context, redundancy, risk`. Twelve clips were produced from a David
Deutsch episode and the user rejected most of them as **"totally boring and irrelevant."**

The measured cause: **seven of those nine scores measure editorial hygiene** — is this thing
well-shaped, complete, non-repetitive, safe, cuttable — and **not one asks whether a stranger
would keep watching.** A tidy, self-contained, low-risk exposition of the law of the excluded
middle scores 9s across the board and is boring. That is exactly what shipped.

Worse, it inverted: a two-party argument scores *worse* on `standalone` and `edit_boundaries`
than a clean monologue, so the rubric actively selected against the best material in the room.
Measured across the selected segments: **85% one speaker, and half the clips contained no
disagreement at all — in an episode titled "Disagreeing about Belief, Probability, and Truth."**

**The disqualifying test, applied BEFORE any scoring:**

> Would somebody who has never heard of this guest keep watching for fifteen seconds?

A candidate that fails is not a low-scoring candidate. It is **not a candidate**. Definitional or
taxonomic exposition with no consequence and no opponent fails by default.

**What actually earns a clip** (the user's own GOOD verdicts, in order of observed power):

1. **Point → counterpoint → counter-counterpoint.** Somebody advances a position, somebody
   pushes back, the first answers. The single most-wanted shape.
2. **Disagreement out loud** — "what you actually said was wrong", "I was shaking my head".
3. **A standalone story** — scene, character, turn, payoff. Qualifies on its own with no
   disagreement at all. It must name what it is about: a story about an unnamed theorem was
   rejected precisely because the viewer cannot follow it.
4. **Real-world stakes** — money lost, people harmed, a decision that matters.
5. **Counterintuitive claims** that contradict what a normal viewer already believes.
6. **A quotable line** somebody could repeat to a friend. The unit of spread.

**The context rule — this is where the second round failed.** Eight of eleven proposed shorts came
back marked *"not enough context"*, *"needs a question to set this up"*, *"more setup needed"*.
They were cut to hit a duration, and the cut removed the question that made the answer mean
anything: a supermarket boss answering an accusation the viewer never heard; a challenge with the
reply trimmed off. **A candidate must include the setup that makes it comprehensible cold, even
when that makes it longer.** If the setup will not fit the format, the candidate is a clip, not a
short — do not compress an exchange until the counterpoint disappears.

### Two formats

| | orientation | duration | what it is |
|---|---|---|---|
| **short** | vertical 9:16 | **under 3 min** (sweet spot 60–110s) | one exchange or one story, complete |
| **clip** | horizontal 16:9 | **3–12 min** | a whole developed argument that can breathe |

Judge which format the material *wants*. All five long-form clips proposed in the second round
were accepted; most shorts needed lengthening. A long point-counterpoint is a clip, not a badly
trimmed short.

### Rights — the mask is not optional

Raw multitrack recordings contain material that never shipped. Measured on the Deutsch episode:
raw 6466.85s vs published 5521s — **946 seconds, ~16 minutes, never released**, and the guest had
editorial control and asked for removals, so the cuts are scattered internally rather than trimmed
from the head. A candidate was mined from pre-roll banter in which the guest negotiates the right
to say things and have them cut.

Run `scripts/rights_mask.py` against the published URL before mining. **Every candidate must lie
wholly inside a published span.** Visuals still come from the raw multitrack — that is where the
isolated per-speaker tracks are — but the published video is the authority on what may be *said*.

### Disfluency editing is allowed

Stutters, filler and abandoned starts may be marked for REMOVAL, listed as exact spans to cut.
Never change a word that was actually said — this is trimming, never paraphrase. Each cut becomes
its own timeline segment.

### Miner prompt template

> You are a clip editor mining a podcast transcript chunk. The chunk covers source time
> {start}–{end} and overlaps its neighbours, so edge moments are visible to another miner —
> propose them anyway; dedup happens downstream.
>
> Apply the disqualifying test first: **would somebody who has never heard of {guest} keep
> watching for fifteen seconds?** If no, do not propose it at any score.
>
> Then look for, in order: point-counterpoint-counter exchanges; disagreement stated out loud; a
> self-contained story that names what it is about; real-world stakes; counterintuitive claims; a
> quotable line.
>
> **Include the setup.** A candidate that starts mid-answer, with the question cut off, is a
> failed candidate no matter how good the answer is. Prefer running long over running
> incomprehensible; if the setup will not fit under three minutes, mark it `format: clip`.
>
> Every candidate must lie wholly inside a published span from `rights-mask.yaml` — material cut
> before publication cannot be used, whatever its quality.
>
> **Quality over quota.** Five excellent candidates beat fifteen adequate ones; the failure this
> rubric replaces was volume of well-formed mediocrity. If the chunk contains nothing that passes
> the stranger test, return nothing and say so.
>
> For each candidate emit the schema entry you have been given, including `format`, `structure`,
> `why_watchable` (concrete — what makes a stranger stay), `quotable_line`, `disfluency_cuts`, and
> the COMPLETE `verbatim` text. The verbatim text is what a human reads at gate 1; a summary in
> its place defeats the gate.

Paste the relevant `candidates.yaml` schema block from `references/schemas.md` into every miner prompt.

### Merge step (orchestrator)

Concatenate all miners' candidates into one `candidates.yaml`, assign final sequential IDs, keep the coverage block from `chunk_transcript.py`. Candidates from overlap zones proposed twice: keep the higher-scored duplicate, note the merge.

Then run `scripts/gate1_candidates.py <episode-dir>` — it renders **every candidate's complete
verbatim text** to `gate1-candidates.md`. That file, not a memo, is what the human reads at gate 1.

The run this rubric replaces approved twelve clips from a selection memo listing titles, durations
and one-line summaries, then carried all twelve through storyboarding, B-roll research, critique,
forced alignment and roughly two hours of serialized rendering before anybody read their words.
Most were then rejected on sight. **Reading the text is the cheapest possible moment to say no,
and it was the one step the pipeline skipped.**

## Stage 3 — Senior story editing

One subagent, model = `roles.strong_reasoning`, highest reasoning effort available. Give it: full `candidates.yaml`, the complete segment-level transcript (`transcript.md`), and the schema for `clip.yaml`.

The senior editor:

1. Re-reads every candidate against the actual transcript — miners saw chunks; the editor sees the whole.
2. Rejects weak, repetitive, misleading, or context-dependent candidates, writing `verdict: rejected:<reason>` back into `candidates.yaml`.
3. Hunts for strong moments the miners missed (especially arcs crossing chunk boundaries).
4. Chooses the final set on quality alone — three great clips beat eight passable ones, and twelve genuinely strong ones is also a valid answer.
5. Designs cuts-within-cuts: removing a tangent, a false start, or redundant setup is encouraged when it tightens the story **without changing meaning**. Every internal cut becomes a separate timeline segment with its own source range.
6. For each selected clip, drafts the initial `clip.yaml` with: clip block (logline, audience_response, hook, payoff), full `timeline` (source/output time systems both populated, verbatim `dialogue` per segment copied from the transcript words, speaker, `visual.kind: aroll` placeholders), and status `proposed`.

The editor must verify each segment's `dialogue` against the word-level transcript — paraphrased dialogue in the manifest breaks subtitle alignment later.

### Editor output contract

Returns: updated `candidates.yaml` (verdicts filled), one `clips/<slug>/clip.yaml` per selection, and a selection memo (per clip: the idea, intended audience response, hook, payoff, and why any internal cuts are meaning-preserving).

## Human approval gate 1

Present to the user: the selection memo, per-clip duration, and the rejected-candidate list with reasons (so the human can rescue one). Use AskUserQuestion with multiSelect over the proposed clips when the list is short; otherwise present `candidates.md` and ask which slugs to produce. **Nothing downstream of this gate runs until the user picks clips.** No B-roll research, no licensing, no downloads — those spend money and API quota on clips that may be cut.

Record approved slugs by setting `clip.status: approved_edit`; delete or leave `proposed` the rest (leave — they're cheap and the user may return).

## Stage 7 — Independent critique

One subagent per clip, model = `roles.critic`. Independence is the point: give the critic ONLY the artifacts (clip.yaml, storyboard.md, the transcript excerpt covering the clip's source ranges ±60s, the asset manifest entries) — never the director's or editor's reasoning, and never run the critic as a fork of the session that authored the storyboard.

The critic checks: hook speed; whether internal cuts preserve meaning (against the surrounding transcript); whether the ending lands; whether visuals support rather than distract; B-roll relevance and license fields; visual-variation pacing; subtitle readability and restraint; thumbnail accuracy.

Every finding must be classified — `blocking` | `recommended` | `optional` — and must name the affected segment/asset ID and propose a concrete correction. A finding without a proposed fix is returned to the critic once for completion.

### Revision loop

Maximum **two** critique→revise rounds per clip:

1. Round 1: critic reports → director/editor subagent revises manifest+storyboard → re-run `validate_clip.py`.
2. Round 2: same critic (SendMessage to the same agent so it keeps context) verifies fixes and may raise NEW blocking findings only for regressions.
3. Still-disputed items after round 2 are not argued further — they go to the human at gate 2, presented as "unresolved creative disagreement: critic says X, director says Y".
