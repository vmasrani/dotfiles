// One <Sequence> per timeline segment, in manifest order. Nothing here decides
// anything: every frame, position, file and transition comes from props.json,
// which came from clip.yaml.

import React from 'react';
import { AbsoluteFill, Audio, OffthreadVideo, Sequence, interpolate, useCurrentFrame } from 'remotion';
import { Credits } from './Credits';
import { Subtitles } from './Subtitles';
import { mediaUrl, useMediaMustExist } from './media';
import { parseMotion, motionCss } from './motion.mjs';
import type { Motion } from './motion.mjs';
import { parseProps } from './schema';
import type { Segment, ShortProps } from './schema';

const AudioTrack: React.FC<{ props: ShortProps }> = ({ props }) => {
  const url = mediaUrl(props, props.audioSrc);
  useMediaMustExist(url);
  return <Audio src={url} />;
};

const MediaLayer: React.FC<{
  url: string;
  fit: 'cover' | 'contain';
  motion: Motion | null;
  progress: number;
  containerStyle?: React.CSSProperties;
}> = ({ url, fit, motion, progress, containerStyle }) => {
  useMediaMustExist(url);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', backgroundColor: '#000', ...containerStyle }}>
      <div
        style={{
          position: 'absolute',
          inset: 0,
          transform: motionCss(motion, progress),
          transformOrigin: 'center center',
        }}
      >
        <OffthreadVideo src={url} muted style={{ width: '100%', height: '100%', objectFit: fit }} />
      </div>
    </div>
  );
};

/** Normalised position inside the segment's NOMINAL duration (crossfade tails excluded). */
const useSegmentProgress = (durationInFrames: number): number => {
  const frame = useCurrentFrame();
  if (durationInFrames <= 1) return 0;
  return Math.min(1, Math.max(0, frame / (durationInFrames - 1)));
};

const SegmentVisual: React.FC<{ segment: Segment; props: ShortProps }> = ({ segment, props }) => {
  const progress = useSegmentProgress(segment.durationInFrames);
  // Throws on a motion string this renderer cannot execute — never a silent still frame.
  const motion = parseMotion(segment.motion);
  const url = (index: number): string => mediaUrl(props, segment.sources[index]);
  const shared = { motion, progress };

  if (segment.kind === 'broll') {
    return <MediaLayer url={url(0)} fit={segment.treatment === 'cover' ? 'cover' : 'contain'} {...shared} />;
  }

  if (segment.treatment === 'splitscreen') {
    if (segment.sources.length !== 2) {
      throw new Error(`segment ${segment.id}: splitscreen needs 2 sources, props.json has ${segment.sources.length}`);
    }
    return (
      <>
        <MediaLayer url={url(0)} fit="cover" {...shared} containerStyle={{ top: 0, height: '50%', bottom: 'auto' }} />
        <MediaLayer url={url(1)} fit="cover" {...shared} containerStyle={{ top: '50%', height: '50%', bottom: 'auto' }} />
      </>
    );
  }

  // `source-frame` keeps the original framing, letterboxed into the vertical frame.
  if (segment.treatment === 'source-frame') {
    return <MediaLayer url={url(0)} fit="contain" {...shared} />;
  }

  // `blur-fill-<speaker>` keeps the WHOLE source frame — nobody's head is ever cropped — and
  // fills the vertical dead space with a blown-up, blurred copy of that same frame instead of
  // black. It is the only treatment that gives head-complete framing from a 16:9 source, and
  // it avoids the ~2.7x upscale a full-height 9:16 crop of 1280x720 requires.
  //
  // Both layers read ONE asset (the same full-frame extract), so this costs no extra file.
  // The backdrop is deliberately dimmed as well as blurred: an undimmed blur competes with the
  // sharp foreground and reads as a smear rather than as background.
  if (segment.treatment.startsWith('blur-fill-')) {
    return (
      <>
        <MediaLayer
          url={url(0)}
          fit="cover"
          {...shared}
          containerStyle={{ filter: 'blur(48px) brightness(0.55)', transform: 'scale(1.15)' }}
        />
        <MediaLayer url={url(0)} fit="contain" {...shared} containerStyle={{ backgroundColor: 'transparent' }} />
      </>
    );
  }

  // Speaker crops are produced full-bleed upstream by scripts/extract_segments.py.
  if (segment.treatment.startsWith('closeup-') || segment.treatment.startsWith('reaction-')) {
    return <MediaLayer url={url(0)} fit="cover" {...shared} />;
  }

  throw new Error(
    `segment ${segment.id}: unsupported A-roll treatment "${segment.treatment}" — ` +
    'expected closeup-<speaker>, reaction-<speaker>, blur-fill-<speaker>, splitscreen or source-frame',
  );
};

/**
 * A crossfade-<N>f transition holds the outgoing segment for N extra frames and
 * ramps the incoming segment in on top of it. The audio cut point never moves.
 */
const SegmentLayer: React.FC<{ segment: Segment; props: ShortProps; fadeInFrames: number }> = ({
  segment,
  props,
  fadeInFrames,
}) => {
  const frame = useCurrentFrame();
  const opacity = fadeInFrames > 0
    ? interpolate(frame, [0, fadeInFrames], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' })
    : 1;

  return (
    <AbsoluteFill style={{ opacity }}>
      <SegmentVisual segment={segment} props={props} />
      {segment.credit === null ? null : <Credits text={segment.credit} props={props} />}
    </AbsoluteFill>
  );
};

export const Short: React.FC<Record<string, unknown>> = (raw) => {
  const props = parseProps(raw);

  return (
    <AbsoluteFill style={{ backgroundColor: '#000' }}>
      <AudioTrack props={props} />
      {props.segments.map((segment, i) => {
        const previous = props.segments[i - 1] as Segment | undefined;
        const fadeInFrames = previous?.transitionOut.kind === 'crossfade' ? previous.transitionOut.frames : 0;
        const tailFrames = segment.transitionOut.kind === 'crossfade' ? segment.transitionOut.frames : 0;
        return (
          <Sequence
            key={segment.id}
            name={`${segment.id} ${segment.treatment}`}
            from={segment.startFrame}
            durationInFrames={segment.durationInFrames + tailFrames}
          >
            <SegmentLayer segment={segment} props={props} fadeInFrames={fadeInFrames} />
          </Sequence>
        );
      })}
      <Subtitles props={props} />
    </AbsoluteFill>
  );
};
