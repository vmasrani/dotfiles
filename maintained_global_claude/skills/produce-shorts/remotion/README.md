# Remotion composition template — stage 8, step 5

This directory is the deterministic compositor for `produce-shorts`. It renders
**exactly** what a clip's manifest says: one `props.json`, generated from
`clip.yaml` + the assembled audio + the aligned `.ass`, drives every frame.

It is a *template*: it ships without `node_modules/`, is copied into an episode
workspace per clip, and `npm install` runs there — never in the skill repo.

## Where it sits in the pipeline

`references/render-qc.md` stage 8 runs, in order:

1. `assemble_audio.py CLIP_DIR` → `renders/v<N>-audio.wav`
2. lock the timeline
3. `align_subtitles.py` → `subtitles/v<N>.ass`, then `validate_subtitles.py`
4. `extract_segments.py CLIP_DIR` → A-roll clips under `assets/aroll/`
5. **this template** — `gen-props.mjs`, then `npx remotion render`
6. per-profile ffmpeg encode + loudness normalisation
7. version the render, never overwrite

Everything upstream is a hard prerequisite. `gen-props.mjs` refuses to write
`props.json` if any of it is missing.

## Copy into the workspace and render

```bash
CLIP=episode-<slug>/clips/<clip-slug>          # the clip dir
N=1                                            # render version

# 1. copy the template into the clip (once per clip)
cp -R "$SKILL/remotion" "$CLIP/remotion"
cd "$CLIP/remotion"
npm install

# 2. clip.yaml -> props.json (validates every input, fails loud)
node gen-props.mjs .. \
  --audio "renders/v$N-audio.wav" \
  --ass   "subtitles/v$N.ass"

# 3. render the visual master (h264; loudness/profile encode is step 6)
npx remotion render Short "../renders/v$N-master.mp4" --props=props.json

# optional: inspect interactively before rendering
npx remotion studio --props=props.json
```

`npm run props -- <clip-dir> --audio … --ass …`, `npm run render` and
`npm run preview` are the same commands with the defaults baked in.

The clip dir is passed to `gen-props.mjs` as a positional argument, so the
template does not have to live inside the clip — but one template copy serves
**one clip at a time** (it symlinks that clip into `public/`, see below).

## gen-props.mjs

```text
node gen-props.mjs <clip-dir> --audio <path> --ass <path> [flags]

  --audio <path>        assembled audio, relative to the clip dir      (required)
  --ass <path>          aligned subtitles, relative to the clip dir    (required)
  --profile <name>      platform profile in episode.yaml               (default: first)
  --fps / --width / --height    override the profile's values
  --episode <path>      episode.yaml                                   (default: <clip-dir>/../../episode.yaml)
  --defaults <path>     config/defaults.yaml, for its `safe_zones`     (default: built-in 200/320/60/120)
  --safe-top/-bottom/-left/-right <px>   override individual insets
  --aroll-dir <dir>     staged A-roll dir, relative to the clip dir    (default: assets/aroll)
  --aroll-ext <ext>     staged A-roll extension                        (default: .mp4)
  --out <path>          where to write props                           (default: ./props.json)
  --public-link <name>  name of the clip symlink inside public/        (default: clip)
```

It reads `clip.yaml` and `episode.yaml`, validates both with zod (strictly, the
same shape `scripts/pslib.py` enforces), and then re-checks the invariants the
render actually depends on — a contiguous zero-based timeline, output/source
duration parity, one frame minimum per segment, `output.duration_s` agreeing
with the last segment, crossfades that fit inside both neighbours, resolution
and fps agreeing with the manifest and the platform profile, assets that exist
and are long enough, `used_in_segments` agreeing in both directions, subtitle
events inside the safe zone and inside the clip's palette.

Any failure exits nonzero, names the field or file, and writes nothing.

### Media resolution — the `public/clip` symlink

Remotion can only load files under its public dir. `gen-props.mjs` therefore
symlinks the clip dir to `public/<--public-link>` (default `public/clip`) and
writes media paths relative to the clip dir; the composition resolves them as
`staticFile("clip/<path>")`. Nothing is fetched over the network at render
time, and no media is copied.

Because the symlink is per-generation, **do not run two clips through one
template copy concurrently** — copy the template per clip.

### Inputs it expects on disk

| Path (relative to the clip dir) | Written by | Used for |
|---|---|---|
| `clip.yaml` | stages 3–7 | the manifest |
| `../../episode.yaml` | stage 1 | speakers, platform profile |
| `renders/v<N>-audio.wav` | `assemble_audio.py` | the single audio track |
| `subtitles/v<N>.ass` | `align_subtitles.py` | subtitle timing truth |
| `assets/aroll/<SEG>.mp4` | `extract_segments.py` | A-roll, already cropped/normalised |
| `assets/aroll/<SEG>-top.mp4`, `-bottom.mp4` | `extract_segments.py` | split-screen halves |
| `assets/<asset file>` | stage 5 | B-roll, as named in `assets[].file` |

A-roll file naming is the contract between `extract_segments.py` and this
template: one file per segment id, two (`-top` / `-bottom`) for `splitscreen`.

## What the composition draws

`src/Root.tsx` registers one composition, `Short`. Its width, height, fps and
`durationInFrames` come from `props.json` via `calculateMetadata` — there are no
hard-coded dimensions. Missing or invalid props fail the render immediately with
every bad field named.

One `<Sequence>` per timeline segment, in manifest order:

| `visual.kind` | `visual.treatment` | Rendered as |
|---|---|---|
| `aroll` | `closeup-<speaker>` | the segment's staged clip, full-bleed (cover) |
| `aroll` | `reaction-<speaker>` | the segment's staged clip, full-bleed (cover) |
| `aroll` | `splitscreen` | two staged clips, stacked, each half height, cover |
| `aroll` | `source-frame` | the staged clip letterboxed (contain) on black |
| `broll` | `cover` | the asset, cover-fit |
| `broll` | `contain` / `letterbox` | the asset, letterboxed on black |

Any other treatment throws. B-roll `treatment` values are limited to
`cover`/`contain`/`letterbox`; the storyboard's editorial intent lives in the
storyboard, not in a string this renderer would have to guess at.

All video is muted — the audio track is the assembled WAV, whose `duck`/`mute`
decisions were already baked in by `assemble_audio.py`.

### Motion (Ken Burns)

`visual.motion` is parsed by `src/motion.mjs`, shared by the generator and the
renderer. An unsupported string **throws** — it never silently renders a still.

```text
[adverb] zoom-in  <from>-><to>%     e.g. "slow zoom-in 100->108% over segment"
[adverb] zoom-out <from>-><to>%     to < from, both within 50-300%
[adverb] pan-left|pan-right|pan-up|pan-down <from>-><to>%    0-50%, from != to
none | static | hold | locked       explicit no-op (so is YAML null)
adverbs: slow, slowly, fast, gentle, gently, subtle, steady, smooth
a trailing "over segment" / "over the segment" is ignored
```

Motion interpolates linearly across the segment's nominal duration (crossfade
tails excluded) and applies to A-roll as well as B-roll. A pan overscales just
enough that the framing never exposes an empty edge.

### Transitions

`transition` is the transition **into the next segment**.

- `cut` — nothing.
- `crossfade-<N>f` — the outgoing segment holds for N extra frames while the
  incoming segment ramps its opacity 0→1 on top of it, starting at the cut
  point. **The cut point never moves**, so the video stays sample-aligned with
  the audio that `assemble_audio.py` already cut. N must fit inside both
  neighbouring segments, and the last segment may not cross-fade.

### Subtitles

`src/Subtitles.tsx` draws the events parsed from the `.ass` — the timing truth
after forced alignment, never the design-time ranges in `clip.yaml`. Line-level
display windows (no word-level karaoke): one `<Sequence>` per dialogue event,
positioned from the .ass alignment plus `MarginV`/`\pos`, always inside the safe
zone, horizontally constrained to `width - left - right`.

Line breaks are the `.ass` file's (`\N`); the text box additionally soft-wraps
so a line can never spill sideways out of the safe zone. `gen-props.mjs`'s
vertical safe-zone check counts the `.ass`'s own breaks, so keep
`validate_subtitles.py` (≤2 lines, ≤42 chars/line) green upstream — it owns line
length, this template owns placement.

Per-word emphasis comes through as styled spans: `\b1` renders at weight 700,
`\c&HBBGGRR&` recolours, `\r` resets, `\N` breaks the line. Every colour must be
`subtitles.base_color` or a member of `emphasis_palette` — an off-palette colour
is an error, not a surprise in the render.

Inter is loaded from `public/fonts/*.woff2` (the Google Fonts latin and
latin-ext subsets of the Inter variable font, SIL OFL 1.1) — **not** from a CDN,
so the render does not depend on the network or on installed system fonts.
`Inter Semibold` is the only font this template ships; another `subtitles.font`
is an error.

### Credits

`src/Credits.tsx` draws a small attribution line in the lower-left of the safe
area for the duration of any segment whose asset has `credit_required: true`
(`"Video by <creator> on <Provider>"`). `gen-props.mjs` refuses to generate
props when a subtitle would sit on top of that line.

## Determinism rules this template keeps

- No `Date.now()`, no `Math.random()`, no animation that is not a pure function
  of the frame number.
- No network access at render time — fonts and media are local files.
- **No AI-generated imagery of any kind**, ever. Visuals come from the source
  footage and from licensed assets listed in `clip.yaml assets[]`.
- Nothing is composited that is not named in `props.json`.
- A file the manifest promised but that is not on disk fails the render, with
  the path, instead of rendering a black hole.
- `Config.setOverwriteOutput(false)` — renders are versioned, never overwritten.

## Files

```text
package.json          pinned remotion 4.x, react, zod, js-yaml
package-lock.json     the exact dependency tree this template was verified on
remotion.config.ts    entry point, h264/yuv420p, never overwrite
tsconfig.json         strict TS, no emit
gen-props.mjs         clip.yaml (+ episode, audio, .ass) -> props.json
lib/clip-schema.mjs   zod mirrors of clip.yaml / episode.yaml
lib/ass.mjs           strict .ass reader (styles, events, override tags)
src/index.ts          registerRoot
src/Root.tsx          the Short composition + calculateMetadata
src/Short.tsx         one Sequence per segment; treatments, motion, transitions
src/Subtitles.tsx     .ass-derived subtitle events
src/Credits.tsx       attribution line for credit_required assets
src/schema.ts         the props.json contract (zod)
src/media.ts          staticFile resolution + missing-file guard
src/motion.mjs        motion grammar, shared by generator and renderer
src/fonts.ts          bundled Inter loading
public/fonts/         Inter woff2 subsets (OFL 1.1)
```

`node_modules/`, `props.json`, `out/` and `public/clip` are generated in the
workspace and are not part of the template (see `.gitignore`).
