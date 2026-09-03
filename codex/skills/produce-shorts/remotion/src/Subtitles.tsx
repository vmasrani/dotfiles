// Subtitle events come from the aligned .ass (the timing truth), already
// converted to frames, styled spans and safe-zone-checked positions by
// gen-props.mjs. This file only draws them.

import React from 'react';
import { AbsoluteFill, Sequence } from 'remotion';
import { FONT_FAMILY } from './fonts';
import type { ShortProps, SubtitleEvent } from './schema';

const anchorTransform: Record<SubtitleEvent['anchorY'], string> = {
  top: 'none',
  middle: 'translateY(-50%)',
  bottom: 'translateY(-100%)',
};

const SubtitleBlock: React.FC<{ event: SubtitleEvent; style: ShortProps['subtitleStyle'] }> = ({ event, style }) => (
  <AbsoluteFill>
    <div
      style={{
        position: 'absolute',
        top: event.posY,
        left: style.leftPx,
        width: style.maxWidthPx,
        transform: anchorTransform[event.anchorY],
        textAlign: event.alignX,
        fontFamily: `${FONT_FAMILY}, sans-serif`,
        fontWeight: style.fontWeight,
        fontSize: style.fontSizePx,
        lineHeight: style.lineHeightEm,
        whiteSpace: 'pre-wrap',
        WebkitTextStroke: style.outlineWidthPx > 0 ? `${style.outlineWidthPx}px ${style.outlineColor}` : undefined,
        paintOrder: 'stroke fill',
        textShadow: style.shadowPx > 0 ? `0 ${style.shadowPx}px ${style.shadowPx * 1.5}px rgba(0, 0, 0, 0.75)` : undefined,
      }}
    >
      {event.styledSpans.map((span, i) => (
        <span
          // eslint-disable-next-line react/no-array-index-key -- spans are positional, not identified
          key={i}
          style={{
            color: span.color,
            fontWeight: span.bold ? style.emphasisFontWeight : style.fontWeight,
            fontStyle: span.italic ? 'italic' : 'normal',
          }}
        >
          {span.text}
        </span>
      ))}
    </div>
  </AbsoluteFill>
);

export const Subtitles: React.FC<{ props: ShortProps }> = ({ props }) => (
  <>
    {props.subtitles.map((event) => (
      <Sequence
        key={`${event.startFrame}-${event.endFrame}`}
        name={`sub ${event.startFrame}f "${event.text.split('\n')[0].slice(0, 24)}"`}
        from={event.startFrame}
        durationInFrames={event.endFrame - event.startFrame}
      >
        <SubtitleBlock event={event} style={props.subtitleStyle} />
      </Sequence>
    ))}
  </>
);
