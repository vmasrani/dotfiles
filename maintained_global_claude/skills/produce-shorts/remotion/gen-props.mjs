#!/usr/bin/env node
// gen-props.mjs — clip.yaml (+ episode defaults + assembled audio + aligned .ass)
//                 -> props.json, the single input to the Short composition.
//
//   node gen-props.mjs <clip-dir> --audio <path> --ass <path> \
//        [--fps 30 --width 1080 --height 1920] [--profile youtube-shorts]
//        [--episode <episode.yaml>] --defaults <config/defaults.yaml>
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

// The screen layout of a timeline segment: captions sit at the bottom over a solo shot and on the seam over a split screen.
const layoutOf = (segment) => (segment.kind === 'aroll' && segment.treatment === 'splitscreen' ? 'split' : 'solo');
// Frames on which the layout switches (a cut between two segments of different layout).
const layoutSwitches = new Set(segments.slice(1).filter((s, k) => layoutOf(s) !== layoutOf(segments[k])).map((s) => s.startFrame));
const layoutAt = (frame) => layoutOf(segments.find((s) => s.startFrame <= frame && frame < s.startFrame + s.durationInFrames));

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
