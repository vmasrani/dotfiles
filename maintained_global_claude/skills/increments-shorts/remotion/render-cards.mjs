#!/usr/bin/env node
// Render every transparent text layer (the `Card` composition) for one horizontal clip.
//
//   node render-cards.mjs <jobs.json>
//
// jobs.json = {"concurrency": 3, "jobs": [{"out": "/abs/B1.mov", "props": {...card props...}}]}
// written by scripts/overlay_text.py. Bundles ONCE, then renders each job as ProRes 4444 with an
// alpha channel (png frames, yuva444p10le) so ffmpeg can overlay it. Refuses to overwrite an
// existing output, and exits nonzero naming the job on the first failure.

import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { bundle } from '@remotion/bundler';
import { renderMedia, selectComposition } from '@remotion/renderer';

const here = path.dirname(fileURLToPath(import.meta.url));
const jobsPath = process.argv[2];
if (!jobsPath) {
  console.error('usage: node render-cards.mjs <jobs.json>');
  process.exit(2);
}
const { jobs, concurrency } = JSON.parse(readFileSync(jobsPath, 'utf8'));
if (!Array.isArray(jobs) || jobs.length === 0) {
  console.error(`${jobsPath}: no jobs`);
  process.exit(2);
}
const taken = jobs.filter((j) => existsSync(j.out)).map((j) => j.out);
if (taken.length) {
  console.error(`refusing to overwrite existing card layers: ${taken.join(', ')}`);
  process.exit(1);
}

const serveUrl = await bundle({ entryPoint: path.join(here, 'src/index.ts'), publicDir: path.join(here, 'public') });
for (const [i, job] of jobs.entries()) {
  const t0 = Date.now();
  try {
    const composition = await selectComposition({ serveUrl, id: 'Card', inputProps: job.props });
    await renderMedia({
      composition,
      serveUrl,
      inputProps: job.props,
      codec: 'prores',
      proResProfile: '4444',
      imageFormat: 'png',
      pixelFormat: 'yuva444p10le',
      outputLocation: job.out,
      concurrency: concurrency ?? 3,
      overwrite: false,
    });
  } catch (err) {
    console.error(`card ${i + 1}/${jobs.length} (${job.out}) failed: ${err instanceof Error ? err.stack : err}`);
    process.exit(1);
  }
  console.log(`card ${i + 1}/${jobs.length} ${path.basename(job.out)} ${((Date.now() - t0) / 1000).toFixed(1)}s`);
}
