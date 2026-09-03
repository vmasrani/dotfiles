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

export const ClipSchema = z.strictObject({
  clip: z.strictObject({
    id: z.string().min(1),
    title: z.string().min(1),
    status: z.enum([
      'proposed', 'approved_edit', 'storyboarded', 'assets_ready', 'critiqued',
      'approved_render', 'rendered', 'qc_passed', 'delivered',
    ]),
    logline: z.string(),
    audience_response: z.string(),
    hook: z.string(),
    payoff: z.string(),
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
  output: z.strictObject({
    aspect: z.string().regex(/^\d+:\d+$/),
    resolution: z.string().regex(/^\d+x\d+$/),
    fps: z.number().positive(),
    duration_s: z.number().positive(),
  }),
  thumbnail: z.strictObject({
    first_frame_text: z.string(),
    hierarchy: z.string(),
    placement: z.string(),
  }),
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
    max_duration_s: z.number().positive(),
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
