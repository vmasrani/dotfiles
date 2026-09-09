// Media paths in props.json are relative to the clip dir. gen-props.mjs links
// the clip dir into public/<assetRoot>, so every path resolves through
// staticFile() and nothing is ever fetched over the network at render time.

import { useEffect, useState } from 'react';
import { cancelRender, delayRender, continueRender, staticFile } from 'remotion';
import type { ShortProps } from './schema';

export const mediaUrl = (props: ShortProps, path: string): string =>
  staticFile(`${props.assetRoot}/${path}`);

/**
 * Fail the render — loudly, naming the path — when a file the manifest promised
 * is not there. Without this a missing asset renders as a silent black hole.
 */
export const useMediaMustExist = (url: string): void => {
  const [handle] = useState(() => delayRender(`checking media ${url}`));

  useEffect(() => {
    let cancelled = false;

    const check = async (): Promise<void> => {
      const response = await fetch(url, { headers: { Range: 'bytes=0-0' } });
      if (response.status >= 400) {
        throw new Error(`missing media at render time: ${url} (HTTP ${response.status})`);
      }
      void response.body?.cancel();
    };

    // Two-argument then(): a failure in the success handler must not be
    // reported as a missing file.
    void check().then(
      () => {
        if (!cancelled) continueRender(handle);
      },
      (err: unknown) => {
        if (cancelled) return;
        cancelRender(
          err instanceof Error ? err : new Error(`could not read media at render time: ${url} — ${String(err)}`),
        );
      },
    );

    return () => {
      cancelled = true;
    };
  }, [url, handle]);
};
