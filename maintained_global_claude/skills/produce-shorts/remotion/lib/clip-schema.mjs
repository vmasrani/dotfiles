// zod mirrors of the canonical manifests in references/schemas.md.
//
// clip.yaml is validated STRICTLY (unknown keys are an error, exactly like the
// pydantic models in scripts/pslib.py). episode.yaml is validated only where
// this generator reads it — the rest of the file belongs to other stages.

import { z } from 'zod';

const seconds = z.number().finite().nonnegative();

export const VisualSchema = z.strictObject({
  kind: z.enum(['aroll', 'broll']),
  treatment: z.string().min(1),
  // splitscreen only: exactly two speaker ids [top, bottom]
  speakers: z.tuple([z.string().min(1), z.string().min(1)]).nullable().default(null),
  // true = a user override by comment; plan_framing.py never changes it
  locked: z.boolean().default(false),
  reason: z.string().nullable().default(null),
  // optional per-segment crop override `x=..:y=..:w=..:h=..` (scripts/frame_segments.py reads it; it becomes the shot geometry in props.json)
  crop: z.string().min(1).nullable().default(null),
  asset_id: z.string().min(1).nullable().default(null),
  motion: z.string().min(1).nullable().default(null),
});

export const SegmentSchema = z.strictObject({
  id: z.string().regex(/^S\d{2,}$/, 'segment id must look like S01'),
  source_file: z.string().min(1),
  source_in: seconds,
  source_out: seconds,
  output_in: seconds,
  output_out: seconds,
  dialogue: z.string(),
  speaker: z.string().min(1),
  audio: z.enum(['as-recorded', 'duck', 'mute']),
  visual: VisualSchema,
  transition: z.string().min(1),
});

export const AssetSchema = z.strictObject({
  id: z.string().regex(/^A\d{2,}$/, 'asset id must look like A03'),
  provider: z.string().min(1),
  provider_asset_id: z.string().min(1),
  source_url: z.string().min(1),
  license: z.string().min(1),
  entitlement: z.enum(['free', 'subscription', 'purchased']),
  download_date: z.string().min(1),
  creator: z.string(),
  credit_required: z.boolean(),
  width: z.int().positive(),
  height: z.int().positive(),
  fps: z.number().positive(),
  duration_s: z.number().positive(),
  file: z.string().min(1),
  sha256: z.string().nullable().default(null),
  used_in_segments: z.array(z.string()).default([]),
});

const LEGACY_STATUS = { storyboarded: 'frozen', approved_render: 'frozen' };
const LEGACY_REVIEW_KEYS = new Set(['storyboard_docs', 'cover']);
const dropLegacyReviewKeys = (v) =>
  v && typeof v === 'object' && !Array.isArray(v)
    ? Object.fromEntries(Object.entries(v).filter(([k]) => !LEGACY_REVIEW_KEYS.has(k)))
    : v;

// clip.yaml `overlays:` (references/schemas.md § Overlays). A short draws only fullscreen still pictures as its quote
// layout; gen-props.mjs refuses everything else with "not implemented for shorts" (the fields are parsed, not drawn).
const OverlayShotSchema = z.strictObject({
  asset: z.string().min(1).nullable().default(null),
  grid: z.unknown().nullable().default(null),
  at: seconds.default(0),
  src_in: z.number().nullable().default(null),
  src_out: z.number().nullable().default(null),
  speed: z.number().default(1),
  hold_last: z.boolean().default(false),
  crop: z.string().nullable().default(null),
  zoom: z.tuple([z.number(), z.number()]).nullable().default(null),
  dissolve_frames: z.int().nonnegative().default(0),
});

export const OverlaySchema = z.strictObject({
  id: z.string().min(1),
  mode: z.enum(['fullscreen', 'pip', 'lowerthird', 'card']),
  start: seconds,
  end: seconds,
  shots: z.array(OverlayShotSchema).default([]),
  box: z.unknown().nullable().default(null),
  from_box: z.unknown().nullable().default(null),
  move_frames: z.int().nonnegative().default(0),
  label: z.string().nullable().default(null),
  lines: z.array(z.unknown()).default([]),
  reveal: z.enum(['none', 'words']).default('none'),
  reveal_s: z.number().default(0),
  placement: z.string().nullable().default(null),
  fade_in_frames: z.int().nonnegative().default(0),
  fade_out_frames: z.int().nonnegative().default(0),
  note: z.string().nullable().default(null),
});

export const ClipSchema = z.strictObject({
  clip: z.strictObject({
    id: z.string().min(1),
    pick: z.string().min(1),
    format: z.enum(['short', 'clip']),
    title: z.string().min(1),
    // Legacy values from before the storyboard doc was removed meant "frozen, awaiting render".
    status: z.preprocess((v) => LEGACY_STATUS[v] ?? v, z.enum(['frozen', 'rendered', 'qc_passed', 'delivered'])),
    why: z.string(),
    ends_on: z.string(),
  }),
  timeline: z.array(SegmentSchema).min(1),
  subtitles: z.strictObject({
    font: z.string().min(1),
    base_color: z.string().regex(/^#[0-9A-Fa-f]{6}$/),
    emphasis_palette: z.array(z.string().regex(/^#[0-9A-Fa-f]{6}$/)).default([]),
    position_default: z.enum(['bottom-center', 'middle-lower']),
    lines: z.array(z.strictObject({
      output_range: z.tuple([seconds, seconds]),
      text: z.string().min(1),
      emphasis: z.array(z.strictObject({ word: z.string().min(1), style: z.string().min(1) })).default([]),
      position: z.enum(['bottom-center', 'middle-lower']),
      note: z.string().nullable().default(null),
    })).default([]),
  }),
  assets: z.array(AssetSchema).default([]),
  broll: z.strictObject({
    provenance: z.string().min(1).default('broll/provenance.json'),
    protected_tail_s: z.number().nonnegative(),
  }).nullable().default(null),
  overlays: z.array(OverlaySchema).default([]),
  output: z.strictObject({
    aspect: z.string().regex(/^\d+:\d+$/),
    resolution: z.string().regex(/^\d+x\d+$/),
    fps: z.number().positive(),
    duration_s: z.number().positive(),
  }),
  review: z.preprocess(dropLegacyReviewKeys, z.strictObject({
    final_url: z.string().nullable().default(null),
    youtube_url: z.string().nullable().default(null),
  }).default({ final_url: null, youtube_url: null })),
  render: z.strictObject({
    versions: z.array(z.looseObject({ version: z.int() })).default([]),
  }),
});

export const EpisodeSchema = z.looseObject({
  episode: z.looseObject({ id: z.string().min(1), title: z.string().min(1) }),
  speakers: z.array(z.looseObject({ id: z.string().min(1), name: z.string().min(1) })).min(1),
  platform_profiles: z.array(z.looseObject({
    name: z.string().min(1),
    resolution: z.string().regex(/^\d+x\d+$/),
    fps: z.number().positive(),
    max_duration_s: z.number().positive().nullable(), // null = no maximum (horizontal clips)
  })).min(1),
});

/** Parse or die with every failing field path named. */
export const parseOrDie = (schema, value, label) => {
  const result = schema.safeParse(value);
  if (result.success) return result.data;
  const issues = result.error.issues
    .map((i) => `  ${label}${i.path.length > 0 ? `.${i.path.join('.')}` : ''}: ${i.message}`)
    .join('\n');
  throw new Error(`${label} failed schema validation:\n${issues}`);
};
