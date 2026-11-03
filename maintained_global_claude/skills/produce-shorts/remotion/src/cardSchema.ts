// The card-props contract for the `Card` composition: transparent text layers (lower-thirds,
// kinetic cards, picture labels) composited over horizontal clips by render_horizontal.py.
// scripts/overlay_text.py builds these props from clip.yaml `overlays:` + config/defaults.yaml
// `broll.text` (the ONE source of truth for the card style); nothing here has a default style.

import { z } from 'zod';

const px = z.number().finite();
const frame = z.int().nonnegative();
const hexColor = z.string().regex(/^#[0-9A-Fa-f]{6}$/);

export const RunSchema = z.strictObject({
  text: z.string().min(1),
  color: hexColor,
  weight: z.int().min(100).max(900),
  /** frame the run appears (pops in); null = with its element */
  appear: frame.nullable(),
  /** frame an underline / strike-through starts drawing across the run */
  underline: frame.nullable(),
  strike: frame.nullable(),
});

export const LineSchema = z.strictObject({
  size: px.positive(),
  runs: z.array(RunSchema).min(1),
});

export const ElementSchema = z.strictObject({
  x: px,
  y: px,
  anchor: z.enum([
    'top-left', 'top-center', 'top-right',
    'center-left', 'center', 'center-right',
    'bottom-left', 'bottom-center', 'bottom-right',
  ]),
  maxWidth: px.positive(),
  align: z.enum(['left', 'center', 'right']),
  plate: z.boolean(),
  accentBar: z.boolean(),
  from: frame,
  to: frame,
  fadeIn: frame,
  fadeOut: frame,
  lines: z.array(LineSchema).min(1),
});

export const CardStyleSchema = z.strictObject({
  plateColor: hexColor,
  plateOpacity: z.number().min(0).max(1),
  plateRadius: px.nonnegative(),
  platePadV: px.nonnegative(),
  platePadH: px.nonnegative(),
  accentColor: hexColor,
  accentBarPx: px.nonnegative(),
  lineGap: z.number().positive(),
  ruleFrames: z.int().positive(),
  popFrames: z.int().positive(),
  ruleColor: hexColor,
  textShadow: z.string(),
});

export const CardPropsSchema = z.strictObject({
  width: z.int().positive(),
  height: z.int().positive(),
  fps: z.number().positive(),
  durationInFrames: z.int().positive(),
  style: CardStyleSchema,
  elements: z.array(ElementSchema).min(1),
});

export type CardProps = z.infer<typeof CardPropsSchema>;
export type CardElement = z.infer<typeof ElementSchema>;
export type CardRun = z.infer<typeof RunSchema>;
export type CardStyle = z.infer<typeof CardStyleSchema>;

export const parseCardProps = (raw: unknown): CardProps => {
  const result = CardPropsSchema.safeParse(raw);
  if (result.success) return result.data;
  const issues = result.error.issues
    .map((i) => `  props${i.path.length > 0 ? `.${i.path.join('.')}` : ''}: ${i.message}`)
    .join('\n');
  throw new Error(
    `card props failed validation:\n${issues}\nCard props are written by scripts/overlay_text.py; ` +
      `render cards through render_horizontal.py (render-cards.mjs), never with default props.`,
  );
};
