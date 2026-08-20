// Inter is loaded from woff2 files bundled in public/fonts/ — never from a CDN.
// A render must not depend on the network or on what happens to be installed on
// the rendering machine.
//
// public/fonts/Inter-*.woff2 are the Google Fonts "latin" and "latin-ext"
// subsets of the Inter variable font (SIL Open Font License 1.1); one file
// serves both weights via its wght axis.

import { loadFont } from '@remotion/fonts';
import { cancelRender, continueRender, delayRender, staticFile } from 'remotion';

export const FONT_FAMILY = 'Inter';

const SUBSETS = [
  {
    file: 'fonts/Inter-latin.woff2',
    unicodeRange:
      'U+0000-00FF, U+0131, U+0152-0153, U+02BB-02BC, U+02C6, U+02DA, U+02DC, U+0304, U+0308, ' +
      'U+0329, U+2000-206F, U+20AC, U+2122, U+2191, U+2193, U+2212, U+2215, U+FEFF, U+FFFD',
  },
  {
    file: 'fonts/Inter-latin-ext.woff2',
    unicodeRange:
      'U+0100-02BA, U+02BD-02C5, U+02C7-02CC, U+02CE-02D7, U+02DD-02FF, U+0304, U+0308, U+0329, ' +
      'U+1D00-1DBF, U+1E00-1E9F, U+1EF2-1EFF, U+2020, U+20A0-20AB, U+20AD-20C0, U+2113, ' +
      'U+2C60-2C7F, U+A720-A7FF',
  },
];

const WEIGHTS = ['600', '700'];

// Why this is not a plain `Promise.all(...).then(continueRender)`:
//
// Under memory pressure the compositor drops a request mid-render ("Could not extract frame
// from compositor: Request closed"). Remotion recycles the page, this module re-runs, and the
// fetch for a woff2 can then hang forever against the recycled static server — settling
// NEITHER `.then` NOR `.catch`. The delayRender handle is stranded, and ~178s later the render
// dies blaming the font. That misnames the failure: the browser crashed, the font is fine.
//
// Measured on a real episode: nine long renders died this way at frames 244, 244, 268, 505,
// 570, 847, 883, 1369 and 1980 — at three-way, two-way AND effectively exclusive machine use.
// Serializing renders lowers the RATE of compositor drops but does not remove them, so an
// exclusive box is not sufficient. Surviving a recycled page is what actually matters.
//
// So: bound every fetch in time, retry it, and let Remotion retry the frame if even that
// fails. A hang becomes a retry instead of a dead render.
const FONT_FETCH_TIMEOUT_MS = 20_000;
const FONT_FETCH_ATTEMPTS = 4;

/** Reject if `promise` has not settled in `ms` — a hung fetch must fail, not wait forever. */
const withTimeout = <T>(promise: Promise<T>, ms: number, what: string): Promise<T> =>
  new Promise<T>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error(`${what} did not settle within ${ms}ms (likely a recycled page)`)),
      ms,
    );
    promise.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      (err: unknown) => {
        clearTimeout(timer);
        reject(err instanceof Error ? err : new Error(String(err)));
      },
    );
  });

const loadSubsetWeight = async (file: string, unicodeRange: string, weight: string) => {
  let last: unknown;
  for (let attempt = 1; attempt <= FONT_FETCH_ATTEMPTS; attempt += 1) {
    try {
      return await withTimeout(
        loadFont({
          family: FONT_FAMILY,
          url: staticFile(file),
          format: 'woff2',
          weight,
          unicodeRange,
          display: 'block',
        }),
        FONT_FETCH_TIMEOUT_MS,
        `${file} @${weight} (attempt ${attempt}/${FONT_FETCH_ATTEMPTS})`,
      );
    } catch (err: unknown) {
      last = err;
    }
  }
  throw last instanceof Error ? last : new Error(String(last));
};

// `retries` lets Remotion re-render the frame if the handle still times out, rather than
// failing the whole render. The timeout is per attempt and deliberately far below the 178s
// default, so a stranded page is detected in seconds instead of minutes.
const handle = delayRender('loading the bundled Inter font', {
  timeoutInMilliseconds: 90_000,
  retries: 3,
});

Promise.all(
  SUBSETS.flatMap((subset) =>
    WEIGHTS.map((weight) => loadSubsetWeight(subset.file, subset.unicodeRange, weight)),
  ),
)
  .then(() => continueRender(handle))
  .catch((err: unknown) =>
    cancelRender(
      new Error(
        `could not load the bundled Inter font from public/fonts/ after ${FONT_FETCH_ATTEMPTS} ` +
          `attempts per subset — either the template copy is incomplete or the page is not ` +
          `serving staticFile(): ${String(err)}`,
      ),
    ),
  );
