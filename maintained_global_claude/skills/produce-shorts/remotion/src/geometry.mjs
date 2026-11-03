// Shot geometry shared by gen-props.mjs (refuses a bad props.json at generation time), schema.ts (refuses it again at
// render time) and Short.tsx (draws it). scripts/frame_segments.py decides the numbers; nothing here invents any.
//
// A panel is one video rectangle of the output frame (`rect`) showing one source video. Its shots tile the segment in
// time. A shot crops a `cropW` x `cropH` window of the source (top-left linearly interpolated between `keys`, frames
// relative to the segment start) and draws it, scaled uniformly, into `dst` (panel-relative). `backdrop` non-null
// means the crop is a smaller sharp foreground over a blurred, darkened copy of itself. `tile` is the speaker's tile on
// the source frame: the crop must stay inside it, so a crop never shows a neighbouring speaker.

const EPS = 0.51; // px: the geometry is integer pixels; scaled rounding may be off by half a pixel

const inside = (inner, outer) =>
  inner.x >= outer.x - EPS && inner.y >= outer.y - EPS &&
  inner.x + inner.w <= outer.x + outer.w + EPS && inner.y + inner.h <= outer.y + outer.h + EPS;

/** Every problem with a panel's geometry, as readable strings (empty = valid). */
export function panelProblems(panel, durationInFrames) {
  const problems = [];
  const source = { x: 0, y: 0, w: panel.sourceDims.w, h: panel.sourceDims.h };
  const frame = { x: 0, y: 0, w: panel.rect.w, h: panel.rect.h };
  let next = 0;
  panel.shots.forEach((shot, i) => {
    const at = `shot ${i} (frames ${shot.fromFrame}-${shot.toFrame})`;
    if (shot.fromFrame !== next) problems.push(`${at} starts at frame ${shot.fromFrame}, the previous shot ended at ${next}`);
    if (shot.toFrame <= shot.fromFrame) problems.push(`${at} is empty`);
    next = shot.toFrame;
    if (!inside(shot.dst, frame)) problems.push(`${at}: draw rectangle ${JSON.stringify(shot.dst)} is outside the ${panel.rect.w}x${panel.rect.h} panel`);
    if (Math.abs(shot.dst.w * shot.cropH - shot.dst.h * shot.cropW) > shot.cropW + shot.cropH) { // dst sides are rounded to even px: up to 1px off each
      problems.push(`${at}: the ${shot.cropW}x${shot.cropH} crop would be stretched into ${shot.dst.w}x${shot.dst.h}`);
    }
    if (shot.backdrop === null && !(shot.dst.w >= panel.rect.w - EPS || shot.dst.h >= panel.rect.h - EPS)) {
      problems.push(`${at}: a ${shot.dst.w}x${shot.dst.h} crop in a ${panel.rect.w}x${panel.rect.h} panel needs a blur-fill backdrop`);
    }
    shot.keys.forEach((key, k) => {
      const crop = { x: key.x, y: key.y, w: shot.cropW, h: shot.cropH };
      if (!inside(crop, source)) problems.push(`${at} key ${k}: crop ${JSON.stringify(crop)} leaves the ${source.w}x${source.h} source frame`);
      if (shot.tile !== null && !inside(crop, shot.tile)) {
        problems.push(`${at} key ${k}: crop ${JSON.stringify(crop)} leaves the speaker's tile ${JSON.stringify(shot.tile)} — it would show a neighbouring speaker`);
      }
      if (k > 0 && key.frame <= shot.keys[k - 1].frame) problems.push(`${at}: crop keys are not in increasing frame order`);
    });
    if (shot.tile !== null && !inside(shot.tile, source)) problems.push(`${at}: tile ${JSON.stringify(shot.tile)} is outside the source frame`);
  });
  if (panel.shots.length > 0 && panel.shots[0].fromFrame !== 0) problems.push('the first shot does not start on frame 0 of the segment');
  if (next !== durationInFrames) problems.push(`the shots end at frame ${next}, the segment is ${durationInFrames} frames`);
  return problems;
}

/** The shot on a segment-relative frame; frames past the last shot (a crossfade tail) stay on the last one. */
export function shotAt(panel, frame) {
  const shot = panel.shots.find((s) => frame >= s.fromFrame && frame < s.toFrame);
  return shot ?? panel.shots[panel.shots.length - 1];
}

/** Top-left of the crop window (source px) on a segment-relative frame: linear between keys, held outside them. */
export function cropAt(shot, frame) {
  const { keys } = shot;
  if (frame <= keys[0].frame) return { x: keys[0].x, y: keys[0].y };
  for (let i = 1; i < keys.length; i += 1) {
    if (frame <= keys[i].frame) {
      const a = keys[i - 1];
      const b = keys[i];
      const f = (frame - a.frame) / (b.frame - a.frame);
      return { x: a.x + (b.x - a.x) * f, y: a.y + (b.y - a.y) * f };
    }
  }
  const last = keys[keys.length - 1];
  return { x: last.x, y: last.y };
}

// ---------------------------------------------------------------------------------------------------------------------
// Quote layout: a picture overlay in a short. The top panel (`quote.rect`) shows screenshots fitted by
// scripts/quotelayout.py; the bottom half is each segment's `quotePanel` (an ordinary panel, tile invariant included).
// Frames are COMPOSITION frames (absolute), like `startFrame` of a segment.
// ---------------------------------------------------------------------------------------------------------------------

/** Every problem with a quote overlay's geometry, as readable strings (empty = valid). */
export function quoteProblems(quote) {
  const problems = [];
  const frame = { x: quote.rect.x, y: quote.rect.y, w: quote.rect.w, h: quote.rect.h };
  if (quote.endFrame <= quote.startFrame) problems.push(`window ${quote.startFrame}-${quote.endFrame} is empty`);
  if (quote.fadeInFrames + quote.fadeOutFrames > quote.endFrame - quote.startFrame) problems.push('the fades do not fit inside the window');
  let next = quote.startFrame;
  quote.shots.forEach((shot, i) => {
    const at = `screenshot ${i} (${shot.src})`;
    if (shot.fromFrame !== next) problems.push(`${at} starts at frame ${shot.fromFrame}, the previous one ended at ${next}`);
    if (shot.toFrame <= shot.fromFrame) problems.push(`${at} is empty`);
    next = shot.toFrame;
    if (i === 0 && shot.dissolveFrames !== 0) problems.push(`${at}: no dissolve into the first screenshot (use the fade)`);
    if (shot.dissolveFrames > shot.toFrame - shot.fromFrame) problems.push(`${at}: the dissolve is longer than the shot`);
    if (Math.abs(shot.dst.w * shot.srcH - shot.dst.h * shot.srcW) > shot.srcW + shot.srcH) {
      problems.push(`${at}: the ${shot.srcW}x${shot.srcH} screenshot would be stretched into ${shot.dst.w}x${shot.dst.h}`);
    }
    const [z0, z1] = shot.zoom;
    if (z0 < 1 || z1 < 1 || z0 > 2 || z1 > 2) problems.push(`${at}: zoom [${z0}, ${z1}] is outside 1.0-2.0`);
    const zoom = Math.max(z0, z1);
    const grown = {
      x: shot.dst.x + shot.dst.w / 2 - (shot.dst.w * zoom) / 2, y: shot.dst.y + shot.dst.h / 2 - (shot.dst.h * zoom) / 2,
      w: shot.dst.w * zoom, h: shot.dst.h * zoom,
    };
    const local = { x: 0, y: 0, w: frame.w, h: frame.h };
    if (!inside(grown, local)) problems.push(`${at}: the screenshot at its full push-in ${JSON.stringify(grown)} leaves the ${frame.w}x${frame.h} panel`);
  });
  if (quote.shots.length === 0) problems.push('no screenshots');
  else if (next !== quote.endFrame) problems.push(`the screenshots end at frame ${next}, the window ends at ${quote.endFrame}`);
  if (quote.shots.length > 0 && quote.shots[0].fromFrame !== quote.startFrame) problems.push('the first screenshot does not start with the window');
  return problems;
}

/** Opacity of the whole quote layout on a composition frame (0 outside the window): fade in, hold, fade out. */
export function quoteOpacity(quote, frame) {
  if (frame < quote.startFrame || frame >= quote.endFrame) return 0;
  const fadeIn = quote.fadeInFrames > 0 ? Math.min(1, (frame - quote.startFrame + 1) / (quote.fadeInFrames + 1)) : 1;
  const fadeOut = quote.fadeOutFrames > 0 ? Math.min(1, (quote.endFrame - frame) / (quote.fadeOutFrames + 1)) : 1;
  return Math.min(fadeIn, fadeOut);
}

/** The screenshots drawn on a frame, bottom to top, each with its opacity (a dissolve fades the new one over the old). */
export function quoteLayers(quote, frame) {
  const layers = [];
  quote.shots.forEach((shot, k) => {
    const following = quote.shots[k + 1];
    const stillShown = frame < shot.toFrame + (following ? following.dissolveFrames : 0);
    if (frame < shot.fromFrame || !stillShown) return;
    const opacity = shot.dissolveFrames > 0 ? Math.min(1, (frame - shot.fromFrame + 1) / (shot.dissolveFrames + 1)) : 1;
    const span = Math.max(1, shot.toFrame - shot.fromFrame - 1);
    const progress = Math.min(1, Math.max(0, (frame - shot.fromFrame) / span));
    layers.push({ index: k, shot, opacity, scale: shot.zoom[0] + (shot.zoom[1] - shot.zoom[0]) * progress });
  });
  return layers;
}
