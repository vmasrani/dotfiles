// One <Sequence> per timeline segment, in manifest order. Nothing here decides
// anything: every frame, position, file and transition comes from props.json,
// which came from clip.yaml.

import React from 'react';
import { AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, useCurrentFrame } from 'remotion';
import { Credits } from './Credits';
import { Subtitles } from './Subtitles';
import { cropAt, quoteLayers, quoteOpacity, shotAt } from './geometry.mjs';
import { mediaUrl, sourceUrl, useMediaMustExist } from './media';
import { parseMotion, motionCss } from './motion.mjs';
import type { Motion } from './motion.mjs';
import { parseProps } from './schema';
import type { Panel, Quote, Segment, ShortProps } from './schema';

/** A blur-fill backdrop is enlarged this much so the blur's faded edge falls outside the panel. */
const BACKDROP_ENLARGE = 1.25;

const AudioTrack: React.FC<{ props: ShortProps }> = ({ props }) => {
  const url = mediaUrl(props, props.audioSrc);
  useMediaMustExist(url);
  return <Audio src={url} />;
};

/** A b-roll file, drawn whole (cover or contain) with the segment's motion. */
const MediaLayer: React.FC<{
  url: string;
  fit: 'cover' | 'contain';
  motion: Motion | null;
  progress: number;
}> = ({ url, fit, motion, progress }) => {
  useMediaMustExist(url);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', backgroundColor: '#000' }}>
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

/**
 * One A-roll video rectangle. Every panel draws the SAME full-frame source video through a crop: the video element is
 * laid out at source size and moved/scaled by a CSS transform so the crop window fills `dst`, inside an
 * overflow:hidden container. A blur-fill shot adds a backdrop: the same crop, scaled to cover the panel, blurred and
 * darkened. The crop windows come from scripts/frame_segments.py and never leave the speaker's tile (geometry.mjs).
 */
const PanelView: React.FC<{ panel: Panel; props: ShortProps; motion: Motion | null; progress: number }> = ({
  panel,
  props,
  motion,
  progress,
}) => {
  const frame = useCurrentFrame();
  const url = sourceUrl(props, panel.source);
  useMediaMustExist(url);
  const shot = shotAt(panel, frame);
  const { x, y } = cropAt(shot, frame);
  const { w: sourceW, h: sourceH } = panel.sourceDims;

  const video = (scale: number, tx: number, ty: number): React.ReactElement => (
    <OffthreadVideo
      src={url}
      muted
      trimBefore={panel.trimBeforeFrame}
      style={{
        position: 'absolute',
        left: 0,
        top: 0,
        width: sourceW,
        height: sourceH,
        maxWidth: 'none',
        transformOrigin: '0 0',
        transform: `translate(${tx}px, ${ty}px) scale(${scale})`,
      }}
    />
  );

  const fgScale = shot.dst.w / shot.cropW;
  // cover: the crop fills the whole panel (its centre part); the blur then fades the panel edges, so the layer is
  // enlarged until those edges fall outside the panel
  const bgScale = Math.max(panel.rect.w / shot.cropW, panel.rect.h / shot.cropH);

  return (
    <div
      style={{
        position: 'absolute',
        left: panel.rect.x,
        top: panel.rect.y,
        width: panel.rect.w,
        height: panel.rect.h,
        overflow: 'hidden',
        backgroundColor: '#000',
      }}
    >
      <div style={{ position: 'absolute', inset: 0, transform: motionCss(motion, progress), transformOrigin: 'center center' }}>
        {shot.backdrop === null ? null : (
          <div
            style={{
              position: 'absolute',
              inset: 0,
              filter: `blur(${shot.backdrop.blurPx}px) brightness(${shot.backdrop.brightness})`,
              transform: `scale(${BACKDROP_ENLARGE})`,
            }}
          >
            <div style={{ position: 'absolute', inset: 0, overflow: 'hidden' }}>
              {video(
                bgScale,
                (panel.rect.w - shot.cropW * bgScale) / 2 - x * bgScale,
                (panel.rect.h - shot.cropH * bgScale) / 2 - y * bgScale,
              )}
            </div>
          </div>
        )}
        <div
          style={{
            position: 'absolute',
            left: shot.dst.x,
            top: shot.dst.y,
            width: shot.dst.w,
            height: shot.dst.h,
            overflow: 'hidden',
          }}
        >
          {video(fgScale, -x * fgScale, -y * fgScale)}
        </div>
      </div>
    </div>
  );
};

const SegmentVisual: React.FC<{ segment: Segment; props: ShortProps }> = ({ segment, props }) => {
  const progress = useSegmentProgress(segment.durationInFrames);
  // Throws on a motion string this renderer cannot execute — never a silent still frame.
  const motion = parseMotion(segment.motion);

  if (segment.kind === 'broll') {
    return (
      <MediaLayer
        url={mediaUrl(props, segment.sources[0])}
        fit={segment.treatment === 'cover' ? 'cover' : 'contain'}
        motion={motion}
        progress={progress}
      />
    );
  }

  // closeup-<speaker> is one `full` panel, splitscreen is `top` + `bottom` (the schema checked the slots).
  if (segment.treatment.startsWith('closeup-') || segment.treatment === 'splitscreen') {
    return (
      <>
        {segment.panels?.map((panel) => (
          <PanelView key={panel.slot} panel={panel} props={props} motion={motion} progress={progress} />
        ))}
      </>
    );
  }

  throw new Error(
    `segment ${segment.id}: unsupported A-roll treatment "${segment.treatment}" — expected closeup-<speaker> or splitscreen`,
  );
};

/**
 * The top half of a quote layout: the overlay's screenshots on a blurred, darkened copy of themselves, with a slow push-in
 * per shot and a dissolve between shots. Fit rectangles, zoom and timing come from props.json (scripts/quotelayout.py).
 * Drawn inside a <Sequence> that opens on the overlay's first frame.
 */
const QuoteShotView: React.FC<{ quote: Quote; url: string; shot: Quote['shots'][number]; opacity: number; scale: number }> = ({
  quote,
  url,
  shot,
  opacity,
  scale,
}) => {
  useMediaMustExist(url);
  return (
    <div style={{ position: 'absolute', inset: 0, opacity }}>
      <Img
        src={url}
        style={{
          position: 'absolute',
          inset: 0,
          width: quote.rect.w,
          height: quote.rect.h,
          objectFit: 'cover',
          filter: `blur(${quote.backdrop.blurPx}px) brightness(${quote.backdrop.brightness})`,
          transform: `scale(${BACKDROP_ENLARGE})`,
        }}
      />
      <div
        style={{
          position: 'absolute',
          left: shot.dst.x,
          top: shot.dst.y,
          width: shot.dst.w,
          height: shot.dst.h,
          transform: `scale(${scale})`,
          transformOrigin: 'center center',
          boxShadow: '0 14px 44px rgba(0, 0, 0, 0.6)',
        }}
      >
        <Img src={url} style={{ width: '100%', height: '100%', display: 'block' }} />
      </div>
    </div>
  );
};

const QuoteTop: React.FC<{ quote: Quote; props: ShortProps }> = ({ quote, props }) => {
  const frame = quote.startFrame + useCurrentFrame();
  return (
    <div
      style={{
        position: 'absolute',
        left: quote.rect.x,
        top: quote.rect.y,
        width: quote.rect.w,
        height: quote.rect.h,
        overflow: 'hidden',
        backgroundColor: '#000',
        opacity: quoteOpacity(quote, frame),
      }}
    >
      {quoteLayers(quote, frame).map(({ index, shot, opacity, scale }) => (
        <QuoteShotView key={index} quote={quote} url={mediaUrl(props, shot.src)} shot={shot} opacity={opacity} scale={scale} />
      ))}
    </div>
  );
};

/** The bottom half of a quote layout while `segment` is on: its speaker, framed like a split-screen panel. */
const QuoteSpeaker: React.FC<{ quote: Quote; segment: Segment; props: ShortProps }> = ({ quote, segment, props }) => {
  const absolute = segment.startFrame + useCurrentFrame();
  if (segment.quotePanel === null || absolute < quote.startFrame || absolute >= quote.endFrame) return null;
  return (
    <AbsoluteFill style={{ opacity: quoteOpacity(quote, absolute) }}>
      <PanelView panel={segment.quotePanel} props={props} motion={null} progress={0} />
    </AbsoluteFill>
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
      {props.quotes.map((quote) => (
        <React.Fragment key={quote.id}>
          <Sequence name={`${quote.id} quote`} from={quote.startFrame} durationInFrames={quote.endFrame - quote.startFrame}>
            <QuoteTop quote={quote} props={props} />
          </Sequence>
          {props.segments
            .filter((s) => s.quotePanel !== null && s.startFrame < quote.endFrame && s.startFrame + s.durationInFrames > quote.startFrame)
            .map((segment) => (
              <Sequence key={segment.id} name={`${quote.id} ${segment.id} speaker`} from={segment.startFrame} durationInFrames={segment.durationInFrames}>
                <QuoteSpeaker quote={quote} segment={segment} props={props} />
              </Sequence>
            ))}
        </React.Fragment>
      ))}
      <Subtitles props={props} />
    </AbsoluteFill>
  );
};
