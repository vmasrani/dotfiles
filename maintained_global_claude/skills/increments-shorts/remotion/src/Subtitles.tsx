// Subtitle events come from the aligned .ass (the timing truth), already
// converted to frames, styled spans, per-word timings (@remotion/captions
// `Caption`s) and safe-zone-checked positions by gen-props.mjs. This file only
// draws them. A card that spans a layout change (solo <-> split screen) carries
// one position per layout and switches on exactly the frame the layout does.
//
// Word-by-word ("karaoke") highlight: inside each validated card, the word whose
// spoken start has most recently passed is drawn in activeColor at
// activeFontWeight; every other word keeps its own colour and weight. The cards
// are NOT re-paged (createTikTokStyleCaptions pages by time window and would
// ignore the card limits that validate_subtitles.py enforced).
//
// No reflow: every word sits in a slot whose width is reserved by an invisible
// copy of the word at its heaviest weight, so the line breaks and word positions
// are fixed for the whole card no matter which word is highlighted.
// align_subtitles.py fits the font size at that same weight.

import React from 'react';
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from 'remotion';
import { FONT_FAMILY } from './fonts';
import type { ShortProps, SubtitleEvent } from './schema';

type Style = ShortProps['subtitleStyle'];
type Span = SubtitleEvent['styledSpans'][number];
type Piece = { kind: 'gap'; span: Span } | { kind: 'word'; word: number; spans: Span[] };

type Placement = SubtitleEvent['placements'][number];

const anchorTransform: Record<Placement['anchorY'], string> = {
  top: 'none',
  middle: 'translateY(-50%)',
  bottom: 'translateY(-100%)',
};

/** Consecutive spans of one word become one slot; whitespace stays between slots. */
const toPieces = (spans: Span[]): Piece[] =>
  spans.reduce<Piece[]>((pieces, span) => {
    const last = pieces[pieces.length - 1];
    if (span.word === null) return [...pieces, { kind: 'gap', span }];
    if (last?.kind === 'word' && last.word === span.word) {
      return [...pieces.slice(0, -1), { ...last, spans: [...last.spans, span] }];
    }
    return [...pieces, { kind: 'word', word: span.word, spans: [span] }];
  }, []);

/** The card's position for the screen layout on this frame (relative to the card's first frame). */
const placementAt = (placements: Placement[], frame: number): Placement =>
  placements.reduce((current, p) => (p.fromFrame <= frame ? p : current), placements[0]);

/** The word whose spoken start most recently passed; -1 before the card's first word. */
const activeWordAt = (words: SubtitleEvent['words'], nowMs: number): number =>
  words.reduce((active, w, i) => (w.startMs <= nowMs ? i : active), -1);

const WordSlot: React.FC<{ spans: Span[]; active: boolean; style: Style }> = ({ spans, active, style }) => {
  const restWeight = (span: Span) => (span.bold ? style.emphasisFontWeight : style.fontWeight);
  return (
    <span style={{ display: 'inline-grid' }}>
      {/* width reservation: the word at its heaviest weight, never painted */}
      <span aria-hidden style={{ gridArea: '1 / 1', visibility: 'hidden' }}>
        {spans.map((span, i) => (
          // eslint-disable-next-line react/no-array-index-key -- spans are positional, not identified
          <span key={i} style={{ fontWeight: Math.max(style.activeFontWeight, restWeight(span)), fontStyle: span.italic ? 'italic' : 'normal' }}>
            {span.text}
          </span>
        ))}
      </span>
      <span style={{ gridArea: '1 / 1', justifySelf: 'center' }}>
        {spans.map((span, i) => (
          // eslint-disable-next-line react/no-array-index-key -- spans are positional, not identified
          <span
            key={i}
            style={{
              color: active ? style.activeColor : span.color,
              fontWeight: active ? style.activeFontWeight : restWeight(span),
              fontStyle: span.italic ? 'italic' : 'normal',
            }}
          >
            {span.text}
          </span>
        ))}
      </span>
    </span>
  );
};

const SubtitleBlock: React.FC<{ event: SubtitleEvent; style: Style }> = ({ event, style }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const active = activeWordAt(event.words, ((event.startFrame + frame) / fps) * 1000);
  // Only the vertical anchor moves with the layout; width, wrap and every word slot stay the same, so nothing reflows.
  const placement = placementAt(event.placements, frame);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          top: placement.posY,
          left: style.leftPx,
          width: style.maxWidthPx,
          transform: anchorTransform[placement.anchorY],
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
        {toPieces(event.styledSpans).map((piece, i) =>
          piece.kind === 'gap' ? (
            // eslint-disable-next-line react/no-array-index-key -- pieces are positional, not identified
            <span key={i} style={{ color: piece.span.color }}>
              {piece.span.text}
            </span>
          ) : (
            // eslint-disable-next-line react/no-array-index-key -- pieces are positional, not identified
            <WordSlot key={i} spans={piece.spans} active={piece.word === active} style={style} />
          ),
        )}
      </div>
    </AbsoluteFill>
  );
};

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
