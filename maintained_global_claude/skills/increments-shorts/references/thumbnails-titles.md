# Thumbnails, titles, descriptions — the channel's voice

Read before step 6 of the interview. Defaults learned from the channel owner; the user may override any of them.

## Title

Short, plain-spoken: a flat claim with an edge, or a straight question. **Never teaser-bait** ("You won't believe...").
Real examples: "The shady history of Effective Altruism" · "Calling Math True Is A Category Error" · "Does P(doom) make any sense?" ·
"It sucks to be a doomer" · "Iraq was not a war for oil" · "Longtermism is a wicked idea" · "Judge an idea by the crazies it
produces" · "What do you say if Reagan asks you the probability of nuclear war?". Max 100 characters.
**No hashtags in the title** — they cost title characters and read as spam; the three hashtags live in the description
(YouTube shows the first ones above the title anyway).

## Description (links + hashtags only, no commentary)

```
Full episode: <episode url>
Blog post: <url>            <- only when the short quotes that post
Increments Podcast: https://www.incrementspodcast.com

#Hashtag1 #Hashtag2 #Hashtag3
```
`deliver.py` builds exactly this (`--blog` adds the middle line; exactly three `--hashtag`s).

## Thumbnail text

- **Complementary to the title, never a repeat.** 1-3 words per line that trigger emotion or attention:
  "I DON'T KNOW.", "TEAM MOSQUITO", "MATH PROVED GOD?", a crossed-out "LONGTERMISM" (`strike: true`).
  `thumbnails.py` rejects text that repeats the title or runs over 3 words per line.
- **Vary who is on each thumbnail across a batch** — guest alone, host alone, both in a diagonal split (`split`),
  two circles (`circles`), or no face + a real quote screenshot (`quoteshot`) — so the channel doesn't repeat itself.
- **Clean source frames** (the script grabs them from the source video, so no burned captions), 1080x1920, picked where the
  person looks into the lens or makes an expressive face. Text never covers eyes (styles keep text in the top ~40% / bottom 25%).
  Find candidate frames with `sample_frame.py`, look at them, then set `frame: {t: <seconds>, tile_x: <gallery tile left edge>}`.
- Styles (`style:` in `thumbnails.yaml`): `bw` (B&W + yellow text, optional red strike) · `color` · `stack` (white line over red
  block) · `banner` (yellow banner) · `sticker` (tilted sticker) · `quote` (quote card) · `split` (two faces + VS) ·
  `circles` · `quoteshot` (real quote screenshot card + face). Propose 2-3 options per short and let the user choose.
- Quote screenshots must be real and credited (provenance entry); prefer the guest's own blog post over a paper.

## Final approval gate (step 7)

One markdown table, one row per short, title and thumbnail text side by side, then the contact sheet image:

| short | title | thumbnail text | options on the sheet |
|---|---|---|---|

The user picks/edits per short; only then render finals. After upload: set Studio's **Related video** to the full
episode (the only tappable link from a Short); the Shorts feed may ignore custom thumbnails.
