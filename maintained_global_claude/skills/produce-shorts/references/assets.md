# Stage 5 — B-roll research and acquisition

One **asset researcher** subagent per clip (or one for a small batch), model = `roles.research`. Runs concurrently with the visual director's first pass (see `references/storyboard.md`, synthesis section).

## The cardinal rule

The researcher reports **only assets that are actually available through a configured provider account or API** — verified by a real API response from `scripts/stock_search.py`, never from memory or a plausible-sounding URL. Search suggestions, thumbnails seen in a web page, and "this provider probably has X" are not assets. Inventing an asset here produces a render that silently uses nothing — the whole pipeline downstream trusts this manifest.

If an exact visual is unavailable or can't be licensed, the researcher returns **alternatives with trade-offs described** to the synthesis pass — it never silently substitutes something different from the director's intent.

## Providers

Configured in `config/defaults.yaml → providers`. Shipped defaults:

| Provider | Auth | License notes |
|---|---|---|
| Pexels | `PEXELS_API_KEY` | Pexels License — free, no credit required, no resale-as-is |
| Pixabay | `PIXABAY_API_KEY` | Content License — free, no credit required |

Paid providers (Storyblocks, Artgrid, Getty) can be added in config with their API details; the researcher must never scrape a provider that isn't configured. A missing API key is a loud stop for that provider, not a reason to guess.

**User-supplied footage** counts as a provider (`provider: user-library`): file path, user attestation of rights in `license`, no download step.

## Workflow per B-roll intent

1. `scripts/stock_search.py PROVIDER "query" --min-width 1920 --min-duration 4` → real results (provider ID, dimensions, fps, duration, URL, license).
2. Researcher reviews results against the director's intent (subject, motion, tone, lighting) and shortlists 1–3 per intent, or reports "nothing suitable" with the queries tried.
3. After synthesis selects an asset: `scripts/stock_download.py PROVIDER PROVIDER_ID --clip-dir clips/<slug> --asset-id A03` downloads the file, computes sha256, probes it, and appends the full manifest entry to `clip.yaml assets[]` (every field in the schema: license, entitlement, download date, creator, credit requirements, resolution/fps/duration, filename, checksum). Downloads happen ONLY for synthesis-selected assets — shortlists are metadata-only.

## Licensing discipline

- Record `credit_required` and exact `credit_text` when the license demands attribution; the renderer places credits from these fields.
- `entitlement` records how we have the right: `free` | `subscription` | `purchased`. For paid providers, the researcher confirms the entitlement is active on the configured account before reporting the asset as available.
- Quality bar: prefer assets whose native resolution ≥ target output on the cropped axis; note in the shortlist when an asset would need upscaling.
- Everything lands in `provenance.json` at packaging time; an asset in the render that isn't in the manifest is a QC failure (stage 9), so there is no path for untracked footage.
