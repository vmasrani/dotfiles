// Attribution line for licensed assets whose provider requires credit
// (clip.yaml assets[].credit_required). It renders only while the segment that
// uses the asset is on screen, in the lower-left of the safe area — the lower
// right belongs to the platform's engagement rail.

import React from 'react';
import { AbsoluteFill } from 'remotion';
import { FONT_FAMILY } from './fonts';
import type { ShortProps } from './schema';

export const Credits: React.FC<{ text: string; props: ShortProps }> = ({ text, props }) => {
  const fontSize = Math.round(props.height * 0.0125);
  return (
    <AbsoluteFill>
      <div
        style={{
          position: 'absolute',
          left: props.safeZone.left,
          bottom: props.safeZone.bottom,
          maxWidth: props.width - props.safeZone.left - props.safeZone.right,
          fontFamily: `${FONT_FAMILY}, sans-serif`,
          fontWeight: 600,
          fontSize,
          lineHeight: 1.3,
          color: 'rgba(255, 255, 255, 0.88)',
          letterSpacing: 0.2,
          textShadow: '0 2px 6px rgba(0, 0, 0, 0.85)',
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
