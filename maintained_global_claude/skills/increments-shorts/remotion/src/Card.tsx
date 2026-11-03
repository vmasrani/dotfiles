// Transparent text layer for horizontal-clip B-roll: lower-thirds, kinetic-type cards and
// picture labels. Every animation is a pure function of the frame. The style comes from props
// (config/defaults.yaml `broll.text` via scripts/overlay_text.py) — nothing is styled here by default.

import React from 'react';
import { AbsoluteFill, interpolate, useCurrentFrame } from 'remotion';
import { parseCardProps, type CardElement, type CardRun, type CardStyle } from './cardSchema';
import { FONT_FAMILY } from './fonts';

const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

const hexToRgba = (hex: string, alpha: number): string => {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
};

const ANCHOR: Record<CardElement['anchor'], [number, number]> = {
  'top-left': [0, 0], 'top-center': [-50, 0], 'top-right': [-100, 0],
  'center-left': [0, -50], center: [-50, -50], 'center-right': [-100, -50],
  'bottom-left': [0, -100], 'bottom-center': [-50, -100], 'bottom-right': [-100, -100],
};

const Rule: React.FC<{ start: number; frame: number; style: CardStyle; kind: 'underline' | 'strike' }> = ({
  start, frame, style, kind,
}) => {
  const p = interpolate(frame, [start, start + style.ruleFrames], [0, 1], clamp);
  if (p <= 0) return null;
  return (
    <span
      style={{
        position: 'absolute',
        left: 0,
        width: `${p * 100}%`,
        height: '0.09em',
        top: kind === 'strike' ? '0.56em' : '1.12em',
        background: kind === 'strike' ? style.ruleColor : style.accentColor,
        borderRadius: '0.05em',
      }}
    />
  );
};

const Run: React.FC<{ run: CardRun; frame: number; style: CardStyle }> = ({ run, frame, style }) => {
  const appear = run.appear ?? 0;
  const p = interpolate(frame, [appear, appear + style.popFrames], [0, 1], clamp);
  return (
    <span
      style={{
        position: 'relative',
        display: 'inline-block',
        whiteSpace: 'pre',
        color: run.color,
        fontWeight: run.weight,
        opacity: p,
        transform: `translateY(${(1 - p) * 0.25}em) scale(${0.92 + 0.08 * p})`,
        transformOrigin: 'left bottom',
      }}
    >
      {run.text}
      {run.underline !== null ? <Rule start={run.underline} frame={frame} style={style} kind="underline" /> : null}
      {run.strike !== null ? <Rule start={run.strike} frame={frame} style={style} kind="strike" /> : null}
    </span>
  );
};

const Element: React.FC<{ el: CardElement; frame: number; style: CardStyle }> = ({ el, frame, style }) => {
  if (frame < el.from || frame >= el.to) return null;
  const fadeIn = el.fadeIn > 0 ? interpolate(frame, [el.from, el.from + el.fadeIn], [0, 1], clamp) : 1;
  const fadeOut = el.fadeOut > 0 ? interpolate(frame, [el.to - el.fadeOut, el.to], [1, 0], clamp) : 1;
  const [ax, ay] = ANCHOR[el.anchor];
  return (
    <div
      style={{
        position: 'absolute',
        left: el.x,
        top: el.y,
        transform: `translate(${ax}%, ${ay}%)`,
        maxWidth: el.maxWidth,
        opacity: Math.min(fadeIn, fadeOut),
        textAlign: el.align,
        fontFamily: FONT_FAMILY,
        textShadow: el.plate ? 'none' : style.textShadow,
        background: el.plate ? hexToRgba(style.plateColor, style.plateOpacity) : 'transparent',
        borderRadius: el.plate ? style.plateRadius : 0,
        padding: el.plate ? `${style.platePadV}px ${style.platePadH}px` : 0,
        borderLeft: el.accentBar ? `${style.accentBarPx}px solid ${style.accentColor}` : 'none',
      }}
    >
      {el.lines.map((line, i) => (
        <div key={i} style={{ fontSize: line.size, lineHeight: style.lineGap }}>
          {line.runs.map((run, j) => (
            <Run key={j} run={run} frame={frame} style={style} />
          ))}
        </div>
      ))}
    </div>
  );
};

export const Card: React.FC<Record<string, unknown>> = (raw) => {
  const props = parseCardProps(raw);
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: 'transparent' }}>
      {props.elements.map((el, i) => (
        <Element key={i} el={el} frame={frame} style={props.style} />
      ))}
    </AbsoluteFill>
  );
};
