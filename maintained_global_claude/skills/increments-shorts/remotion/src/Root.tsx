// The composition's dimensions, fps and length are properties of the clip, not
// of this file — they come from props.json via calculateMetadata.

import React from 'react';
import { Composition } from 'remotion';
import { Card } from './Card';
import { parseCardProps } from './cardSchema';
import { Short } from './Short';
import { parseProps } from './schema';

export const RemotionRoot: React.FC = () => (
  <>
  <Composition
    id="Short"
    component={Short}
    // Placeholders. calculateMetadata replaces all four from props.json, and
    // refuses to produce metadata at all when props.json is missing or invalid.
    width={1080}
    height={1920}
    fps={30}
    durationInFrames={1}
    defaultProps={{}}
    calculateMetadata={({ props }) => {
      const parsed = parseProps(props);
      return {
        width: parsed.width,
        height: parsed.height,
        fps: parsed.fps,
        durationInFrames: parsed.durationInFrames,
      };
    }}
  />
  {/* Transparent text layer for horizontal-clip B-roll (lower-thirds, cards, labels).
      Rendered by render-cards.mjs with ProRes 4444 + alpha; props from scripts/overlay_text.py. */}
  <Composition
    id="Card"
    component={Card}
    width={1920}
    height={1080}
    fps={30}
    durationInFrames={1}
    defaultProps={{}}
    calculateMetadata={({ props }) => {
      const parsed = parseCardProps(props);
      return {
        width: parsed.width,
        height: parsed.height,
        fps: parsed.fps,
        durationInFrames: parsed.durationInFrames,
      };
    }}
  />
  </>
);
