// The props.json contract. gen-props.mjs writes it, the composition refuses to
// render anything that does not match it.

import type { Caption } from '@remotion/captions';
import { z } from 'zod';

const px = z.number().finite();
const frame = z.int().nonnegative();

export const TransitionSchema = z.discriminatedUnion('kind', [
  z.strictObject({ kind: z.literal('cut') }),
  z.strictObject({ kind: z.literal('crossfade'), frames: z.int().positive() }),
]);

export const SegmentSchema = z.strictObject({
  id: z.string().min(1),
  startFrame: frame,
  durationInFrames: z.int().positive(),
  speaker: z.string().min(1),
  kind: z.enum(['aroll', 'broll']),
  treatment: z.string().min(1),
  motion: z.string().min(1).nullable(),
  sources: z.array(z.string().min(1)).min(1),
  transitionOut: TransitionSchema,
  credit: z.string().min(1).nullable(),
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
  layout: z.enum(['solo', 'split']),
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
  subtitles: z.array(SubtitleEventSchema),
});

export type Transition = z.infer<typeof TransitionSchema>;
export type Segment = z.infer<typeof SegmentSchema>;
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
