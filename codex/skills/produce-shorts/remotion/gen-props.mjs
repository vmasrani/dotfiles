#!/usr/bin/env node
// gen-props.mjs — clip.yaml (+ episode defaults + assembled audio + aligned .ass)
//                 -> props.json, the single input to the Short composition.
//
//   node gen-props.mjs <clip-dir> --audio <path> --ass <path> \
//        [--fps 30 --width 1080 --height 1920] [--profile youtube-shorts]
//        [--episode <episode.yaml>] [--defaults <config/defaults.yaml>]
//        [--aroll-dir assets/aroll] [--out props.json] [--public-link clip]
//        [--safe-top 200 --safe-bottom 320 --safe-left 60 --safe-right 120]
//
// Everything it cannot prove is an error. There is no partial props.json: the
// file is written only after every input has been validated and every media
// file it names has been found on disk.

import { existsSync, lstatSync, mkdirSync, readFileSync, rmSync, statSync, symlinkSync, writeFileSync } from 'node:fs';
import { dirname, isAbsolute, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import yaml from 'js-yaml';
import { ClipSchema, EpisodeSchema, parseOrDie } from './lib/clip-schema.mjs';
import { parseAss } from './lib/ass.mjs';
import { parseMotion } from './src/motion.mjs';

const TEMPLATE_DIR = dirname(fileURLToPath(import.meta.url));
const EPS = 0.01; // the pipeline-wide comparison epsilon (references/schemas.md)
const SCHEMA_VERSION = 1;

// Mirrors config/defaults.yaml `safe_zones` (1080x1920 reference frame).
const DEFAULT_SAFE_ZONE = { top: 200, bottom: 320, left: 60, right: 120 };

const AROLL_TREATMENTS = ['closeup-<speaker>', 'blur-fill-<speaker>', 'splitscreen', 'source-frame', 'reaction-<speaker>'];
const BROLL_TREATMENTS = ['cover', 'contain', 'letterbox'];

/** Vertical room a credit line occupies at the bottom-left of the safe area. */
const CREDIT_RESERVE_PX = 44;

const die = (msg) => {
  throw new Error(msg);
};

const readYaml = (path, label) => {
  if (!existsSync(path)) die(`${label} not found: ${path}`);
  return yaml.load(readFileSync(path, 'utf8'));
};

const near = (a, b) => Math.abs(a - b) <= EPS;

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const { values: flags, positionals } = parseArgs({
  allowPositionals: true,
  options: {
    audio: { type: 'string' },
    ass: { type: 'string' },
    fps: { type: 'string' },
    width: { type: 'string' },
    height: { type: 'string' },
    profile: { type: 'string' },
    episode: { type: 'string' },
    defaults: { type: 'string' },
    'aroll-dir': { type: 'string', default: 'assets/aroll' },
    'aroll-ext': { type: 'string', default: '.mp4' },
    out: { type: 'string' },
    'public-link': { type: 'string', default: 'clip' },
    'safe-top': { type: 'string' },
    'safe-bottom': { type: 'string' },
    'safe-left': { type: 'string' },
    'safe-right': { type: 'string' },
  },
});

if (positionals.length !== 1) {
  die('usage: node gen-props.mjs <clip-dir> --audio <path> --ass <path> [flags]  (see README.md)');
}
for (const required of ['audio', 'ass']) {
  if (flags[required] === undefined) die(`--${required} is required`);
}

const num = (name, raw) => {
  if (raw === undefined) return undefined;
  const v = Number(raw);
  if (!Number.isFinite(v)) die(`--${name} must be a number, got ${JSON.stringify(raw)}`);
  return v;
};

const clipDir = resolve(positionals[0]);
if (!existsSync(clipDir) || !statSync(clipDir).isDirectory()) die(`clip dir not found: ${clipDir}`);

/** Resolve a user-supplied path against the clip dir and return it relative to the clip dir. */
const inClipDir = (path, label) => {
  const abs = isAbsolute(path) ? path : resolve(clipDir, path);
  const rel = relative(clipDir, abs);
  if (rel.startsWith('..') || isAbsolute(rel)) {
    die(`${label} must live inside the clip dir (${clipDir}), got ${abs}`);
  }
  if (!existsSync(abs)) die(`${label} not found: ${abs}`);
  return rel.split('\\').join('/');
};

// ---------------------------------------------------------------------------
// Manifests
// ---------------------------------------------------------------------------

const clip = parseOrDie(ClipSchema, readYaml(join(clipDir, 'clip.yaml'), 'clip.yaml'), 'clip.yaml');

const episodePath = flags.episode === undefined ? resolve(clipDir, '..', '..', 'episode.yaml') : resolve(flags.episode);
const episode = parseOrDie(
  EpisodeSchema,
  readYaml(episodePath, `episode.yaml (looked at ${episodePath}; pass --episode to override)`),
  'episode.yaml',
);

const profile = flags.profile === undefined
  ? episode.platform_profiles[0]
  : episode.platform_profiles.find((p) => p.name === flags.profile);
if (profile === undefined) {
  die(`--profile ${flags.profile} is not in episode.yaml platform_profiles (${episode.platform_profiles.map((p) => p.name).join(', ')})`);
}

const [profileWidth, profileHeight] = profile.resolution.split('x').map(Number);
const width = num('width', flags.width) ?? profileWidth;
const height = num('height', flags.height) ?? profileHeight;
const fps = num('fps', flags.fps) ?? profile.fps;

const [clipWidth, clipHeight] = clip.output.resolution.split('x').map(Number);
if (clipWidth !== width || clipHeight !== height) {
  die(`clip.yaml output.resolution is ${clip.output.resolution} but the render is ${width}x${height} — fix the manifest or the flags, do not render a mismatch`);
}
if (!near(clip.output.fps, fps)) {
  die(`clip.yaml output.fps is ${clip.output.fps} but the render is ${fps} fps`);
}
if (clip.output.duration_s > profile.max_duration_s) {
  die(`clip is ${clip.output.duration_s}s, over the ${profile.name} limit of ${profile.max_duration_s}s`);
}

const speakerIds = new Set(episode.speakers.map((s) => s.id));

// ---------------------------------------------------------------------------
// Safe zones
// ---------------------------------------------------------------------------

const fileSafeZone = flags.defaults === undefined
  ? {}
  : (readYaml(resolve(flags.defaults), 'defaults yaml')?.safe_zones ?? {});

const safeZone = {
  top: num('safe-top', flags['safe-top']) ?? fileSafeZone.top ?? DEFAULT_SAFE_ZONE.top,
  bottom: num('safe-bottom', flags['safe-bottom']) ?? fileSafeZone.bottom ?? DEFAULT_SAFE_ZONE.bottom,
  left: num('safe-left', flags['safe-left']) ?? fileSafeZone.left ?? DEFAULT_SAFE_ZONE.left,
  right: num('safe-right', flags['safe-right']) ?? fileSafeZone.right ?? DEFAULT_SAFE_ZONE.right,
};
for (const [edge, value] of Object.entries(safeZone)) {
  if (value < 0) die(`safe zone ${edge} is negative (${value})`);
}
if (safeZone.top + safeZone.bottom >= height || safeZone.left + safeZone.right >= width) {
  die(`safe zone insets leave no usable area inside ${width}x${height}`);
}

// ---------------------------------------------------------------------------
// Timeline
// ---------------------------------------------------------------------------

const toFrame = (seconds) => Math.round(seconds * fps);

const parseTransition = (raw, segId) => {
  if (raw === 'cut') return { kind: 'cut' };
  const m = /^crossfade-(\d+)f$/.exec(raw);
  if (m === null) {
    die(`${segId}: unsupported transition ${JSON.stringify(raw)} — expected "cut" or "crossfade-<N>f"`);
  }
  const frames = Number(m[1]);
  if (frames < 1) die(`${segId}: crossfade-${frames}f must be at least 1 frame`);
  return { kind: 'crossfade', frames };
};

const assetsById = new Map(clip.assets.map((a) => [a.id, a]));

const arollSources = (segment) => {
  const dir = flags['aroll-dir'];
  const ext = flags['aroll-ext'];
  const treatment = segment.visual.treatment;
  const speakerOf = (prefix) => {
    const speaker = treatment.slice(prefix.length);
    if (!speakerIds.has(speaker)) {
      die(`${segment.id}: treatment "${treatment}" names speaker "${speaker}", which is not in episode.yaml speakers (${[...speakerIds].join(', ')})`);
    }
  };

  if (treatment.startsWith('closeup-')) speakerOf('closeup-');
  else if (treatment.startsWith('reaction-')) speakerOf('reaction-');
  else if (treatment.startsWith('blur-fill-')) speakerOf('blur-fill-');
  else if (treatment !== 'splitscreen' && treatment !== 'source-frame') {
    die(`${segment.id}: unsupported aroll treatment ${JSON.stringify(treatment)} — expected one of ${AROLL_TREATMENTS.join(', ')}`);
  }

  const names = treatment === 'splitscreen'
    ? [`${segment.id}-top${ext}`, `${segment.id}-bottom${ext}`]
    : [`${segment.id}${ext}`];
  return names.map((name) => inClipDir(join(dir, name), `${segment.id}: A-roll clip (staged by scripts/extract_segments.py)`));
};

const brollSources = (segment) => {
  if (!BROLL_TREATMENTS.includes(segment.visual.treatment)) {
    die(`${segment.id}: unsupported broll treatment ${JSON.stringify(segment.visual.treatment)} — expected one of ${BROLL_TREATMENTS.join(', ')}`);
  }
  if (segment.visual.asset_id === null) die(`${segment.id}: broll segment has no asset_id`);
  const asset = assetsById.get(segment.visual.asset_id);
  if (asset === undefined) die(`${segment.id}: asset_id ${segment.visual.asset_id} is not in clip.yaml assets[]`);
  if (!asset.used_in_segments.includes(segment.id)) {
    die(`asset ${asset.id} does not list ${segment.id} in used_in_segments — manifest disagrees with itself`);
  }
  const duration = segment.output_out - segment.output_in;
  if (asset.duration_s + EPS < duration) {
    die(`asset ${asset.id} is ${asset.duration_s}s but ${segment.id} needs ${duration.toFixed(2)}s`);
  }
  return [inClipDir(asset.file, `${segment.id}: asset ${asset.id} file`)];
};

const creditFor = (segment) => {
  if (segment.visual.kind !== 'broll') return null;
  const asset = assetsById.get(segment.visual.asset_id);
  if (!asset.credit_required) return null;
  const provider = asset.provider.charAt(0).toUpperCase() + asset.provider.slice(1);
  return asset.creator.trim() === '' ? `Video from ${provider}` : `Video by ${asset.creator} on ${provider}`;
};

if (!near(clip.timeline[0].output_in, 0)) {
  die(`timeline does not start at 0.0 (${clip.timeline[0].output_in})`);
}

const segments = clip.timeline.map((segment, i) => {
  const previous = clip.timeline[i - 1];
  if (previous !== undefined && !near(previous.output_out, segment.output_in)) {
    die(`timeline gap/overlap between ${previous.id} (out ${previous.output_out}) and ${segment.id} (in ${segment.output_in})`);
  }
  const outputDuration = segment.output_out - segment.output_in;
  const sourceDuration = segment.source_out - segment.source_in;
  if (!near(outputDuration, sourceDuration)) {
    die(`${segment.id}: output duration ${outputDuration.toFixed(3)}s != source duration ${sourceDuration.toFixed(3)}s — this pipeline has no speed changes`);
  }
  if (outputDuration <= 0) die(`${segment.id}: non-positive duration`);
  if (!speakerIds.has(segment.speaker)) {
    die(`${segment.id}: speaker ${JSON.stringify(segment.speaker)} is not in episode.yaml speakers`);
  }

  const startFrame = toFrame(segment.output_in);
  const durationInFrames = toFrame(segment.output_out) - startFrame;
  if (durationInFrames < 1) {
    die(`${segment.id}: rounds to ${durationInFrames} frames at ${fps} fps — a segment must render at least one frame`);
  }

  // Throws on any motion string the renderer cannot execute.
  parseMotion(segment.visual.motion);

  return {
    id: segment.id,
    startFrame,
    durationInFrames,
    speaker: segment.speaker,
    kind: segment.visual.kind,
    treatment: segment.visual.treatment,
    motion: segment.visual.motion,
    sources: segment.visual.kind === 'aroll' ? arollSources(segment) : brollSources(segment),
    transitionOut: parseTransition(segment.transition, segment.id),
    credit: creditFor(segment),
  };
});

const durationInFrames = toFrame(clip.output.duration_s);
const lastSegment = segments[segments.length - 1];
if (lastSegment.startFrame + lastSegment.durationInFrames !== durationInFrames) {
  die(`clip.output.duration_s (${clip.output.duration_s}s = ${durationInFrames}f) disagrees with the timeline end (${lastSegment.startFrame + lastSegment.durationInFrames}f)`);
}

segments.forEach((segment, i) => {
  if (segment.transitionOut.kind !== 'crossfade') return;
  const next = segments[i + 1];
  if (next === undefined) {
    die(`${segment.id} is the last segment and cannot cross-fade into anything — use "cut"`);
  }
  const frames = segment.transitionOut.frames;
  if (frames > segment.durationInFrames || frames > next.durationInFrames) {
    die(`${segment.id}: crossfade-${frames}f is longer than ${segment.id} (${segment.durationInFrames}f) or ${next.id} (${next.durationInFrames}f)`);
  }
});

const usedAssetIds = new Set(clip.timeline.filter((s) => s.visual.kind === 'broll').map((s) => s.visual.asset_id));
for (const asset of clip.assets) {
  if (!usedAssetIds.has(asset.id)) {
    die(`asset ${asset.id} (${asset.file}) is not used by any timeline segment — remove it or use it`);
  }
}

// ---------------------------------------------------------------------------
// Audio + subtitles
// ---------------------------------------------------------------------------

const audioSrc = inClipDir(flags.audio, 'assembled audio (--audio)');
const assPath = resolve(clipDir, flags.ass);
if (!existsSync(assPath)) die(`aligned subtitles (--ass) not found: ${assPath}`);
const ass = parseAss(readFileSync(assPath, 'utf8'));

const scaleX = width / ass.playResX;
const scaleY = height / ass.playResY;

const styleSignature = (s) => `${s.fontName}|${s.fontSize}|${s.outline}|${s.outlineColour}|${s.shadow}`;
const firstStyle = ass.events[0].style;
for (const event of ass.events) {
  if (styleSignature(event.style) !== styleSignature(firstStyle)) {
    die(`.ass mixes typographic styles (${firstStyle.name} vs ${event.style.name}) — one clip renders one subtitle type size`);
  }
}

const FONT_FAMILIES = { 'inter semibold': 'Inter', 'inter': 'Inter' };
const family = FONT_FAMILIES[firstStyle.fontName.trim().toLowerCase()];
if (family === undefined) {
  die(`.ass style font ${JSON.stringify(firstStyle.fontName)} is not bundled with this template (only ${Object.keys(FONT_FAMILIES).join(', ')} — see public/fonts/)`);
}
if (FONT_FAMILIES[clip.subtitles.font.trim().toLowerCase()] !== family) {
  die(`clip.yaml subtitles.font (${clip.subtitles.font}) disagrees with the .ass style font (${firstStyle.fontName})`);
}

const allowedColors = new Set([clip.subtitles.base_color, ...clip.subtitles.emphasis_palette].map((c) => c.toLowerCase()));
const checkColor = (color, where) => {
  if (!/^#[0-9a-f]{6}$/i.test(color)) {
    die(`${where}: colour ${color} is not opaque #RRGGBB — this renderer does not do subtitle alpha`);
  }
  if (!allowedColors.has(color.toLowerCase())) {
    die(`${where}: colour ${color} is outside the clip's palette (${[...allowedColors].join(', ')}) — the emphasis palette is deliberately restrained`);
  }
};

const alignX = (alignment) => (alignment % 3 === 1 ? 'left' : alignment % 3 === 2 ? 'center' : 'right');
const anchorY = (alignment) => (alignment <= 3 ? 'bottom' : alignment <= 6 ? 'middle' : 'top');

const fontSizePx = firstStyle.fontSize * scaleY;
const lineHeightEm = 1.2;

const subtitles = ass.events.map((event, i) => {
  const where = `.ass event ${i + 1} (${event.start.toFixed(2)}-${event.end.toFixed(2)}s)`;
  if (event.end <= event.start) die(`${where}: end is not after start`);
  if (event.end > clip.output.duration_s + EPS) {
    die(`${where}: ends after the clip (${clip.output.duration_s}s)`);
  }
  const previous = ass.events[i - 1];
  if (previous !== undefined && event.start + EPS < previous.end) {
    die(`${where}: overlaps the previous event (ends ${previous.end.toFixed(2)}s)`);
  }

  for (const span of event.spans) checkColor(span.color, where);
  if (event.style.primaryColour.toLowerCase() !== clip.subtitles.base_color.toLowerCase()) {
    die(`${where}: style ${event.style.name} base colour ${event.style.primaryColour} != clip.yaml subtitles.base_color ${clip.subtitles.base_color}`);
  }

  const anchor = anchorY(event.alignment);
  const marginV = event.marginV !== 0 ? event.marginV : event.style.marginV;
  const posY = event.posY !== null
    ? event.posY * scaleY
    : anchor === 'bottom'
      ? (ass.playResY - marginV) * scaleY
      : anchor === 'top'
        ? marginV * scaleY
        : height / 2;

  const lineCount = event.text.split('\n').length;
  const blockHeight = lineCount * fontSizePx * lineHeightEm;
  const top = anchor === 'bottom' ? posY - blockHeight : anchor === 'top' ? posY : posY - blockHeight / 2;
  const bottom = top + blockHeight;
  if (top + EPS < safeZone.top || bottom > height - safeZone.bottom + EPS) {
    die(`${where}: renders at y ${top.toFixed(0)}-${bottom.toFixed(0)}px, outside the safe zone (${safeZone.top}-${height - safeZone.bottom}px) — fix the .ass margins and re-run scripts/validate_subtitles.py`);
  }

  return {
    startFrame: toFrame(event.start),
    endFrame: toFrame(event.end),
    text: event.text,
    styledSpans: event.spans.map((s) => ({ text: s.text, color: s.color, bold: s.bold, italic: s.italic })),
    posY,
    anchorY: anchor,
    alignX: alignX(event.alignment),
  };
});

// A credit line owns the bottom-left of the safe area while it is on screen;
// a subtitle may not be parked on top of it.
for (const segment of segments.filter((s) => s.credit !== null)) {
  const segEnd = segment.startFrame + segment.durationInFrames;
  for (const event of subtitles) {
    if (event.endFrame <= segment.startFrame || event.startFrame >= segEnd) continue;
    const floor = height - safeZone.bottom - CREDIT_RESERVE_PX;
    const bottomEdge = event.anchorY === 'bottom' ? event.posY : event.posY + fontSizePx * lineHeightEm;
    if (bottomEdge > floor + EPS) {
      die(`subtitle at frame ${event.startFrame} sits at y ${bottomEdge.toFixed(0)}px and collides with the ${segment.id} credit line (floor ${floor}px) — raise the .ass MarginV for that line`);
    }
  }
}

// ---------------------------------------------------------------------------
// Public-dir symlink + write
// ---------------------------------------------------------------------------

const publicDir = join(TEMPLATE_DIR, 'public');
mkdirSync(publicDir, { recursive: true });
const linkPath = join(publicDir, flags['public-link']);
if (existsSync(linkPath) || lstatSync(linkPath, { throwIfNoEntry: false }) !== undefined) {
  if (!lstatSync(linkPath).isSymbolicLink()) {
    die(`${linkPath} exists and is not a symlink — refusing to replace it`);
  }
  rmSync(linkPath);
}
symlinkSync(clipDir, linkPath, 'dir');

const props = {
  schemaVersion: SCHEMA_VERSION,
  clipId: clip.clip.id,
  title: clip.clip.title,
  width,
  height,
  fps,
  durationInFrames,
  assetRoot: flags['public-link'],
  audioSrc,
  safeZone,
  subtitleStyle: {
    fontFamily: family,
    fontWeight: 600,
    emphasisFontWeight: 700,
    fontSizePx,
    lineHeightEm,
    outlineWidthPx: firstStyle.outline * scaleY,
    outlineColor: firstStyle.outlineColour,
    shadowPx: firstStyle.shadow * scaleY,
    maxWidthPx: width - safeZone.left - safeZone.right,
    leftPx: safeZone.left,
  },
  segments,
  subtitles,
};

const outPath = flags.out === undefined ? join(TEMPLATE_DIR, 'props.json') : resolve(flags.out);
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${JSON.stringify(props, null, 2)}\n`);

process.stdout.write(
  `${outPath}\n  ${segments.length} segments, ${subtitles.length} subtitle events, ` +
  `${durationInFrames} frames @ ${fps}fps (${clip.output.duration_s}s), ${width}x${height}\n` +
  `  public/${flags['public-link']} -> ${clipDir}\n`,
);
