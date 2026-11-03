// The props.json contract. gen-props.mjs writes it, the composition refuses to
// render anything that does not match it.

import type { Caption } from '@remotion/captions';
import { z } from 'zod';
import { panelProblems, quoteProblems } from './geometry.mjs';

const px = z.number().finite();
const frame = z.int().nonnegative();

export const TransitionSchema = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('cut') }),
  z.strictObject({ kind: z.literal('crossfade'), frames: z.int().positive() }),
]);

const RectSchema = z.strictObject({ x: px, y: px, w: px.positive(), h: px.positive() });

/** One shot of a panel: a crop window of the source video drawn into `dst` (see geometry.mjs). */
export const PanelShotSchema = z.strictObject({
  fromFrame: frame,
  toFrame: z.int().positive(),
  cropW: px.positive(),
  cropH: px.positive(),
  keys: z.array(z.strictObject({ frame: px, x: px, y: px })).min(1),
  dst: RectSchema,
  backdrop: z.strictObject({ blurPx: px.positive(), brightness: px.positive() }).nullable(),
  tile: RectSchema.nullable(),
});

/** One video rectangle of an A-roll segment, cropped from the single source video (scripts/frame_segments.py). */
export const PanelSchema = z.strictObject({
  slot: z.enum(['full', 'top', 'bottom']),
  rect: RectSchema,
  /** path relative to the episode root (served at `episodeRoot/`) */
  source: z.string().min(1),
  sourceDims: z.strictObject({ w: z.int().positive(), h: z.int().positive() }),
  /** source-video frame, at the composition fps, that plays on the segment's first frame */
  trimBeforeFrame: frame,
  shots: z.array(PanelShotSchema).min(1),
});

/** One screenshot of a quote layout (scripts/quotelayout.py decided `dst`); frames are composition frames. */
export const QuoteShotSchema = z.strictObject({
  fromFrame: frame,
  toFrame: z.int().positive(),
  /** path relative to the clip dir */
  src: z.string().min(1),
  srcW: z.int().positive(),
  srcH: z.int().positive(),
  dst: RectSchema,
  zoom: z.tuple([px.positive(), px.positive()]),
  dissolveFrames: frame,
});

/** A picture overlay of a short: screenshots on the top panel, each A-roll segment's `quotePanel` below. */
export const QuoteSchema = z.strictObject({
  id: z.string().min(1),
  startFrame: frame,
  endFrame: z.int().positive(),
  fadeInFrames: frame,
  fadeOutFrames: frame,
  rect: RectSchema,
  backdrop: z.strictObject({ blurPx: px.positive(), brightness: px.positive() }),
  shots: z.array(QuoteShotSchema).min(1),
}).superRefine((quote, ctx) => {
  quoteProblems(quote).forEach((problem) => ctx.addIssue({ code: 'custom', message: `quote ${quote.id}: ${problem}` }));
});

export const SegmentSchema = z.strictObject({
  id: z.string().min(1),
  startFrame: frame,
  durationInFrames: z.int().positive(),
  speaker: z.string().min(1),
  kind: z.enum(['aroll', 'broll']),
  treatment: z.string().min(1),
  motion: z.string().min(1).nullable(),
  /** b-roll: the one asset file (relative to the clip dir); a-roll: empty — its video is in `panels` */
  sources: z.array(z.string().min(1)),
  panels: z.array(PanelSchema).nullable(),
  /** the segment's speaker, drawn below the screenshot while a quote overlay is up (A-roll under an overlay only) */
  quotePanel: PanelSchema.nullable(),
  transitionOut: TransitionSchema,
  credit: z.string().min(1).nullable(),
}).superRefine((segment, ctx) => {
  const bad = (message: string) => ctx.addIssue({ code: 'custom', message });
  if (segment.kind === 'broll') {
    if (segment.sources.length !== 1 || segment.panels !== null) bad(`${segment.id}: b-roll needs exactly 1 source and no panels`);
    return;
  }
  if (segment.sources.length !== 0 || segment.panels === null) {
    bad(`${segment.id}: a-roll takes its video from panels, not sources`);
    return;
  }
  const slots = segment.panels.map((p) => p.slot).join('+');
  const want = segment.treatment === 'splitscreen' ? 'top+bottom' : 'full';
  if (slots !== want) bad(`${segment.id}: ${segment.treatment} needs panels ${want}, props.json has ${slots}`);
  segment.panels.forEach((panel) => {
    panelProblems(panel, segment.durationInFrames).forEach((problem) => bad(`${segment.id} ${panel.slot} panel: ${problem}`));
  });
  if (segment.quotePanel !== null) {
    if (segment.quotePanel.slot !== 'bottom') bad(`${segment.id}: the quote panel is the bottom panel, props.json has ${segment.quotePanel.slot}`);
    panelProblems(segment.quotePanel, segment.durationInFrames).forEach((problem) => bad(`${segment.id} quote panel: ${problem}`));
  }
});

const hexColor = z.string().regex(/^#[0-9A-Fa-f]{6}$/);

export const SpanSchema = z.strictObject({
  text: z.string(),
  color: hexColor,
  bold: z.boolean(),
  italic: z.boolean(),
  /** index into the event's `words`; null for whitespace between words */
  word: z.int().nonnegative().nullable(),
});

/** One spoken word of a card — exactly @remotion/captions' `Caption` (absolute ms in the clip). */
export const CaptionSchema = z.strictObject({
  text: z.string().min(1),
  startMs: z.number().nonnegative(),
  endMs: z.number().nonnegative(),
  timestampMs: z.number().nullable(),
  confidence: z.number().nullable(),
});
// Compile-time proof the props carry the package's type, not a look-alike.
true satisfies (z.infer<typeof CaptionSchema> extends Caption ? (Caption extends z.infer<typeof CaptionSchema> ? true : never) : never);

export const PlacementSchema = z.strictObject({
  fromFrame: frame,
  layout: z.enum(['solo', 'split', 'quote']),
  posY: px,
  anchorY: z.enum(['top', 'middle', 'bottom']),
});

export const SubtitleEventSchema = z.strictObject({
  startFrame: frame,
  endFrame: z.int().positive(),
  text: z.string().min(1),
  styledSpans: z.array(SpanSchema).min(1),
  words: z.array(CaptionSchema).min(1),
  // One position per screen layout the card spans (solo -> bottom, split -> seam), switching on exactly the
  // frame the layout switches; fromFrame is relative to startFrame and the first is always 0.
  placements: z.array(PlacementSchema).min(1),
  alignX: z.enum(['left', 'center', 'right']),
});

export const ShortPropsSchema = z.strictObject({
  schemaVersion: z.literal(1),
  clipId: z.string().min(1),
  title: z.string().min(1),
  width: z.int().positive(),
  height: z.int().positive(),
  fps: z.number().positive(),
  durationInFrames: z.int().positive(),
  assetRoot: z.string().min(1),
  /** public/ name that links the episode root, where a-roll source videos live */
  episodeRoot: z.string().min(1),
  audioSrc: z.string().min(1),
  safeZone: z.strictObject({ top: px, bottom: px, left: px, right: px }),
  subtitleStyle: z.strictObject({
    fontFamily: z.string().min(1),
    fontWeight: z.int().positive(),
    emphasisFontWeight: z.int().positive(),
    activeColor: hexColor,
    activeFontWeight: z.int().positive(),
    fontSizePx: z.number().positive(),
    lineHeightEm: z.number().positive(),
    outlineWidthPx: z.number().nonnegative(),
    outlineColor: z.string().min(1),
    shadowPx: z.number().nonnegative(),
    maxWidthPx: z.number().positive(),
    leftPx: px,
  }),
  segments: z.array(SegmentSchema).min(1),
  quotes: z.array(QuoteSchema),
  subtitles: z.array(SubtitleEventSchema),
}).superRefine((props, ctx) => {
  const bad = (message: string) => ctx.addIssue({ code: 'custom', message });
  const sorted = [...props.quotes].sort((a, b) => a.startFrame - b.startFrame);
  sorted.slice(1).forEach((q, k) => {
    if (q.startFrame < sorted[k].endFrame) bad(`quotes ${sorted[k].id} and ${q.id} overlap`);
  });
  props.quotes.forEach((quote) => {
    if (quote.endFrame > props.durationInFrames) bad(`quote ${quote.id} ends at frame ${quote.endFrame}, after the clip (${props.durationInFrames})`);
    if (quote.rect.x !== 0 || quote.rect.y !== 0 || quote.rect.w !== props.width || quote.rect.h * 2 !== props.height) {
      bad(`quote ${quote.id}: the top panel ${JSON.stringify(quote.rect)} is not the top half of the ${props.width}x${props.height} frame`);
    }
    props.segments.forEach((segment) => {
      const covered = segment.startFrame < quote.endFrame && segment.startFrame + segment.durationInFrames > quote.startFrame;
      if (!covered) return;
      if (segment.kind !== 'aroll') bad(`quote ${quote.id} covers the b-roll segment ${segment.id} — a quote layout needs a speaker below it`);
      else if (segment.quotePanel === null) bad(`quote ${quote.id} covers ${segment.id}, which has no quote panel — re-run scripts/frame_segments.py`);
      else if (segment.quotePanel.rect.y !== quote.rect.h || segment.quotePanel.rect.h !== quote.rect.h) {
        bad(`${segment.id}: the quote panel ${JSON.stringify(segment.quotePanel.rect)} is not the bottom half under quote ${quote.id}`);
      }
    });
  });
});

export type Transition = z.infer<typeof TransitionSchema>;
export type Segment = z.infer<typeof SegmentSchema>;
export type Panel = z.infer<typeof PanelSchema>;
export type Quote = z.infer<typeof QuoteSchema>;
export type SubtitleEvent = z.infer<typeof SubtitleEventSchema>;
export type ShortProps = z.infer<typeof ShortPropsSchema>;

const HOW_TO_FIX =
  'Generate props.json with:\n' +
  '  node gen-props.mjs <clip-dir> --audio renders/v<N>-audio.wav --ass subtitles/v<N>.ass\n' +
  'and render with --props=props.json (see README.md).';

/** Parse untrusted composition input or fail the render with every bad field named. */
export const parseProps = (raw: unknown): ShortProps => {
  const result = ShortPropsSchema.safeParse(raw);
  if (result.success) return result.data;
  const issues = result.error.issues
    .map((i) => `  props${i.path.length > 0 ? `.${i.path.join('.')}` : ''}: ${i.message}`)
    .join('\n');
  throw new Error(`props.json failed validation:\n${issues}\n${HOW_TO_FIX}`);
};
