# Horizontal clips — intro, name tags, pips, quote screenshots

The template the owner approved is the Bayesian Conspiracy clip C4
(`clips/yudkowsky-says-rationality-is-law-vaden-that-s-what-i-reject/clip.yaml`, 5:08). Every
horizontal clip follows its recipe; deviations are the owner's call. Overlays live in
`clip.yaml overlays:` (schema: `references/schemas.md` § Overlays); every file in `broll/` needs a
`broll/provenance.json` entry; **no AI-generated imagery, ever**. Output times are OUTPUT seconds.

## Trimmed C4 overlay track

```yaml
broll: {provenance: broll/provenance.json, protected_tail_s: 62.0}   # last 62 s: no fullscreen cutaway
overlays:
  - {id: P0, mode: fullscreen, start: 0.0, end: 5.0, fade_out_frames: 24,        # intro picture
     shots: [{asset: intro.mp4, src_in: 0.0, src_out: 5.0}]}
  - {id: T0, mode: card, start: 0.4, end: 4.7, placement: title-center,          # intro title
     reveal: words, reveal_s: 1.4, fade_in_frames: 8, fade_out_frames: 10,
     lines:
       - runs: [{text: THE BAYESIAN CONSPIRACY, color: accent, weight: 800}]
       - runs: [{text: Eneasz Brodsky & Steven Zuber, at: 0.7}]
       - runs: [{text: with Vaden Masrani, color: muted, at: 1.3}]}
  - {id: T1, mode: lowerthird, start: 5.3, end: 9.3, placement: tile-left, fade_in_frames: 6, fade_out_frames: 8,
     lines: [{runs: [{text: Eneasz Brodsky}]}, {runs: [{text: "co-host, Bayesian Conspiracy", color: muted}]}]}
  - {id: T2, mode: lowerthird, start: 9.6,  end: 13.6, placement: tile-right, ...}   # Steven
  - {id: T3, mode: lowerthird, start: 60.8, end: 65.3, placement: tile-mid, ...}     # Vaden: tag when he first speaks
  - id: P1                                  # person named -> real credited photo, over a NON-speaking tile
    mode: pip
    start: 83.6
    end: 86.5
    box: {x: 1380, y: 140, w: 440, h: 550}          # 4:5 photo, right tile
    from_box: {x: 1545, y: 346, w: 110, h: 138}     # grows out of the speaker's face
    move_frames: 10
    label: Sam Bankman-Fried
    fade_in_frames: 4
    fade_out_frames: 6
    shots: [{asset: sbf.jpg, zoom: [1.0, 1.04]}]
  - id: P2                                  # face + their major book (grid 2x1, book pops in 0.6 s later)
    mode: pip
    start: 88.5
    end: 93.8
    box: {x: 40, y: 150, w: 712, h: 440}
    label: "William MacAskill · What We Owe the Future"
    shots:
      - grid: {cols: 2, rows: 1, tiles: [{asset: macaskill.jpg, at: 0.0}, {asset: book-macaskill.jpg, at: 0.6}]}
  - id: B1                                  # guest READS a quote -> original-source screenshots, one per passage
    mode: fullscreen
    start: 121.8
    end: 168.1
    fade_in_frames: 8
    fade_out_frames: 8
    shots:
      - {asset: q1.png, at: 0.0,   crop: "x=607:y=481:w=2400:h=1350", zoom: [1.0, 1.03]}
      - {asset: q2.png, at: 11.25, crop: "x=607:y=481:w=2400:h=1350", zoom: [1.0, 1.03], dissolve_frames: 6}
      # … q3, q4, q5a, q5b — each `at` is the second he starts reading that passage
  - {id: T4, mode: lowerthird, start: 198.8, end: 204.0, placement: tile-mid,
     lines: [{runs: [{text: "Cox's theorem"}]}, {runs: [{text: "R. T. Cox, 1946", color: muted}]}]}
  - {id: P6, mode: pip, start: 253.6, end: 258.6, box: {x: 100, y: 140, w: 440, h: 550},
     shots: [{asset: bulldog.png}]}         # owner-supplied screenshot, as-is, timed to the claim it backs
```

## Intro (P0 + T0)

- **P0** is a 5 s picture: the clip's opening footage, blurred and darkened, with the show's cover
  art faded in at centre top. Build it once per clip with ffmpeg-full:
  `-ss <clip source_in> -t 5.2 -i source/episode.mp4 -an -vf "scale=1920:1080,gblur=sigma=28,eq=brightness=-0.10:saturation=1.15,vignette=PI/4.5,fps=30,format=yuv420p" -c:v libx264 -crf 14 -preset slow`,
  then overlay the cover art (scaled to 380 px, fade in) → `broll/intro.mp4`. Provenance: the
  episode footage (owner's / guest-appearance source URL) plus the cover art's own entry (its source
  and licence). The art must be the show's real cover, never generated.
- **T0** is the word-revealed title card: `<SHOW> / <hosts> / with <guest>`; for the owner's own
  Increments episodes use the Increments branding and no "with" line.
- **Do not hand-type T0 or the tags.** Fill `episode.yaml show:` and run
  `scripts/intro_overlays.py CLIP_DIR` (print) then `--apply`. It also writes T1…: one lower-third
  per speaker at first appearance, staggered so the text layer never overlaps itself.
  P0 is the one part it does not generate.

## Name tags and gallery layout

Tags sit on the speaker's own tile (`tile-left|mid|right`, geometry in `config/defaults.yaml
broll.text.placements`). The layout can change mid-episode, so the tile is read from
`episode.yaml layout_timeline` at the SOURCE time of the speaker's first segment — never assumed
from another clip. Example, Bayesian Conspiracy: before ~2800 s Eneasz left / Vaden mid / Steven
right; after it Vaden left / Steven mid / Eneasz right. Detect changes from face tracks, confirm
with extracted source frames on both sides of the change, then record them. Tag everyone early
(first ~15 s), guests at their first line.

## Pips (people, books)

- A named person gets a **pip** with a real, credited photo (Wikimedia Commons or the person's own
  press photo; 4:5 crop, e.g. 440x550), and **their major book beside the face** (grid 2x1 with
  the book card 1040x1300: blurred cover background + cover with drop shadow).
- Place the pip over a tile whose person is **not speaking** (and not on the name tag's tile while
  the tag is up); `from_box` at the speaker's face makes it grow out of the mouth that named them.
- 3-6 s on screen, `fade_in_frames: 4`, `fade_out_frames: 6`. Credits go in `broll/ATTRIBUTION.txt`
  for the video description.

## Quote screenshots (guest reads a quote)

1. Find the **ORIGINAL source** of the passage he reads. If the page changed since (blog edited,
   paper revised), use the archived version from the time it was written (web.archive.org, e.g.
   the 2019 GPI paper). Save the raw capture in `broll/orig/`.
2. **Verify the wording against what he actually reads** (transcript words) and report every
   difference to the owner before rendering.
3. Capture one still per passage with a mouse-selection-style **highlight advancing sentence by
   sentence** as he reads, and a drawn cursor (Playwright/headless Chromium at ~1.5x; a selection
   range over the passage, cursor SVG at the selection end). Record the highlight box in
   `broll/highlight_boxes.json` and the page URL + quoted text in provenance `notes`.
   The capture script is per-clip scratch work today (not packaged in `scripts/`).
4. `fullscreen` overlay, one `shots:` entry per passage, `at` = the second he starts that
   passage, `crop` to the text column, `zoom: [1.0, 1.03]`, `dissolve_frames: 6` between passages.
   Keep it out of the protected tail.
5. **Fallbacks, in order, when no legible real page exists:** the owner's own show-notes page that
   quotes it (own-show episodes: the episode page on the show's site), then a **typeset quote
   card** with a citation (real text, real attribution). Never generated imagery.

## Owner-supplied screenshots

Use as-is, one per claim, timed to the line it backs (the Bentham's Bulldog probability claims:
`bulldog.png`, `P6`). Do not recrop or restyle; give each a provenance entry (source URL,
"owner-supplied", licence "all rights reserved" if so).

## Checks before rendering

`validate_clip.py CLIP_DIR` (overlay invariants, provenance), then render and extract frames at
every overlay entry: right person per speaker, tags on the right faces (check once on each side of
a layout change), pip not covering a speaking face, highlight legible, protected tail clean.
