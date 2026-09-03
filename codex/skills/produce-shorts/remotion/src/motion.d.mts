export type Motion =
  | { kind: 'zoom'; fromScale: number; toScale: number }
  | { kind: 'pan'; axis: 'x' | 'y'; sign: 1 | -1; fromOffset: number; toOffset: number };

export declare const MOTION_GRAMMAR: string;

/** Throws on any string outside MOTION_GRAMMAR. `null`/"none" mean a locked frame. */
export declare function parseMotion(raw: string | null | undefined): Motion | null;

export declare function motionTransform(
  motion: Motion | null,
  progress: number,
): { scale: number; translateXPercent: number; translateYPercent: number };

/** CSS `transform` value for a motion at normalised progress in [0, 1]. */
export declare function motionCss(motion: Motion | null, progress: number): string;
