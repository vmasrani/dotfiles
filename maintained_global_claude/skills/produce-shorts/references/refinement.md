# Stage 2 — per-pick refinement in chat

This loop is what the owner values most. It runs once per frozen pick, in chat, before anything
renders. The pick doc says *which* exchange; this loop fixes *exactly where it starts and stops*
and what happens inside it. Every change is an edit to the pick's `clip.yaml` (re-flow
`output_in/out`, `output.duration_s`, then `validate_clip.py`), applied only after the owner says
which option he wants. Do one pick at a time; show the next pick only when the owner moves on.

Edit tooling: there is no dedicated re-range script yet. Use a short throwaway script (scratchpad,
never the skill dir) that loads `clip.yaml` with `pslib.load_clip`, changes `source_in/out` on
word boundaries from `transcript.json`, rewrites `dialogue` from the transcript words in range,
re-flows the output times (each segment starts where the last ended) and saves with `save_clip`.
Keep `clip.pre-<change>.yaml` copies. Segment ids are never renumbered: new segments take new
ids (`S99`, …).

## 1. Opening — the clip must start on a question or challenge

For every candidate show the **first lines and last lines**, speaker-labelled, with source
timestamps:

```
S13 · What would you do in Reagan's office about the Soviets?   2:08   16:44-18:55
OPENS   [16:44] Eneasz: Yes. Okay. But again, if someone came to you and said ...
CLOSES  [18:49] Vaden: ... that indicates that they're — starting to dig uranium.
```

Rules:

- Every clip opens on the **interviewer's question or challenge**. If it opens mid-answer, move
  the start back to the nearest real question and show the new opening for confirmation.
- Avoid openers that point at something before the clip: "I'm a big fan of it", "as Ozzie said",
  "Yes. Okay. But again, …", any mid-sentence start. Trim the leading filler word run (and
  re-capitalise the first remaining word in `dialogue`) rather than start on the throat-clear.
- State what you changed and the new duration in one line.

## 2. Ending — offer lettered candidates, recommend one

Show about **one minute of text after the current end**, then offer 2-3 lettered candidate
endings, each with the exact last line, the timestamp and the resulting duration, and **a
recommendation**:

```
Current end (2:08)  "... starting to dig uranium."
Next minute: [18:55] Eneasz: Okay, but that's a narrow case ...

A  stay: "... starting to dig uranium."                                  2:08
B  +0:09 Eneasz concedes: "Fine, that one I'll give you."                2:17   <- recommend: host concession lands the point
C  +0:34 Vaden's recap: "... so you don't need a number."                2:42
```

Preference order: a **punchy line** (quotable, ends the argument) or a **concession from the
host**; never an ending that trails into the next topic or the first words of a new thought.
Stay under 3:00 for a short; if the best ending pushes past it, say so and offer the clip format.

## 3. Full text on request

When asked ("show me the whole thing"), print the pick's complete text, **speaker-labelled with
output-time timestamps** (the time the viewer will see it, not the source time), merging
consecutive same-speaker segments into one paragraph:

```
[0:00] Eneasz: Yes. Okay. But again, if someone came to you ...
[0:21] Vaden: So what you do is you don't put a number on it. You get spies ...
[1:04] Eneasz: ...
```

## 4. Cuts, pauses, reactions

- **Interruptions and crosstalk** ("No, I wasn't", "wait, wait") are cut when the owner asks.
  Cut on **word gaps** from the transcript. Say whether the cut was checked only by energy (RMS
  in the gap) or by ear/waveform; a cut verified only by energy is flagged as unheard.
- **Keep meaningful silences.** A long pause before a concession stays — a restored 8 s pause was
  shown as a split screen of the two reacting hosts (a `locked` split-screen segment with an empty
  `dialogue`, reason "owner: restored dramatic pause").
- **Hide distracting reactions** (the guest shaking his head while the host speaks): switch the
  asker's lines to a **solo close-up** and lock it: `visual.treatment: closeup-host1`,
  `locked: true`, `reason: "owner: Eneasz speaks, solo close-up (hides listener head-shake)"`.
  `plan_framing.py` never changes a locked segment.
- **Muted tail.** A too-short final caption (under the minimum display time) is fixed by a short
  video-only tail: a segment with `audio: mute` that holds the speaker's closeup just after the
  last word (`reason: "tail hold: video-only filler"`). The audio still ends on the punch.

## 5. Overlap check against neighbouring picks

After every start/end change, compare the pick's source range with the picks before and after it
(`doc_ops.py show` / each `clip.yaml`). A word belongs to at most one pick. If a new ending
overlaps the next pick's start (S13's new ending overlapped S14's start), tell the owner and
**re-range the later pick** (move its start past the shared words, re-check that it still opens on
a question), or merge/drop one — his choice.

## 6. Housekeeping

- **Dropped picks** move to `dropped-clips/<slug>/` beside `clips/`; never deleted.
- **Caption name typos** are fixed in the clip's `dialogue` (captions come from it) — and in
  `transcript.json` if the typo is systemic; `validate_clip.py` invariant 11 fails when `dialogue`
  and the transcript disagree, so after a transcript name fix re-sync every clip's `dialogue`.
- **Quote layout candidates** (shorts): when the speaker quotes or paraphrases a page or claim,
  note the line and the source in the refinement summary; the capture happens at render time
  (`references/render-qc.md` § Shorts, `references/broll-horizontal.md` § Quote screenshots).
- When the owner confirms a pick, print its final one-line state:
  `S13 · 2:17 · opens on Eneasz's challenge · ends on his concession · no overlaps`.
