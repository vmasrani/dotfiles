export type Rect = { x: number; y: number; w: number; h: number };
export type CropKey = { frame: number; x: number; y: number };
export type PanelShot = {
  fromFrame: number;
  toFrame: number;
  cropW: number;
  cropH: number;
  keys: CropKey[];
  dst: Rect;
  backdrop: { blurPx: number; brightness: number } | null;
  tile: Rect | null;
};
export type PanelGeometry = {
  rect: Rect;
  sourceDims: { w: number; h: number };
  shots: PanelShot[];
};

/** Every problem with a panel's geometry, as readable strings (empty = valid). */
export declare function panelProblems(panel: PanelGeometry, durationInFrames: number): string[];

/** The shot on a segment-relative frame; frames past the last shot stay on the last one. */
export declare function shotAt<P extends PanelGeometry>(panel: P, frame: number): P['shots'][number];

/** Top-left of the crop window (source px) on a segment-relative frame. */
export declare function cropAt(shot: PanelShot, frame: number): { x: number; y: number };

export type QuoteShot = {
  fromFrame: number;
  toFrame: number;
  src: string;
  srcW: number;
  srcH: number;
  dst: Rect;
  zoom: [number, number];
  dissolveFrames: number;
};
export type QuoteGeometry = {
  startFrame: number;
  endFrame: number;
  fadeInFrames: number;
  fadeOutFrames: number;
  rect: Rect;
  shots: QuoteShot[];
};

/** Every problem with a quote overlay's geometry, as readable strings (empty = valid). */
export declare function quoteProblems(quote: QuoteGeometry): string[];

/** Opacity of the whole quote layout on a composition frame (0 outside its window). */
export declare function quoteOpacity(quote: QuoteGeometry, frame: number): number;

/** The screenshots drawn on a composition frame, bottom to top. */
export declare function quoteLayers<Q extends QuoteGeometry>(
  quote: Q,
  frame: number,
): { index: number; shot: Q['shots'][number]; opacity: number; scale: number }[];
