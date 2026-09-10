import { Config } from '@remotion/cli/config';

Config.setEntryPoint('./src/index.ts');

// The platform profiles in config/defaults.yaml are all h264/mp4. Per-profile
// re-encodes and loudness normalisation happen after this step (render-qc.md
// stage 8 step 6); this render is the visual master.
Config.setCodec('h264');
Config.setVideoImageFormat('jpeg');
Config.setPixelFormat('yuv420p');

// Renders are versioned and never overwritten (render-qc.md stage 8 step 7).
Config.setOverwriteOutput(false);
