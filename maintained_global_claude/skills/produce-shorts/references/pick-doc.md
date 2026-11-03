# Stage 1 — the pick doc, the comment loop, survivors, and the freeze

## 1. What earns a pick — the editorial rules

These rules come from two rejected production runs. The first shipped twelve tidy, self-contained,
low-risk monologues that the user called "totally boring and irrelevant": the old rubric scored
editorial hygiene (well-shaped, cuttable, non-repetitive) and never asked whether a stranger would
keep watching, so it actively selected *against* arguments — 85% of segments were one speaker, in an
episode titled "Disagreeing about…". The second cut answers away from their questions to hit a
duration; eight of eleven came back "not enough context".

**The disqualifying test, before anything else:**

> Would somebody who has never heard of this guest keep watching for fifteen seconds?

Fail → not a pick at any length. Definitional or taxonomic exposition with no consequence and no
opponent fails by default.

**What earns a pick**, in order of observed power:

1. **Point → counterpoint → counter-counterpoint.** Somebody advances a position, somebody pushes
   back, the first answers. The most-wanted shape.
2. **Disagreement out loud** — "what you actually said was wrong", "I was shaking my head".
3. **A standalone story** — scene, character, turn, payoff — that names what it is about.
4. **Real-world stakes** — money lost, people harmed, a decision that matters.
5. **Counterintuitive claims** that contradict what a normal viewer already believes.
6. **A quotable line** somebody could repeat to a friend.

**Open on the question.** The interviewer's question or challenge is the first thing a viewer
hears. A proposal whose first words are an answer, or point backwards ("as Ozzie said", "I'm a big
fan of it", a mid-sentence start), is moved back to the nearest real question before it is shown;
the exact start is then settled in stage 2 (`references/refinement.md`).

**Include the setup.** A pick that starts mid-answer with the question cut off has failed, however
good the answer. Prefer running long over running incomprehensible. If the setup will not fit under
three minutes, it is a **clip**, not a short — never compress an exchange until the counterpoint
disappears.

**End on the punch.** The last words of every pick are the payoff, the turn, or the quotable line
(a punchy line or a concession from the host beats a recap).
Never end on "…and so, yeah", a trailing qualifier, or the first words of the next thought. Name
the ending line in the label (`ends on:`) so the user can judge it at a glance.

**Formats.** Short: vertical, **under 180 s** including cuts removed (hard limit), sweet spot
60–110 s. Clip: horizontal, any length, typically 3–12 min. Judge which format the material wants;
a long point-counterpoint is a clip, not a badly trimmed short.

**Quality over quota.** Rank everything; propose roughly 3–6 shorts and 1–3 clips, best first. An
episode with two genuinely good picks gets two.

**Trimming inside a pick** is allowed for stutters, filler, abandoned starts, or a tangent — mark
the removed words as a cut. Never change or reorder words that were said. A pick may splice in a
second region from elsewhere in the episode (a definition, an earlier claim); regions always play
in source order.

**Know what is already out.** Before picking, run `published_shorts.py match EPISODE_DIR`: it
lists the channel's already-published shorts whose transcripts overlap this episode, with their
source time ranges. Overlap is allowed, not forbidden — a new pick may cover the same moment if it
does it in a new way (different boundaries, a different angle, the counterpoint the published one
left out). But it must be a deliberate choice: a pick that overlaps a published short says so in
its `why` and how it differs, and the doc label carries `⚠ overlaps "<published title>"`.

**No overlaps between picks.** A word belongs to at most one pick. If a short lives inside a clip, propose the
better of the two and mention the other in its `why`.

## 2. The editor dispatch

One subagent, `subagent_type` from `config/models.yaml` `editor`. It gets the complete
`transcript/transcript.md` (speaker-labelled, timestamped turns), the speaker names, the episode
title, `rights-mask.yaml` if present (every pick lies wholly inside a published span), the
`published_shorts.py match` output, §1 above verbatim, and the `draft-picks.json` format below. It writes `review/draft-picks.json` and returns
a ≤10-line summary. One editor reading the whole episode — never chunked miners; arcs that cross
chunk boundaries were the first thing the chunked design lost.

## 3. `review/draft-picks.json` — the editor's one-shot input to the doc

Consumed once by `build_pick_doc.py`; after the doc exists it is never read again.

```json
{
  "picks": [
    {
      "id": "S1",
      "format": "short",
      "title": "The supermarket boss who couldn't answer",
      "why": "Ben accuses, Kasra concedes, then flips it — a full point/counterpoint in 90s.",
      "regions": [
        {
          "start": 734.2, "start_words": "But if you actually look at",
          "end": 851.0,   "end_words": "and that's why it fails."
        }
      ],
      "cuts": [
        {"start": 790.1, "words": "you know, um, the the"}
      ]
    }
  ]
}
```

- `id`: `S<n>` for shorts, `C<n>` for clips, numbered in rank order.
- `start_words` / `end_words`: the first and last ~5 words of the region, verbatim. The builder
  snaps each region to word indices in `transcript.json` by searching near `start`/`end` (±5 s)
  for that word sequence and **fails loud** if it is not found or found twice.
- `cuts`: optional; each is a verbatim word run inside a region, located the same way.
- Builder validation (all fail loud, naming the pick): unknown format, id prefix ≠ format, overlap
  between picks, a short whose kept duration ≥ 180 s, a cut outside its pick's regions.

## 4. The pick doc

`build_pick_doc.py EPISODE_DIR` renders HTML and uploads it with conversion
(`gog drive upload --convert`) into the episode's Drive folder (`review.drive_folder` in
`config/defaults.yaml`, under a subfolder named for the episode). It records
`review.pick_doc {id, url}` and the pick → colour map `review.picks` in `episode.yaml`.

Layout, top to bottom:

1. **Title** `<episode title> — picks`, then a one-paragraph **key**: how to comment (§5), what
   colours, grey, and strikethrough mean.
2. **Status list** — one line per pick, on the pick's colour:
   `S1 · SHORT · 1:28 · PROPOSED — The supermarket boss who couldn't answer`.
3. **The transcript**, complete, in source order, spaced for reading:
   - A bold **speaker header** `[17:32] David` whenever the speaker changes; that speaker's speech
     follows as short paragraphs (split at sentence boundaries every ~20–30 s), each continuation
     paragraph opening with a tiny grey timestamp (`17:58`). Short backchannels from another
     speaker (≤ 4 words or < 1.5 s) sit inline as `(Ben: Hmm.)` in small type.
   - Words outside every pick: grey text (`review.grey`), fully readable.
   - Words inside a pick: dark text on the pick's background colour.
   - Words cut from inside a pick: the pick's background **and** strikethrough.
   - **Label line** immediately before each pick's first region, kept short:
     `▶ S1 · SHORT (vertical) · 1:28` (suffix ` · ⚠ published` when it overlaps a published
     short); later regions get `▶ S1 · region 2`. Labels always start with `▶ ` — that prefix is
     how the freeze and `doc_ops.py` tell labels from transcript text. Published-short spans no
     pick covers get a small grey `· published as "<title>"` marker.

**The doc carries no rationale.** Each pick's why, regions, ending line and published-overlap
details are internal: they live in `episode.yaml` `review.picks.<id>` (`doc_ops.py show S1`),
kept current by every edit. Mention them in comment replies when they help the user decide.

**Raw multitrack sources** (`rights-mask.yaml` present): the full transcript is still shown, but
stretches outside every published span render grey italic with strikethrough, preceded by a
`· not published (mm:ss–mm:ss)` marker. The builder, every `doc_ops.py` edit, and the freeze fail
loud if a pick region leaves a published span.

Each pick gets a distinct colour from `review.palette`. Freeze and `doc_ops.py` identify a pick's
words **by their background colour**, so colours are never reused within one doc.

## 5. The comment loop

How the user comments (this text is in the doc's key):

- Highlight transcript text → comment. Plain language works: "start here", "end after this",
  "include up to 14:10", "cut this", "keep this", "drop", "approve", "new short: this exchange",
  "make this a clip".
- Highlight at least ~5 words so the passage is unambiguous.
- Comment on a label or status line to talk about the whole pick.

When the user says "check the doc":

1. `doc_ops.py comments EPISODE_DIR` — every open comment thread, with the quoted (highlighted)
   text, the full reply chain, and the comment's resolved word range (`locate` run on the quote).
2. For each thread, decide the edit and apply it with `doc_ops.py`:

   | user intent | command |
   |---|---|
   | move start/end | `range S1 --start-word I --end-word J` (whole first/last region) |
   | cut / un-cut words | `cut S1 --from-word I --to-word J` / `uncut …` |
   | add a region | `add-region S1 --start-word I --end-word J` |
   | new pick | `add S4 --format short --start-word I --end-word J --title "…"` |
   | change format | `format S2 clip` (renumbers the id: S2 → next free C<n>) |
   | drop / approve / reopen | `status S1 dropped|approved|proposed` |

   Word indices come from `doc_ops.py locate EPISODE_DIR "<quoted text>"`, which returns the
   unique word range of a quote (or fails loud when absent or ambiguous). "Include up to 14:10"
   → `locate --time 850` returns the word index at that time. Snap starts to a sentence or turn
   start and ends to a sentence end unless the user pointed at an exact word.
3. Every command re-applies the pick's colours and rewrites its label and status line (times,
   duration, ends-on) in place, so the user's other comments stay anchored. Commands enforce the
   §3 validation rules (no overlaps, short < 180 s) and fail loud instead of applying.
4. `doc_ops.py reply EPISODE_DIR COMMENT_ID "<what changed>"` then `resolve`. Reply concretely:
   "S1 now 12:02–13:42 (1:40), starts on Ben's question." A question back to the user: reply,
   do **not** resolve.
5. Append one line to the doc's revision-log thread (`doc_ops.py log`): `Rev N — addressed X,
   open Y`. Tell the user the same line in chat.

The editor's judgement also applies on your own edits: after moving an end, re-check that the new
last line is still a punchy ending, and say so in the reply if it is not.

## 6. Survivors and the freeze

The owner trims the proposals by comment ("drop", "start here", "end after this") or simply by
removing a pick's highlight/words from the doc. When he says he is done, the **survivors** are the
picks still coloured in the doc: confirm with `doc_ops.py show`, mark each survivor
`doc_ops.py status PICK approved` and every other pick `dropped`, then
`freeze_picks.py EPISODE_DIR`.

It reads the doc (Docs API `documents.get`), aligns the doc's transcript text to `transcript.json`
words (`▶` labels, `· published as` markers, status lines, key, speaker headers and continuation timestamps
excluded), and for each approved
pick colour builds the kept word ranges (coloured, not struck through). It writes
`clips/<slug>/clip.yaml` (schema in `references/schemas.md`): one timeline segment per contiguous
kept run, split further at speaker changes in time (word-midpoint) order — where speakers talk
over each other (multitrack) the cut sits between the two groups' midpoints, and a word that cannot
keep half its duration in a segment of its own speaker (typically a backchannel force-aligned across
the other speaker) stays in the audio uncaptioned and is logged as a warning; `dialogue` copied verbatim from the words; source
times from word timestamps with a small pad (`review.boundary_pad_s`) that never crosses into a
neighbouring word; `visual.treatment` defaulted to `closeup-<speaker>` (shorts) or `source-frame`
(clips), refined by `plan_framing.py`. Then it runs `validate_clip.py` on each clip and sets
`status.stage: frozen`.

It refuses (nonzero) when: any pick is still `proposed`, the doc text no longer aligns to the
transcript (somebody edited the words — the error names the paragraph), a pick colour appears that
is not in `review.picks`, or a short's kept duration is ≥ 180 s.

After the freeze the doc is read-only history. The pick's exact start, end, cuts and overlays are
settled **in chat on `clip.yaml`** (stage 2, `references/refinement.md`) — not by re-opening the doc.
Picks the owner drops during refinement move to `dropped-clips/`.
