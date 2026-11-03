#!/usr/bin/env node
// gen-props.mjs — clip.yaml (+ episode defaults + assembled audio + aligned .ass)
//                 -> props.json, the single input to the Short composition.
//
//   node gen-props.mjs <clip-dir> --audio <path> --ass <path> \
//        [--fps 30 --width 1080 --height 1920] [--profile youtube-shorts]
//        [--episode <episode.yaml>] --defaults <config/defaults.yaml>
//        [--out props.json] [--public-link clip] [--episode-link episode]
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
import { panelProblems } from './src/geometry.mjs';

const TEMPLATE_DIR = dirname(fileURLToPath(import.meta.url));
const EPS = 0.01; // the pipeline-wide comparison epsilon (references/schemas.md)
const SCHEMA_VERSION = 1;

// Mirrors config/defaults.yaml `safe_zones` (1080x1920 reference frame).
const DEFAULT_SAFE_ZONE = { top: 200, bottom: 320, left: 60, right: 120 };

const AROLL_TREATMENTS = ['closeup-<speaker>', 'splitscreen'];
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
    out: { type: 'string' },
    'public-link': { type: 'string', default: 'clip' },
    'episode-link': { type: 'string', default: 'episode' },
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
if (profile.max_duration_s !== null && clip.output.duration_s > profile.max_duration_s) {
  die(`clip is ${clip.output.duration_s}s, over the ${profile.name} limit of ${profile.max_duration_s}s`);
}

const speakerIds = new Set(episode.speakers.map((s) => s.id));

// ---------------------------------------------------------------------------
// Safe zones
// ---------------------------------------------------------------------------

if (flags.defaults === undefined) {
  die('--defaults <skill>/config/defaults.yaml is required — the karaoke caption colours and active weight (subtitles.active_color, subtitles.active_font_weight) live there');
}
const defaultsYaml = readYaml(resolve(flags.defaults), 'defaults yaml');
const fileSafeZone = defaultsYaml?.safe_zones ?? {};

// Karaoke highlight: the word being spoken is drawn in activeColor at activeFontWeight.
const karaokeCfg = defaultsYaml?.subtitles ?? {};
const activeColor = karaokeCfg.active_color;
const activeFontWeight = karaokeCfg.active_font_weight;
if (typeof activeColor !== 'string' || !/^#[0-9a-f]{6}$/i.test(activeColor)) {
  die(`${flags.defaults}: subtitles.active_color must be an opaque #RRGGBB, got ${JSON.stringify(activeColor)}`);
}
// Bundled Inter is a variable font (wght 100-900, src/fonts.ts); align_subtitles.py has measured widths for these.
if (![600, 700, 800, 900].includes(activeFontWeight)) {
  die(`${flags.defaults}: subtitles.active_font_weight must be one of 600, 700, 800, 900, got ${JSON.stringify(activeFontWeight)}`);
}

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

// scripts/frame_segments.py decides the framing of every a-roll segment; this copies its geometry into props.json.
const framingPath = join(clipDir, 'assets', 'framing.json');
const framing = existsSync(framingPath)
  ? JSON.parse(readFileSync(framingPath, 'utf8'))
  : die(`${framingPath} not found — run scripts/frame_segments.py (prep_short.py does)`);

const episodeRoot = dirname(episodePath);

/** Resolve a path relative to the episode root; the file must exist (Remotion opens it by URL). */
const inEpisodeRoot = (path, label) => {
  const abs = resolve(episodeRoot, path);
  const rel = relative(episodeRoot, abs);
  if (rel.startsWith('..') || isAbsolute(rel)) die(`${label} must live inside the episode root (${episodeRoot}), got ${abs}`);
  if (!existsSync(abs)) die(`${label} not found: ${abs}`);
  return rel.split('\\').join('/');
};

const rectOf = ([x, y, w, h]) => ({ x, y, w, h });

const arollPanels = (segment) => {
  const treatment = segment.visual.treatment;
  const speakerOf = (prefix) => {
    const speaker = treatment.slice(prefix.length);
    if (!speakerIds.has(speaker)) {
      die(`${segment.id}: treatment "${treatment}" names speaker "${speaker}", which is not in episode.yaml speakers (${[...speakerIds].join(', ')})`);
    }
    return speaker;
  };
  const wantSpeakers = treatment.startsWith('closeup-')
    ? { full: speakerOf('closeup-') }
    : treatment === 'splitscreen'
      ? Object.fromEntries(['top', 'bottom'].map((slot, k) => [slot, segment.visual.speakers?.[k]]))
      : die(`${segment.id}: unsupported aroll treatment ${JSON.stringify(treatment)} — expected one of ${AROLL_TREATMENTS.join(', ')}`);

  const entry = framing.segments[segment.id]
    ?? die(`${segment.id}: no framing in ${framingPath} — re-run scripts/frame_segments.py`);
  if (entry.treatment !== treatment) {
    die(`${segment.id}: ${framingPath} was framed for treatment ${entry.treatment}, clip.yaml now says ${treatment} — re-run scripts/frame_segments.py`);
  }
  const slots = entry.panels.map((p) => p.slot).join('+');
  if (slots !== Object.keys(wantSpeakers).join('+')) {
    die(`${segment.id}: ${framingPath} has panels ${slots}, ${treatment} needs ${Object.keys(wantSpeakers).join('+')} — re-run scripts/frame_segments.py`);
  }
  return entry.panels.map((panel) => {
    if (panel.speaker !== wantSpeakers[panel.slot]) {
      die(`${segment.id} ${panel.slot}: framed for ${panel.speaker}, clip.yaml wants ${wantSpeakers[panel.slot]} — re-run scripts/frame_segments.py`);
    }
    return panelProps(segment, panel);
  });
};

/** One framing.json panel as props: shots in segment-relative frames, source file checked on disk, geometry re-validated. */
const panelProps = (segment, panel) => {
  {
    const startFrame = toFrame(segment.output_in);
    const first = panel.shots[0];
    const last = panel.shots[panel.shots.length - 1];
    if (!near(first.t0, segment.output_in) || !near(last.t1, segment.output_out)) {
      die(`${segment.id} ${panel.slot}: framed for ${first.t0}-${last.t1}s, clip.yaml has ${segment.output_in}-${segment.output_out}s — re-run scripts/frame_segments.py`);
    }
    const shots = panel.shots.map((shot) => ({
      fromFrame: toFrame(shot.t0) - startFrame,
      toFrame: toFrame(shot.t1) - startFrame,
      cropW: shot.crop.w,
      cropH: shot.crop.h,
      keys: shot.crop.keys.map(([t, x, y]) => ({ frame: (t - segment.output_in) * fps, x, y })),
      dst: rectOf(shot.dst),
      backdrop: shot.backdrop === null ? null : { blurPx: shot.backdrop.blur_px, brightness: shot.backdrop.brightness },
      tile: shot.tile === null ? null : { x: shot.tile[0], y: shot.tile[1], w: shot.tile[2] - shot.tile[0], h: shot.tile[3] - shot.tile[1] },
    }));
    const result = {
      slot: panel.slot,
      rect: rectOf(panel.rect),
      source: inEpisodeRoot(panel.source, `${segment.id} ${panel.slot}: source video`),
      sourceDims: { w: panel.source_dims[0], h: panel.source_dims[1] },
      trimBeforeFrame: toFrame(panel.source_start_s),
      shots,
    };
    const problems = panelProblems(result, toFrame(segment.output_out) - startFrame);
    if (problems.length > 0) die(`${segment.id} ${panel.slot}: bad geometry in ${framingPath}:\n  ${problems.join('\n  ')}`);
    return result;
  }
};

// ---------------------------------------------------------------------------------------------------------------------
// Quote layout: clip.yaml overlays of a short (fullscreen stills) + scripts/frame_segments.py's quote geometry.
// ---------------------------------------------------------------------------------------------------------------------

const STILL_EXT = /\.(png|jpe?g|webp)$/i;

/** Why a short cannot draw this overlay (empty = it can). Mirrors scripts/quotelayout.py unsupported(). */
const unsupportedForShort = (ov) => {
  if (ov.mode !== 'fullscreen') return [`mode ${JSON.stringify(ov.mode)} (only fullscreen picture overlays)`];
  const why = [];
  if (ov.lines.length > 0 || ov.box !== null || ov.from_box !== null) why.push('text lines / box / from_box');
  if (ov.label !== null) why.push('label');
  if (ov.shots.length === 0) why.push('no shots');
  ov.shots.forEach((shot, k) => {
    if (shot.grid !== null) why.push(`shot ${k + 1}: a grid`);
    else if (shot.asset === null || !STILL_EXT.test(shot.asset)) why.push(`shot ${k + 1}: ${JSON.stringify(shot.asset)} is not a still image (png/jpg/webp)`);
    if (shot.crop !== null) why.push(`shot ${k + 1}: crop`);
    if (shot.src_in !== null || shot.src_out !== null || shot.speed !== 1 || shot.hold_last) why.push(`shot ${k + 1}: video range`);
  });
  return why;
};

/** The provenance ledger entry of a B-roll file (by file name, as scripts/broll.py indexes it); dies without one. */
const provenanceFor = (() => {
  let ledger = null;
  return (asset) => {
    if (clip.broll === null) die(`clip.yaml has overlays but no broll: block (provenance, protected_tail_s)`);
    if (ledger === null) {
      const path = resolve(clipDir, clip.broll.provenance);
      if (!existsSync(path)) die(`B-roll provenance ledger not found: ${path} — every overlay asset needs an entry (source URL, licence, permission)`);
      ledger = new Map(JSON.parse(readFileSync(path, 'utf8')).map((e) => [String(e.file).split('/').pop(), e]));
    }
    const entry = ledger.get(asset.split('/').pop());
    if (entry === undefined) die(`broll/${asset}: no entry in ${clip.broll.provenance} — real, credited B-roll only; provenance is mandatory`);
    for (const key of ['source_url', 'licence', 'permission']) {
      if (!entry[key]) die(`broll/${asset}: provenance entry lacks ${key}`);
    }
    return entry;
  };
})();

const quotes = clip.overlays.map((ov) => {
  const why = unsupportedForShort(ov);
  if (why.length > 0) die(`overlay ${ov.id}: not implemented for shorts — ${why.join('; ')}`);
  const record = (framing.quotes ?? []).find((q) => q.id === ov.id)
    ?? die(`overlay ${ov.id}: no quote geometry in ${framingPath} — re-run scripts/frame_segments.py`);
  if (!near(record.start, ov.start) || !near(record.end, ov.end) || record.shots.length !== ov.shots.length) {
    die(`overlay ${ov.id}: ${framingPath} was framed for ${record.start}-${record.end}s with ${record.shots.length} screenshot(s), clip.yaml has ${ov.start}-${ov.end}s with ${ov.shots.length} — re-run scripts/frame_segments.py`);
  }
  const startFrame = toFrame(ov.start);
  const endFrame = toFrame(ov.end);
  return {
    id: ov.id,
    startFrame,
    endFrame,
    fadeInFrames: ov.fade_in_frames,
    fadeOutFrames: ov.fade_out_frames,
    rect: rectOf(record.rect),
    backdrop: { blurPx: record.backdrop.blur_px, brightness: record.backdrop.brightness },
    shots: record.shots.map((shot, k) => {
      provenanceFor(shot.asset);
      if (shot.asset !== ov.shots[k].asset) die(`overlay ${ov.id} shot ${k + 1}: framed for ${shot.asset}, clip.yaml has ${ov.shots[k].asset} — re-run scripts/frame_segments.py`);
      return {
        fromFrame: k === 0 ? startFrame : toFrame(shot.t0),
        toFrame: k === record.shots.length - 1 ? endFrame : toFrame(shot.t1),
        src: inClipDir(`broll/${shot.asset}`, `overlay ${ov.id} shot ${k + 1} screenshot`),
        srcW: shot.src_dims[0],
        srcH: shot.src_dims[1],
        dst: rectOf(shot.dst),
        zoom: shot.zoom,
        dissolveFrames: shot.dissolve_frames,
      };
    }),
  };
});

/** The bottom panel a segment shows while a quote overlay covers it (null when none does). */
const quotePanelFor = (segment) => {
  const startFrame = toFrame(segment.output_in);
  const endFrame = toFrame(segment.output_out);
  const covered = quotes.some((q) => startFrame < q.endFrame && endFrame > q.startFrame);
  const panel = framing.segments[segment.id]?.quote ?? null;
  if (!covered) {
    if (panel !== null) die(`${segment.id}: ${framingPath} has a quote panel but no overlay covers the segment — re-run scripts/frame_segments.py`);
    return null;
  }
  if (panel === null) die(`${segment.id}: a quote overlay covers it but ${framingPath} has no quote panel — re-run scripts/frame_segments.py`);
  if (panel.speaker !== segment.speaker) {
    die(`${segment.id} quote: framed for ${panel.speaker}, the segment's speaker is ${segment.speaker} — re-run scripts/frame_segments.py`);
  }
  return panelProps(segment, panel);
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
    sources: segment.visual.kind === 'aroll' ? [] : brollSources(segment),
    panels: segment.visual.kind === 'aroll' ? arollPanels(segment) : null,
    quotePanel: segment.visual.kind === 'aroll' ? quotePanelFor(segment) : null,
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
// Position per layout run (scripts/align_subtitles.py writes it next to the .ass; capplace.placements_path).
const placementsPath = assPath.replace(/\.ass$/, '.placements.json');
if (!existsSync(placementsPath)) {
  die(`caption positions per layout (${placementsPath}) not found — re-run scripts/align_subtitles.py`);
}
const placementsFile = JSON.parse(readFileSync(placementsPath, 'utf8'));
if (placementsFile.events.length !== ass.events.length) {
  die(`${placementsPath}: ${placementsFile.events.length} cards, the .ass has ${ass.events.length} — re-run scripts/align_subtitles.py`);
}

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

/**
 * Per-word timing from the event's `\k` syllables as @remotion/captions `Caption`s (absolute ms),
 * plus the styled spans re-cut so every visible run names the word it belongs to and whitespace
 * (spaces, row breaks) belongs to none. The validated card is kept as is — this never re-pages.
 */
const karaokeWords = (event, where) => {
  if (event.syllables.length === 0) {
    die(`${where}: no karaoke word timings (\\k tags) — regenerate the .ass with scripts/align_subtitles.py`);
  }
  const startCs = Math.round(event.start * 100);
  const endCs = Math.round(event.end * 100);
  const last = event.syllables[event.syllables.length - 1];
  if (last.offsetCs + last.durationCs !== endCs - startCs) {
    die(`${where}: karaoke durations sum to ${last.offsetCs + last.durationCs}cs but the event lasts ${endCs - startCs}cs — the .ass timing is inconsistent`);
  }
  // Consecutive spans of one syllable form one word; whitespace at a word's edges (the space after it,
  // a row break) belongs to no word, whitespace inside it (a dash riding with its word) stays with it.
  const groups = [];
  for (const span of event.spans) {
    const group = groups[groups.length - 1];
    if (group !== undefined && group.syllable === span.syllable) group.spans.push(span);
    else groups.push({ syllable: span.syllable, spans: [span] });
  }
  const words = [];
  const styledSpans = [];
  const seen = new Set();
  for (const { syllable, spans } of groups) {
    const text = spans.map((s) => s.text).join('');
    const core = text.trim();
    if (core === '') {
      for (const s of spans) styledSpans.push({ text: s.text, color: s.color, bold: s.bold, italic: s.italic, word: null });
      continue;
    }
    if (syllable === null) {
      die(`${where}: ${JSON.stringify(core)} comes before the first \\k tag, so it has no spoken time`);
    }
    if (seen.has(syllable)) die(`${where}: word ${JSON.stringify(core)} is split around other text — one word must be one run`);
    seen.add(syllable);
    const syl = event.syllables[syllable];
    const startMs = (startCs + syl.offsetCs) * 10;
    const word = words.length;
    words.push({ text: core, startMs, endMs: startMs + syl.durationCs * 10, timestampMs: null, confidence: null });
    const coreFrom = text.length - text.trimStart().length;
    const coreTo = text.trimEnd().length;
    let at = 0;
    for (const s of spans) {
      const cuts = [[at, Math.min(at + s.text.length, coreFrom), null], [Math.max(at, coreFrom), Math.min(at + s.text.length, coreTo), word], [Math.max(at, coreTo), at + s.text.length, null]];
      for (const [from, to, owner] of cuts) {
        if (to > from) styledSpans.push({ text: s.text.slice(from - at, to - at), color: s.color, bold: s.bold, italic: s.italic, word: owner });
      }
      at += s.text.length;
    }
  }
  return { styledSpans, words };
};

const fontSizePx = firstStyle.fontSize * scaleY;
const lineHeightEm = 1.2;

// The screen layout on a frame: captions sit at the bottom over a solo shot, on the seam over a split screen, and under the
// seam (top of the bottom panel) over a quote layout, whatever the timeline shows beneath it.
const segmentLayout = (segment) => (segment.kind === 'aroll' && segment.treatment === 'splitscreen' ? 'split' : 'solo');
const layoutAt = (frame) => (quotes.some((q) => q.startFrame <= frame && frame < q.endFrame)
  ? 'quote'
  : segmentLayout(segments.find((s) => s.startFrame <= frame && frame < s.startFrame + s.durationInFrames)));
// Frames on which the layout switches (a cut between segments of different layout, or an overlay opening / closing).
const layoutSwitches = new Set(
  [...segments.map((s) => s.startFrame), ...quotes.flatMap((q) => [q.startFrame, q.endFrame])]
    .filter((f) => f > 0 && f < segments[segments.length - 1].startFrame + segments[segments.length - 1].durationInFrames)
    .filter((f) => layoutAt(f) !== layoutAt(f - 1)),
);

/**
 * One position per layout run of a card: [{fromFrame, layout, posY, anchorY}], fromFrame relative to the card's
 * startFrame. Dies unless the runs open on the card's first frame, switch on exactly the frames the layout switches
 * (and on no other), match the layout they claim, are the band height of the card, and sit inside the safe zone.
 */
const cardPlacements = (event, side, startFrame, endFrame, blockHeight, where) => {
  if (Math.abs(side.start - event.start) > 0.005 || Math.abs(side.end - event.end) > 0.005) {
    die(`${where}: ${placementsPath} has this card at ${side.start.toFixed(2)}-${side.end.toFixed(2)}s — re-run scripts/align_subtitles.py`);
  }
  if (side.runs.length === 0) die(`${where}: no caption position in ${placementsPath}`);
  const runs = side.runs.map((run) => {
    const from = toFrame(run.t0);
    const at = `${where} ${run.layout} run from frame ${from}`;
    if (layoutAt(from) !== run.layout) die(`${at}: the timeline shows a ${layoutAt(from)} layout on that frame`);
    const top = run.top * scaleY;
    const bottom = run.bottom * scaleY;
    if (Math.abs(bottom - top - blockHeight) > 1.5) die(`${at}: band ${top.toFixed(0)}-${bottom.toFixed(0)}px is not the card's ${blockHeight.toFixed(0)}px`);
    if (top + EPS < safeZone.top || bottom > height - safeZone.bottom + EPS) {
      die(`${at}: renders at y ${top.toFixed(0)}-${bottom.toFixed(0)}px, outside the safe zone (${safeZone.top}-${height - safeZone.bottom}px) — fix the placement and re-run scripts/validate_subtitles.py`);
    }
    const anchor = run.placement === 'bottom' ? 'bottom' : run.placement === 'seam' ? 'middle' : 'top';
    const posY = anchor === 'bottom' ? bottom : anchor === 'middle' ? (top + bottom) / 2 : top;
    return { fromFrame: from - startFrame, layout: run.layout, posY, anchorY: anchor };
  });
  if (runs[0].fromFrame !== 0) die(`${where}: the first caption position starts at frame ${startFrame + runs[0].fromFrame}, not the card's first frame ${startFrame}`);
  if (toFrame(side.runs[side.runs.length - 1].t1) !== endFrame) die(`${where}: the caption positions end before the card does (frame ${endFrame})`);
  const switchesInCard = [...layoutSwitches].filter((f) => f > startFrame && f < endFrame).sort((a, b) => a - b);
  const runSwitches = runs.slice(1).map((r) => startFrame + r.fromFrame);
  if (JSON.stringify(runSwitches) !== JSON.stringify(switchesInCard)) {
    die(`${where}: the layout switches on frames [${switchesInCard}] but the caption position switches on [${runSwitches}] — every layout segment the card overlaps needs its own position; re-run scripts/align_subtitles.py`);
  }
  return runs;
};

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
  const assPosY = event.posY !== null
    ? event.posY * scaleY
    : anchor === 'bottom'
      ? (ass.playResY - marginV) * scaleY
      : anchor === 'top'
        ? marginV * scaleY
        : height / 2;

  const lineCount = event.text.split('\n').length;
  const blockHeight = lineCount * fontSizePx * lineHeightEm;
  const startFrame = toFrame(event.start);
  const endFrame = toFrame(event.end);
  const placements = cardPlacements(event, placementsFile.events[i], startFrame, endFrame, blockHeight, where);
  const opening = placements[0];
  if (opening.anchorY !== anchor || Math.abs(opening.posY - assPosY) > 1) {
    die(`${where}: the .ass opens at ${anchor} ${assPosY.toFixed(0)}px but ${placementsPath} at ${opening.anchorY} ${opening.posY.toFixed(0)}px — re-run scripts/align_subtitles.py`);
  }

  const { styledSpans, words } = karaokeWords(event, where);

  return {
    startFrame,
    endFrame,
    text: event.text,
    styledSpans,
    words,
    placements,
    alignX: alignX(event.alignment),
  };
});

// A credit line owns the bottom-left of the safe area while it is on screen;
// a subtitle may not be parked on top of it.
for (const segment of segments.filter((s) => s.credit !== null)) {
  const segEnd = segment.startFrame + segment.durationInFrames;
  for (const event of subtitles) {
    event.placements.forEach((placement, k) => {
      const from = event.startFrame + placement.fromFrame;
      const to = k + 1 < event.placements.length ? event.startFrame + event.placements[k + 1].fromFrame : event.endFrame;
      if (to <= segment.startFrame || from >= segEnd) return;
      const floor = height - safeZone.bottom - CREDIT_RESERVE_PX;
      const blockHeight = event.text.split('\n').length * fontSizePx * lineHeightEm;
      const bottomEdge = placement.anchorY === 'bottom' ? placement.posY : placement.anchorY === 'middle' ? placement.posY + blockHeight / 2 : placement.posY + blockHeight;
      if (bottomEdge > floor + EPS) {
        die(`subtitle at frame ${from} sits at y ${bottomEdge.toFixed(0)}px and collides with the ${segment.id} credit line (floor ${floor}px) — raise the .ass MarginV for that line`);
      }
    });
  }
}

// ---------------------------------------------------------------------------
// Public-dir symlink + write
// ---------------------------------------------------------------------------

const publicDir = join(TEMPLATE_DIR, 'public');
mkdirSync(publicDir, { recursive: true });
const linkDir = (name, target) => {
  const linkPath = join(publicDir, name);
  if (existsSync(linkPath) || lstatSync(linkPath, { throwIfNoEntry: false }) !== undefined) {
    if (!lstatSync(linkPath).isSymbolicLink()) {
      die(`${linkPath} exists and is not a symlink — refusing to replace it`);
    }
    rmSync(linkPath);
  }
  symlinkSync(target, linkPath, process.platform === 'win32' ? 'junction' : 'dir');
};
linkDir(flags['public-link'], clipDir);
linkDir(flags['episode-link'], episodeRoot);

const props = {
  schemaVersion: SCHEMA_VERSION,
  clipId: clip.clip.id,
  title: clip.clip.title,
  width,
  height,
  fps,
  durationInFrames,
  assetRoot: flags['public-link'],
  episodeRoot: flags['episode-link'],
  audioSrc,
  safeZone,
  subtitleStyle: {
    fontFamily: family,
    fontWeight: 600,
    emphasisFontWeight: 700,
    activeColor,
    activeFontWeight,
    fontSizePx,
    lineHeightEm,
    outlineWidthPx: firstStyle.outline * scaleY,
    outlineColor: firstStyle.outlineColour,
    shadowPx: firstStyle.shadow * scaleY,
    maxWidthPx: width - safeZone.left - safeZone.right,
    leftPx: safeZone.left,
  },
  segments,
  quotes,
  subtitles,
};

const outPath = flags.out === undefined ? join(TEMPLATE_DIR, 'props.json') : resolve(flags.out);
mkdirSync(dirname(outPath), { recursive: true });
writeFileSync(outPath, `${JSON.stringify(props, null, 2)}\n`);

process.stdout.write(
  `${outPath}\n  ${segments.length} segments, ${subtitles.length} subtitle events, ` +
  `${durationInFrames} frames @ ${fps}fps (${clip.output.duration_s}s), ${width}x${height}\n` +
  `  public/${flags['public-link']} -> ${clipDir}\n  public/${flags['episode-link']} -> ${episodeRoot}\n`,
);
