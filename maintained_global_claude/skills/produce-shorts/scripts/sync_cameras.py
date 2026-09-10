#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "numpy>=1.26",
#   "scipy>=1.11",
# ]
# ///
"""Stage 1 sync — align isolated camera files to the episode by audio cross-correlation.

Method: both files are decoded to mono 16 kHz and reduced to a 5 ms log-RMS energy
envelope, whose positive first difference (an onset function) is the correlation feature.
Lags are scored with a *normalised* correlation — Pearson r computed per lag over the
actual overlapping region — so no lag is rewarded merely for overlapping more frames.
The peak lag is the offset; confidence multiplies how far the peak stands above the whole
curve (peak-to-sidelobe ratio) by how far it stands above its best competitor outside a
0.5 s guard band, so both "all noise" and "genuinely ambiguous, the audio repeats" score
near zero.

(A dedicated library was considered — `audio-offset-finder` — but it pulls librosa for a
single correlation and offers neither the per-lag normalisation nor the sliding-window gap
detection this stage needs, so scipy's FFT correlation is used directly.)

Subcommands: `compute` (measure + write the sync block), `verify` (render a 5 s
side-by-side for human eyeballing), `mark-verified` (record the human's pass).
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import typer
import yaml
from loguru import logger
from rich.console import Console
from rich.table import Table as RichTable
from scipy.signal import correlate

from pslib import (
    Episode,
    SyncEntry,
    SyncGap,
    ffprobe_media,
    fmt_mmss,
    load_episode,
    save_episode,
)

console = Console()
app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config" / "defaults.yaml"

SAMPLE_RATE = 16_000
HOP_S = 0.005                    # envelope resolution — 5 ms, far finer than the 0.05 s tolerance
HOP = int(SAMPLE_RATE * HOP_S)
GUARD_S = 0.5                    # side-lobe guard band when measuring peak sharpness
SHARPNESS_REFERENCE = 0.50       # side lobes below half the peak incur no confidence penalty
PSR_SCALE = 8.0                  # peak-to-sidelobe ratio that counts as a solid lock
MIN_OVERLAP_S = 30.0             # a lag correlating over less than this is not evidence
METHOD = "audio-cross-correlation"

GAP_WINDOW_S = 20.0              # sliding window for discontinuity detection
GAP_SEARCH_S = 2.0               # local lag search around the global offset
GAP_R_THRESHOLD = 0.50           # window correlation below this is a discontinuity
GAP_DRIFT_S = 0.20               # local lag this far from the global offset is a discontinuity
GAP_SILENCE_FRACTION = 0.15      # windows quieter than this fraction of median energy are skipped


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def min_confidence(config: Path) -> float:
    if not config.is_file():
        raise typer.BadParameter(
            f"config file not found: {config} — pass --config pointing at config/defaults.yaml"
        )
    data = yaml.safe_load(config.read_text()) or {}
    value = (data.get("sync") or {}).get("min_confidence")
    if value is None:
        raise typer.BadParameter(f"{config} has no `sync.min_confidence` — this gate cannot be skipped")
    return float(value)


# ---------------------------------------------------------------------------
# Audio
# ---------------------------------------------------------------------------


def decode_mono(path: Path) -> np.ndarray:
    """Decode any media file to mono 16 kHz float32 in [-1, 1] via ffmpeg."""
    cmd = [
        "ffmpeg", "-v", "error", "-nostdin", "-i", str(path),
        "-vn", "-ac", "1", "-ar", str(SAMPLE_RATE), "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed decoding audio from {path} (exit {proc.returncode}): "
            f"{proc.stderr.decode(errors='replace').strip()}"
        )
    samples = np.frombuffer(proc.stdout, dtype=np.int16)
    if samples.size == 0:
        raise RuntimeError(
            f"{path} yielded no audio samples — it has no audio stream, so it cannot be "
            "synchronised by audio cross-correlation"
        )
    return samples.astype(np.float32) / 32768.0


def energy_envelope(signal: np.ndarray) -> np.ndarray:
    """5 ms log-RMS energy envelope — used to pick loud moments and detect silence."""
    n = signal.size // HOP
    if n < 2:
        raise RuntimeError(f"audio is shorter than {2 * HOP_S}s — nothing to correlate")
    frames = signal[: n * HOP].reshape(n, HOP).astype(np.float64)
    rms = np.sqrt((frames * frames).mean(axis=1))
    return np.log1p(rms * 1000.0)


def onset_envelope(energy: np.ndarray) -> np.ndarray:
    """Positive first difference of the log-energy envelope — the correlation feature.

    Measured on synthetic fixtures (see the module docstring): correlating raw energy
    scores a correct *isolated* camera at r≈0.66-0.76, because the track is silent
    whenever its speaker is not talking and that silence drags the similarity down.
    Onsets are sparse and sharp, so the same alignments score r≈0.85-0.92 with side
    lobes at ≈0.10 — the peak stands out whether the camera is a room mix or a single
    isolated mic.
    """
    return np.clip(np.diff(energy, prepend=energy[0]), 0.0, None)


# ---------------------------------------------------------------------------
# Normalised cross-correlation
# ---------------------------------------------------------------------------


@dataclass
class Alignment:
    lag_frames: int
    offset_s: float
    r_peak: float
    r_side: float
    sharpness: float
    psr: float
    confidence: float


def ncc_curve(a: np.ndarray, b: np.ndarray, min_overlap: int) -> tuple[np.ndarray, np.ndarray]:
    """Pearson r of `a` against `b` for every lag k where a[i] pairs with b[i-k].

    Normalised per lag over the actual overlapping region (zero-padded correlations give
    the overlap sums for the `a` side, prefix sums for the `b` side), so a lag is never
    rewarded merely for overlapping more frames. Lags overlapping fewer than
    `min_overlap` frames are NaN — they are arithmetic, not evidence.
    """
    n, m = a.size, b.size
    lags = np.arange(-(m - 1), n)
    ones = np.ones(m, dtype=np.float64)

    sab = correlate(a, b, mode="full", method="fft")
    sa = correlate(a, ones, mode="full", method="fft")
    saa = correlate(a * a, ones, mode="full", method="fft")

    b_sum = np.concatenate(([0.0], np.cumsum(b)))
    b_sq = np.concatenate(([0.0], np.cumsum(b * b)))

    a_lo = np.clip(lags, 0, n)
    a_hi = np.clip(lags + m, 0, n)
    b_lo = np.clip(-lags, 0, m)
    b_hi = np.clip(n - lags, 0, m)
    length = (a_hi - a_lo).astype(np.float64)

    with np.errstate(invalid="ignore", divide="ignore"):
        sb = b_sum[b_hi] - b_sum[b_lo]
        sbb = b_sq[b_hi] - b_sq[b_lo]
        num = length * sab - sa * sb
        den = np.sqrt(
            np.clip(length * saa - sa * sa, 0.0, None) * np.clip(length * sbb - sb * sb, 0.0, None)
        )
        r = np.where(den > 0.0, num / den, np.nan)

    r[length < min_overlap] = np.nan
    return lags, r


def align(a: np.ndarray, b: np.ndarray, max_offset_s: float | None) -> Alignment:
    """Best lag plus a confidence that answers "is THIS lag the right one?".

    Two independent factors, both 0..1, multiplied:

    `lock`   how far the peak stands above the whole correlation curve, via the classic
             peak-to-sidelobe ratio (peak minus the off-peak mean, in off-peak standard
             deviations). Separates signal from a curve that is all noise.
    `unique` how far the peak stands above its best *competitor* outside the guard band.
             Collapses when the audio repeats (a rebroadcast bed, a looped intro), where
             a single offset is genuinely ambiguous no matter how sharp the peak is.

    Measured on synthetic fixtures: correct alignments 0.96-0.99, uncorrelated noise 0.19,
    a deliberately period-40s episode ≈0.
    """
    min_overlap = int(min(MIN_OVERLAP_S / HOP_S, 0.5 * min(a.size, b.size)))
    lags, r = ncc_curve(a, b, min_overlap)
    if max_offset_s is not None:
        limit = int(max_offset_s / HOP_S)
        r = np.where(np.abs(lags) <= limit, r, np.nan)
    if np.all(np.isnan(r)):
        raise RuntimeError(
            "no lag has enough overlap to correlate — the two files barely intersect in time "
            f"(need {MIN_OVERLAP_S}s of overlap; try widening --max-offset-s)"
        )
    peak = int(np.nanargmax(r))
    r_peak = float(r[peak])
    guard = int(GUARD_S / HOP_S)
    masked = r.copy()
    masked[max(0, peak - guard) : peak + guard + 1] = np.nan
    off_peak = masked[~np.isnan(masked)]
    if off_peak.size == 0:
        raise RuntimeError(
            "the correlation curve has no lags outside the peak's guard band — the files are "
            "too short to tell a real alignment from an accidental one"
        )
    r_side = float(np.max(off_peak))
    spread = float(np.std(off_peak))
    psr = 0.0 if spread <= 0.0 else (r_peak - float(np.mean(off_peak))) / spread
    sharpness = 0.0 if r_peak <= 0 else max(0.0, 1.0 - max(r_side, 0.0) / r_peak)
    lock = 1.0 - float(np.exp(-max(psr, 0.0) / PSR_SCALE))
    unique = float(np.clip(sharpness / SHARPNESS_REFERENCE, 0.0, 1.0))
    return Alignment(
        lag_frames=int(lags[peak]),
        offset_s=round(float(lags[peak]) * HOP_S, 3),
        r_peak=round(r_peak, 4),
        r_side=round(r_side, 4),
        sharpness=round(sharpness, 4),
        psr=round(psr, 2),
        confidence=round(lock * unique, 4),
    )


# ---------------------------------------------------------------------------
# Gap detection
# ---------------------------------------------------------------------------


def detect_gaps(
    ep_onset: np.ndarray, cam_onset: np.ndarray, cam_energy: np.ndarray, lag: int
) -> list[SyncGap]:
    """Windows of camera audio that do not line up at the global lag.

    Each `GAP_WINDOW_S` window of camera audio is re-correlated against the episode within
    ±GAP_SEARCH_S of the global lag. A window whose best local r is poor, or whose best
    local lag has drifted, is a discontinuity. Near-silent windows carry no alignment
    information and are skipped rather than reported as failures, as are windows recorded
    while the episode was not rolling.
    """
    win = int(GAP_WINDOW_S / HOP_S)
    search = int(GAP_SEARCH_S / HOP_S)
    if cam_onset.size < win:
        return []
    median_energy = float(np.median(cam_energy))
    flagged: list[int] = []
    for start in range(0, cam_onset.size - win + 1, win):
        if float(np.mean(cam_energy[start : start + win])) < GAP_SILENCE_FRACTION * median_energy:
            continue
        if start + lag < 0 or start + lag + win > ep_onset.size:
            continue  # camera rolled outside the episode here — absence of footage, not a gap
        chunk = cam_onset[start : start + win]
        lo = max(0, start + lag - search)
        hi = min(ep_onset.size, start + lag + win + search)
        if hi - lo < win:
            continue
        lags, r = ncc_curve(ep_onset[lo:hi], chunk, min_overlap=win)
        if np.all(np.isnan(r)):
            flagged.append(start)
            continue
        best = int(np.nanargmax(r))
        local_lag = lo + int(lags[best]) - start
        drifted = abs(local_lag - lag) * HOP_S > GAP_DRIFT_S
        if float(r[best]) < GAP_R_THRESHOLD or drifted:
            flagged.append(start)

    gaps: list[SyncGap] = []
    for start in flagged:
        if gaps and abs(gaps[-1].camera_s + gaps[-1].duration_s - start * HOP_S) < 1e-6:
            gaps[-1].duration_s = round(gaps[-1].duration_s + GAP_WINDOW_S, 3)
        else:
            gaps.append(SyncGap(camera_s=round(start * HOP_S, 3), duration_s=GAP_WINDOW_S))
    return gaps


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------


def episode_audio_path(root: Path, episode: Episode) -> Path:
    rel = episode.media.episode_audio or episode.media.episode_video
    path = root / rel
    if not path.is_file():
        raise typer.BadParameter(
            f"episode media not found: {path} (episode.yaml media points at {rel}) — "
            "run `ingest.py init` first"
        )
    return path


def camera_files(episode: Episode, only: list[str] | None) -> list[tuple[str, str]]:
    """[(speaker_id, relative camera path)] — the files this stage is responsible for."""
    pairs = [(s.id, s.camera_file) for s in episode.speakers if s.camera_file]
    if not pairs:
        raise typer.BadParameter(
            "no speaker in episode.yaml has a camera_file — register isolated footage with "
            "`ingest.py register-camera` before running sync, or skip this stage entirely"
        )
    if not only:
        return pairs
    selected = []
    for wanted in only:
        matches = [p for p in pairs if p[1] == wanted or Path(p[1]).name == Path(wanted).name]
        if not matches:
            raise typer.BadParameter(
                f"--file {wanted} is not a registered camera file; known: {[p[1] for p in pairs]}"
            )
        selected.extend(matches)
    return selected


def find_sync(episode: Episode, rel: str) -> SyncEntry | None:
    return next((e for e in episode.sync if e.file == rel), None)


def diagnose(a: Alignment) -> str:
    """Which of the two confidence factors failed, and what the operator should do."""
    if a.sharpness < SHARPNESS_REFERENCE and a.psr >= PSR_SCALE:
        return (
            f"several offsets fit this camera equally well (the best rival scores "
            f"{a.r_side:.3f} against the peak's {a.r_peak:.3f}), so no single offset can be "
            "trusted. This happens when the audio repeats — a looped music bed, a duplicated "
            "take, or the same segment recorded twice. Trim the camera file to a stretch that "
            "appears only once in the episode and re-run, or set the offset by hand after "
            "checking a side-by-side."
        )
    return (
        "no offset stands out from the noise: this file does not share recognisable audio "
        "with the episode. Check it is the right take, that its audio stream is not "
        "silent/music-only, and that the two actually overlap in time."
    )


def render_results(rows: list[tuple[str, Alignment, list[SyncGap]]], threshold: float) -> None:
    table = RichTable(title=f"Camera sync (min_confidence {threshold})", header_style="bold cyan")
    table.add_column("camera file", overflow="fold")
    for col in ("offset_s", "peak r", "side r", "sharp", "psr", "conf", "gaps", "verdict"):
        table.add_column(col)
    for rel, a, gaps in rows:
        ok = a.confidence >= threshold
        table.add_row(
            rel,
            f"{a.offset_s:+.3f}",
            f"{a.r_peak:.4f}",
            f"{a.r_side:.4f}",
            f"{a.sharpness:.4f}",
            f"{a.psr:.1f}",
            f"{a.confidence:.4f}",
            str(len(gaps)),
            "[green]ok[/]" if ok else "[bold red]LOW[/]",
        )
    console.print(table)


# ---------------------------------------------------------------------------
# compute
# ---------------------------------------------------------------------------


@app.command()
def compute(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    file: list[str] = typer.Option(
        None, "--file", help="Restrict to these camera files (default: every registered camera)"
    ),
    max_offset_s: float = typer.Option(
        600.0, "--max-offset-s", help="Largest plausible |offset| to search, in seconds"
    ),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", help="Pipeline defaults YAML"),
) -> None:
    """Measure every camera's offset against the episode audio and write the sync block."""
    root = episode_root.resolve()
    threshold = min_confidence(config.resolve())
    episode = load_episode(root / "episode.yaml")

    ep_path = episode_audio_path(root, episode)
    logger.info(f"decoding episode audio: {ep_path.name}")
    ep_energy = energy_envelope(decode_mono(ep_path))
    ep_onset = onset_envelope(ep_energy)
    logger.info(f"episode envelope: {ep_onset.size} frames ({ep_onset.size * HOP_S:.1f}s)")

    rows: list[tuple[str, Alignment, list[SyncGap]]] = []
    for speaker_id, rel in camera_files(episode, file):
        cam_path = root / rel
        if not cam_path.is_file():
            raise typer.BadParameter(
                f"speaker {speaker_id} points at {rel} but that file does not exist under {root}"
            )
        logger.info(f"decoding camera audio for {speaker_id}: {rel}")
        cam_energy = energy_envelope(decode_mono(cam_path))
        cam_onset = onset_envelope(cam_energy)
        alignment = align(ep_onset, cam_onset, max_offset_s)
        gaps = detect_gaps(ep_onset, cam_onset, cam_energy, alignment.lag_frames)
        logger.info(
            f"{rel}: offset {alignment.offset_s:+.3f}s  r={alignment.r_peak:.4f}  "
            f"psr={alignment.psr:.1f}  confidence={alignment.confidence:.4f}  gaps={len(gaps)}"
        )
        rows.append((rel, alignment, gaps))

        previous = find_sync(episode, rel)
        still_verified = False
        if previous is not None:
            unchanged = abs(previous.offset_s - alignment.offset_s) <= 0.01
            if previous.verified and unchanged:
                still_verified = True  # same offset a human already eyeballed — recompute is idempotent
            elif previous.verified:
                logger.warning(
                    f"{rel}: offset changed {previous.offset_s:+.3f}s -> {alignment.offset_s:+.3f}s; "
                    "clearing the previous human verification — re-run `verify` and `mark-verified`"
                )
            episode.sync.remove(previous)
        episode.sync.append(
            SyncEntry(
                file=rel,
                offset_s=alignment.offset_s,
                confidence=alignment.confidence,
                method=METHOD,
                gaps=gaps,
                verified=still_verified,
            )
        )

    episode.sync.sort(key=lambda e: e.file)
    save_episode(root / "episode.yaml", episode)
    render_results(rows, threshold)

    for rel, alignment, gaps in rows:
        if gaps:
            logger.warning(
                f"{rel}: {len(gaps)} discontinuity window(s), first at camera "
                f"{fmt_mmss(gaps[0].camera_s)} — the camera may have stopped/restarted; a single "
                "offset cannot describe it"
            )

    low = [(rel, a) for rel, a, _ in rows if a.confidence < threshold]
    if low:
        for rel, a in low:
            logger.error(
                f"{rel}: confidence {a.confidence:.4f} < sync.min_confidence {threshold} "
                f"(peak r {a.r_peak:.4f}, sharpness {a.sharpness:.4f}, peak-to-sidelobe "
                f"{a.psr:.1f}) — {diagnose(a)}"
            )
        raise typer.Exit(1)

    console.print(
        f"[bold green]OK[/] {len(rows)} camera(s) synced. Next: `sync_cameras.py verify "
        f"{root} --file <cam>` then `mark-verified` once the side-by-side looks right."
    )


# ---------------------------------------------------------------------------
# verify
# ---------------------------------------------------------------------------


def high_energy_moment(ep_env: np.ndarray, lo_s: float, hi_s: float, span_s: float) -> float:
    """Episode time of the loudest `span_s` window inside [lo_s, hi_s]."""
    win = max(1, int(span_s / HOP_S))
    lo, hi = int(lo_s / HOP_S), int(hi_s / HOP_S)
    hi = min(hi, ep_env.size)
    if hi - lo < win:
        raise RuntimeError(
            f"the episode and camera overlap for less than {span_s}s ({lo_s:.2f}s–{hi_s:.2f}s) — "
            "nothing to compare side by side"
        )
    window = ep_env[lo:hi]
    kernel = np.ones(win) / win
    smoothed = np.convolve(window, kernel, mode="valid")
    return round((lo + int(np.argmax(smoothed))) * HOP_S, 3)


@app.command()
def verify(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    file: str = typer.Option(..., "--file", help="Camera file to compare against the episode"),
    seconds: float = typer.Option(5.0, "--seconds", help="Length of the side-by-side excerpt"),
    at: float | None = typer.Option(
        None, "--at", help="Episode timestamp to sample (default: loudest overlapping moment)"
    ),
) -> None:
    """Render a side-by-side excerpt at the computed offset for human eyeballing."""
    root = episode_root.resolve()
    episode = load_episode(root / "episode.yaml")
    rel = camera_files(episode, [file])[0][1]
    entry = find_sync(episode, rel)
    if entry is None:
        raise typer.BadParameter(
            f"no sync entry for {rel} — run `sync_cameras.py compute {root}` first"
        )

    ep_path = episode_audio_path(root, episode)
    ep_video = root / episode.media.episode_video
    cam_path = root / rel
    for path in (ep_video, cam_path):
        if not path.is_file():
            raise typer.BadParameter(f"missing media file: {path}")
        if ffprobe_media(path).width is None:
            raise typer.BadParameter(
                f"{path} has no video stream — a side-by-side check needs pictures in both files"
            )

    ep_duration = ffprobe_media(ep_video).duration_s
    cam_duration = ffprobe_media(cam_path).duration_s
    overlap_lo = max(0.0, entry.offset_s)
    overlap_hi = min(ep_duration, entry.offset_s + cam_duration)

    if at is None:
        ep_t = high_energy_moment(
            energy_envelope(decode_mono(ep_path)), overlap_lo, overlap_hi - seconds, seconds
        )
    else:
        ep_t = float(at)
    if not (overlap_lo <= ep_t <= overlap_hi - seconds):
        raise typer.BadParameter(
            f"--at {ep_t}s is outside the {overlap_lo:.2f}s–{overlap_hi - seconds:.2f}s window where "
            "both files have footage"
        )
    cam_t = ep_t - entry.offset_s

    out_dir = root / "sync"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"verify-{Path(rel).stem}-{ep_t:.3f}s.mp4"
    cmd = [
        "ffmpeg", "-y", "-v", "error", "-nostdin",
        "-ss", f"{ep_t:.3f}", "-i", str(ep_video),
        "-ss", f"{cam_t:.3f}", "-i", str(cam_path),
        "-filter_complex",
        (
            "[0:v]scale=-2:540,setsar=1,drawtext=text='EPISODE %{pts\\:hms}':x=10:y=10:"
            "fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5[l];"
            "[1:v]scale=-2:540,setsar=1,drawtext=text='CAMERA %{pts\\:hms}':x=10:y=10:"
            "fontsize=24:fontcolor=white:box=1:boxcolor=black@0.5[r];"
            "[l][r]hstack=inputs=2[v]"
        ),
        "-map", "[v]", "-map", "0:a?",
        "-t", f"{seconds:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed rendering the side-by-side (exit {proc.returncode}): {proc.stderr.strip()}")

    console.print(
        f"[bold green]OK[/] side-by-side at episode {fmt_mmss(ep_t)} / camera {fmt_mmss(cam_t)} "
        f"(offset {entry.offset_s:+.3f}s, confidence {entry.confidence:.4f})"
    )
    console.print(str(out))
    console.print(
        "[dim]watch it: lips and gestures must land on the same frame in both panels. If they do, "
        f"run `sync_cameras.py mark-verified {root} --file {rel}`.[/]"
    )


# ---------------------------------------------------------------------------
# mark-verified
# ---------------------------------------------------------------------------


@app.command("mark-verified")
def mark_verified(
    episode_root: Path = typer.Argument(..., help="Episode directory containing episode.yaml"),
    file: str = typer.Option(..., "--file", help="Camera file whose side-by-side you checked"),
    config: Path = typer.Option(DEFAULT_CONFIG, "--config", help="Pipeline defaults YAML"),
) -> None:
    """Record that a human checked this camera's side-by-side and it lines up."""
    root = episode_root.resolve()
    threshold = min_confidence(config.resolve())
    episode = load_episode(root / "episode.yaml")
    pairs = camera_files(episode, [file])
    rel = pairs[0][1]

    entry = find_sync(episode, rel)
    if entry is None:
        raise typer.BadParameter(
            f"no sync entry for {rel} — nothing to verify. Run `sync_cameras.py compute {root}` first."
        )
    if entry.confidence < threshold:
        raise typer.BadParameter(
            f"{rel} has confidence {entry.confidence:.4f}, below sync.min_confidence {threshold} — "
            "a human pass cannot promote an offset the correlation never found"
        )
    if entry.verified:
        logger.info(f"{rel} was already verified — no change")
    entry.verified = True
    save_episode(root / "episode.yaml", episode)
    console.print(
        f"[bold green]OK[/] {rel} verified (offset {entry.offset_s:+.3f}s, "
        f"confidence {entry.confidence:.4f}, {len(entry.gaps)} gap(s))"
    )


def cli() -> None:
    """CLI entry point — the one place operational failures become a clean exit."""
    try:
        app()
    except (RuntimeError, FileNotFoundError) as exc:  # deliberate, actionable failures
        console.print(f"[bold red]error[/] {exc}")
        raise SystemExit(1) from None


if __name__ == "__main__":
    cli()
