// Canonical parser for clip.yaml `visual.motion` strings.
//
// One implementation, shared by gen-props.mjs (Node, validation time) and
// Short.tsx (render time, via motion.d.mts). An unsupported string THROWS —
// silently rendering a static frame for a motion the manifest asked for would
// be a wrong-but-plausible result.

/** Leading adverbs the storyboard is allowed to write; they carry no timing. */
const ADVERBS = new Set(['slow', 'slowly', 'fast', 'gentle', 'gently', 'subtle', 'steady', 'smooth']);

/** Explicit "no motion" spellings. `null` in YAML means the same thing. */
const NO_MOTION = new Set(['none', 'static', 'hold', 'locked']);

const VERBS = ['zoom-in', 'zoom-out', 'pan-left', 'pan-right', 'pan-up', 'pan-down'];

export const MOTION_GRAMMAR = [
  '  [adverb] zoom-in  <from>-><to>%   (to > from, both 50-300)',
  '  [adverb] zoom-out <from>-><to>%   (to < from, both 50-300)',
  '  [adverb] pan-left|pan-right|pan-up|pan-down <from>-><to>%   (0-50, from != to)',
  '  none | static | hold | locked     (explicit no-op)',
  `  adverbs: ${[...ADVERBS].join(', ')}`,
  '  an optional trailing " over segment" / " over the segment" is ignored',
].join('\n');

const fail = (raw, why) => {
  throw new Error(
    `unsupported motion string ${JSON.stringify(raw)}: ${why}\nsupported grammar:\n${MOTION_GRAMMAR}`,
  );
};

/**
 * @param {string | null | undefined} raw
 * @returns {null | {kind: 'zoom', fromScale: number, toScale: number}
 *                | {kind: 'pan', axis: 'x' | 'y', sign: 1 | -1, fromOffset: number, toOffset: number}}
 */
export function parseMotion(raw) {
  if (raw === null || raw === undefined) return null;
  if (typeof raw !== 'string') fail(raw, 'motion must be a string or null');

  let s = raw.trim().toLowerCase().replace(/\s+/g, ' ');
  if (s === '') fail(raw, 'empty string — write null (or "none") for no motion');
  s = s.replace(/ over (the )?segment$/, '');

  if (NO_MOTION.has(s)) return null;

  const words = s.split(' ');
  while (words.length > 0 && ADVERBS.has(words[0])) words.shift();
  const rest = words.join(' ');

  const m = /^([a-z-]+) (\d+(?:\.\d+)?) ?-> ?(\d+(?:\.\d+)?)%$/.exec(rest);
  if (m === null) {
    fail(raw, `does not match "<verb> <from>-><to>%" (verbs: ${VERBS.join(', ')})`);
  }
  const [, verb, fromRaw, toRaw] = m;
  if (!VERBS.includes(verb)) fail(raw, `unknown verb "${verb}" (verbs: ${VERBS.join(', ')})`);

  const from = Number(fromRaw);
  const to = Number(toRaw);
  if (from === to) fail(raw, `from and to are both ${from}% — that is a no-op, write null instead`);

  if (verb === 'zoom-in' || verb === 'zoom-out') {
    for (const v of [from, to]) {
      if (v < 50 || v > 300) fail(raw, `zoom percentage ${v}% outside the supported 50-300% range`);
    }
    if (verb === 'zoom-in' && to < from) fail(raw, `zoom-in must grow (${from}% -> ${to}%)`);
    if (verb === 'zoom-out' && to > from) fail(raw, `zoom-out must shrink (${from}% -> ${to}%)`);
    return { kind: 'zoom', fromScale: from / 100, toScale: to / 100 };
  }

  for (const v of [from, to]) {
    if (v < 0 || v > 50) fail(raw, `pan percentage ${v}% outside the supported 0-50% range`);
  }
  // pan-left: the framing travels toward the asset's left edge, so the image
  // slides right on screen (positive translate). pan-up likewise slides down.
  const axis = verb === 'pan-left' || verb === 'pan-right' ? 'x' : 'y';
  const sign = verb === 'pan-left' || verb === 'pan-up' ? 1 : -1;
  return { kind: 'pan', axis, sign, fromOffset: from / 100, toOffset: to / 100 };
}

/**
 * Deterministic transform for a motion at normalised progress p in [0, 1].
 *
 * @param {ReturnType<typeof parseMotion>} motion
 * @param {number} p
 * @returns {{scale: number, translateXPercent: number, translateYPercent: number}}
 */
export function motionTransform(motion, p) {
  const still = { scale: 1, translateXPercent: 0, translateYPercent: 0 };
  if (motion === null) return still;

  const lerp = (a, b) => a + (b - a) * p;

  if (motion.kind === 'zoom') {
    return { ...still, scale: lerp(motion.fromScale, motion.toScale) };
  }

  // Overscale just enough that the panned framing never exposes an empty edge.
  const scale = 1 + 2 * Math.max(motion.fromOffset, motion.toOffset);
  const offset = motion.sign * lerp(motion.fromOffset, motion.toOffset) * 100;
  return {
    scale,
    translateXPercent: motion.axis === 'x' ? offset : 0,
    translateYPercent: motion.axis === 'y' ? offset : 0,
  };
}

/**
 * @param {ReturnType<typeof parseMotion>} motion
 * @param {number} p
 * @returns {string}
 */
export function motionCss(motion, p) {
  const t = motionTransform(motion, p);
  return `translate(${t.translateXPercent}%, ${t.translateYPercent}%) scale(${t.scale})`;
}
