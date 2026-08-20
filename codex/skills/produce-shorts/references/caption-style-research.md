# Caption/subtitle style research — burned-in captions for vertical podcast clips (1080x1920)

Researched 2026-08-06 for produce-shorts. Goal: fix captions that are too small (~57px / 0.030 of
height) and bottom-anchored (occluded by mobile UI).

## Evidence

### 1. Font size (fraction of frame height)

- Rule-of-thumb used across broadcast/accessibility guidance: subtitle text height should be
  **1/20 to 1/10 of frame height** (0.05–0.10), floor ~44px at 1080p.
  [vsubtitle.com](https://vsubtitle.com/subtitle-font-size-and-reading-speed-2026/)
- Vertical-specific guidance (TikTok/Reels/Shorts): **36–48px, sometimes up to 60px**, on a
  1080-wide source — but this figure is usually quoted against **frame width**, not height, and
  reads low compared to the broadcast rule above. On a 1920-tall / 1080-wide frame, 48–60px ≈
  0.025–0.031 of height — i.e. close to what we already have and, per other sources, too small.
  [OpusClip](https://www.opus.pro/blog/tiktok-caption-subtitle-best-practices)
- Descript/creator-tool guidance for vertical short-form: **48–56pt**, similarly low if read
  literally in px against 1920 height.
  [vsubtitle.com](https://vsubtitle.com/subtitle-font-size-and-reading-speed-2026/)
- **Disagreement**: the broadcast/legibility literature (1/20–1/10 of height) and the "px" figures
  quoted by caption-tool blogs disagree by roughly 2x. This is very likely because caption-tool
  blogs are quoting *default/conservative* export sizes rather than what top-performing creators
  actually render — Opus Clip, Submagic, and CapCut karaoke templates in practice render noticeably
  larger, closer to 90–130px on a 1920 canvas (visually ~2-3 words filling most of the frame width).
  We could not find a single source publishing an exact px/height fraction for a specific viral
  template — this is a **stated gap**: no captioning tool publishes its literal font-size fraction.
- **Recommendation**: given the broadcast floor (0.05) and the visual density of actually-viral
  karaoke-style clips (words are big, ~2-4 per card, filling most of frame width), target the
  **upper part of the range: 0.06–0.075 of frame height** (≈115–145px at 1920). This is meaningfully
  bigger than your current 0.030 and bigger than the conservative 48-56px figures, matching what
  visually reads as "big TikTok captions" rather than a broadcast lower-third.

### 2. Vertical position / safe areas (YouTube Shorts UI)

Multiple safe-zone tools agree on similar numbers for a 1080×1920 frame:

- Usable/safe content area: **~900×1160px to ~900×1350px**, centered.
  [postplanify.com](https://postplanify.com/tools/youtube-shorts-safe-zone-checker), [youtubetoolkit.com](https://youtubetoolkit.com/blog/youtube-shorts-dimensions)
- Specific margins: keep critical text/logos **≥380px from top, ≥380px from bottom, ≥60px from
  left, ≥120px from right**. [youtubetoolkit.com](https://youtubetoolkit.com/blog/youtube-shorts-dimensions)
  - 380/1920 ≈ **0.198** top margin, **0.198** bottom margin.
  - Right-hand action rail (like/comment/share/subscribe): subscribe button alone ~180×80px in the
    bottom-right; rail generally consumes the right ~120px (0.111 of 1080 width) — wider (~15-18%
    of width) when accounting for the full vertical stack of icons.
  - Bottom bar (channel name, title, progress bar): grows to **~400px (0.208 of height)** when the
    description is expanded.
- TikTok-specific guidance (separate source): avoid **bottom 25%** of frame (UI clutter) and **top
  15%** (username/caption text baked in by TikTok itself); captions recommended at **60-70% of
  frame height from the top** — i.e. **center–lower-middle**, not true center and not bottom.
  [OpusClip](https://www.opus.pro/blog/tiktok-caption-subtitle-best-practices)

**Reconciling with the user's "mid-screen" preference**: the evidence confirms mid-screen is right
in spirit — bottom-quarter is unambiguously bad (UI band ≈0.20-0.21 of height on both YouTube
Shorts and TikTok). But "dead center" (50%) is not quite what the data says either — 60-70% from
top (i.e. **just below true center, in the lower-middle third**) is the specific zone multiple
sources converge on, since it stays clear of both the top username/title area and the bottom
UI/progress band while sitting where the eye naturally rests during talking-head content (near the
subject's chin/chest, not covering the face). **Flag: user asked for "middle of the screen" — the
evidence supports mid-to-lower-middle (60-70% from top), not exact 50%.** Both are viable; 50-58%
is a reasonable compromise if the pipeline wants one universal anchor that also clears typical
face/head framing in talking-head footage.

### 3. Words / characters per card

- Streaming-era standard (Netflix, referenced by YouTube guidance): **42 characters per line**.
  [vsubtitle.com](https://vsubtitle.com/subtitle-font-size-and-reading-speed-2026/)
- Short-form vertical practice trends much shorter per the "1-second read" rule: captions should be
  readable in under 1 second of focused attention at arm's length — in practice this means **short
  bursts, 3-8 words visible at once**, not full 42-char lines, since the font is much bigger and the
  frame narrower (1080px wide vs. a horizontal 1920px frame).
- **Lines per card**: dominant modern pattern (karaoke/Opus Clip/Submagic/CapCut style) is **1-2
  lines**, most commonly **1-2 short lines of ~2-5 words each**, refreshing frequently in sync with
  speech rather than showing long static blocks.
- **Gap**: no source gives an exact chars-per-line number specific to karaoke-style vertical
  captions (the 42-char figure is a horizontal/broadcast convention). Recommend a much lower
  practical cap given font size ~0.065 of height: **~14-20 characters per line**, **max 2 lines**.

### 4. Weight and case

- Dominant weight: **Bold / Extra Bold** — sources repeatedly cite "Montserrat Bold" as the de
  facto standard for Shorts/Reels/TikTok. [Blitzcut](https://blitzcutai.com/blog/best-caption-fonts-tiktok), [Kapwing](https://www.kapwing.com/resources/font-for-subtitles/)
- Case: most viral templates use **sentence case or Title Case**, not full uppercase — uppercase
  appears more in "meme-caption"/Impact-style templates, less in the modern karaoke-highlight
  style. No hard numeric data found; this is qualitative — noted as a gap.
- Letter spacing: no specific numeric guidance found (gap). Typical UI default is 0 to slightly
  tight tracking for bold condensed faces; not enough sourced evidence to give a number.

### 5. Legibility treatment (stroke/outline, shadow, plate)

- Simplest/most-cited approach: **2-4px dark stroke or drop shadow around light (white) text**;
  specifically "pure black outline, 2px stroke, white text" is called out as a common concrete
  spec. [legibility.info](https://legibility.info/rules-for-text-in-videos), [circletranslations.com](https://circletranslations.com/blog/subtitle-fonts-top-10-fonts-for-subtitles-and-closed-captions)
- Caution from the same research: **thick strokes eat the letterform** — a 4px stroke on a 24px
  font consumes most of the interior and makes the face read as heavier than it is.
  [toolboxhubs.com](https://toolboxhubs.com/en/blog/css-text-stroke-guide)
- Translating the "2-4px at ~24-48px font" ratio to a fraction: roughly **0.05-0.10 of font size**
  (e.g. 2px/24px ≈ 0.083, 4px/48px ≈ 0.083) — consistent across the cited range, giving a solid
  **~0.06-0.09 of font-size** target for stroke width.
  Applied to our recommended ~125px font: **~8-11px stroke**.
- Background plate: no numeric consensus found. Qualitatively, stroke+shadow (no solid plate) is
  the dominant style in Opus Clip/Submagic/CapCut karaoke templates — a solid background box is
  more associated with older/basic auto-caption styles (native TikTok/IG captions) than with the
  highest-performing custom styles. Treat "no plate, stroke+shadow" as the recommended default,
  contrast-with-underlay only as a fallback for busy backgrounds.

### 6. Emphasis / karaoke word-highlight

- Word-by-word ("karaoke") highlighting — each spoken word lights up / changes color as it's said —
  is explicitly described as standard in both Opus Clip and Submagic, and credited with improving
  watch time. [OpusClip help](https://help.opus.pro/docs/article/change-captions), [toolcrush.io](https://toolcrush.io/blog/how-to-use-submagic-to-add-ai-captions)
- Opus Clip also supports "AI keyword highlighters" — color-emphasizing specific *keywords*
  (not just literally the currently-spoken word) — a related but distinct pattern from strict
  per-word karaoke timing.
- **Gap**: no source gave a definitive list of the single most common highlight colors. Commonly
  observed/cited in creator tooling (not independently verified numerically here): bright
  yellow, green, or a saturated accent (e.g. #FFD400-ish yellow, or brand-accent colors) against
  white base text — flagged as qualitative/anecdotal, not sourced to a hard figure.
- **Recommendation given the gap**: per-word (or per-2-3-word) highlight in a single bright accent
  color is the norm — treat this as a MUST-HAVE for matching top performers, but leave the exact
  hex as a configurable/brand choice rather than inventing a "standard" color.

### 7. Font families

- **Montserrat Bold** — repeatedly named as the current go-to for Shorts/Reels/TikTok captions.
  Free (Google Fonts, SIL Open Font License). [Blitzcut](https://blitzcutai.com/blog/best-caption-fonts-tiktok)
- Other sans-serifs cited as broadly good for on-screen/caption legibility: **Helvetica, Arial**
  (both widely licensed/system fonts, not free-libre but ubiquitous).
  [Kapwing](https://www.kapwing.com/resources/font-for-subtitles/)
- Not independently confirmed in this pass (carried from general industry knowledge, not from a
  cited source this round): **Inter** (free, SIL OFL, excellent screen hinting), **Poppins** (free,
  Google Fonts, geometric — visually close to Montserrat), **Proxima Nova** (paid/licensed,
  common in Western branding), and Impact-alike "TheBoldFont" (free, used for meme-caption style,
  less common in the modern karaoke look). Flagging these as reasonable choices consistent with the
  sourced guidance (bold geometric sans) but not independently re-verified with a citation this
  session.

## Recommended spec (1080×1920 @ 30fps)

| Property | Recommendation | Basis |
|---|---|---|
| Font size | **0.065 of frame height** (≈125px) | broadcast floor 0.05-0.10 + visual density of viral karaoke templates; user's "too small" complaint confirmed — current 0.030 is roughly half the broadcast floor |
| Font weight | Bold / Extra Bold | Montserrat Bold cited as current standard |
| Case | Sentence case (not uppercase) | qualitative — modern karaoke style trends away from all-caps |
| Font family | Montserrat (free) or Inter/Poppins as alternates | sourced (Montserrat) + reasonable free alternates |
| Stroke/outline | **0.08 of font size** (≈10px at 125px font) | derived from cited 2-4px @ 24-48px ratio |
| Shadow | Yes, soft drop shadow in addition to stroke | cited as common combined treatment |
| Background plate | None by default (stroke+shadow only) | dominant in top-tier karaoke templates; plate reads as "basic" auto-caption style |
| Position anchor | **62% of frame height from top** (fraction 0.62) — lower-middle, not bottom, not exact center | reconciles YouTube Shorts (top 380px / 0.198 + bottom 380-400px / ~0.20 UI bands) with TikTok's cited 60-70%-from-top sweet spot |
| Horizontal margin | Keep clear of right rail: ≥15% of width from right edge (≥162px); ≥6% from left (≥65px) | derived from cited YouTube Shorts margins (60px left / 120px right) rounded up for safety incl. full icon stack |
| Max chars/line | **~18** | practical cap given large font in 1080px width; no sourced exact figure, treated as a gap-filled estimate |
| Max lines/card | **2** | dominant modern pattern |
| Words/card | **~3-6** | derived from 1-second-read rule + char cap |
| Word emphasis | Per-word (or per-phrase) karaoke highlight in one bright accent color | cited as standard, improves watch time; exact color left as brand choice |

## YAML for config

```yaml
captions:
  font_family: "Montserrat"
  font_weight: "bold"          # or "extrabold" if available
  case: "sentence"              # sentence | title | upper
  font_size_fraction: 0.065     # of frame height (1920 * 0.065 ≈ 125px)
  outline_fraction: 0.08        # of font_size (stroke width)
  shadow: true
  background_plate: false
  position_anchor: 0.62         # fraction of frame height from top, caption baseline/center
  horizontal_margin_left_fraction: 0.06
  horizontal_margin_right_fraction: 0.15   # clears YT Shorts right action rail
  max_chars_per_line: 18
  max_lines: 2
  words_per_card_min: 3
  words_per_card_max: 6
  emphasis:
    mode: "karaoke_per_word"    # highlight currently-spoken word/phrase
    highlight_color: "#FFD400"  # placeholder accent — treat as brand-configurable, not a sourced standard
```

## Explicit conflicts with stated preferences

- **"Larger" font** — confirmed and quantified: current 0.030 vs. recommended 0.065 (~2.2x
  bigger). Evidence range spans 0.05-0.10; we picked 0.065 as a defensible middle that avoids
  eating too much vertical space at 2 lines while still reading as "big."
- **"Middle of the screen"** — partially confirmed, refined: evidence points to **60-70% from top**
  (lower-middle), not exact 50% center. Recommended 0.62. If a single simpler anchor is preferred
  and dead-center is acceptable for the product, 0.50-0.55 is still clear of both UI bands
  (0.198-0.21 each) and is a reasonable simplification — just slightly off the specific sweet spot
  the platform-safe-area and creator sources independently converge on.

## Stated gaps (no hard number found)

- Exact font-size fraction used by any specific top-performing channel or tool's literal render
  (only ranges/rules-of-thumb found).
- Exact letter-spacing/tracking values for caption fonts.
- A single "standard" highlight color — commonly yellow/green/accent anecdotally, not independently
  sourced to a number here.
- Descript's literal default max-lines/max-words values (tool allows configuring, defaults not
  published in sources found).
