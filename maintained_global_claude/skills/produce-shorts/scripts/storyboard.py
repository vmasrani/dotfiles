#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "opencv-python-headless>=4.10,<5",
#   "numpy>=1.26",
# ]
# ///
"""Stage 2 — real stills + a rough preview for one frozen pick (references/storyboard-doc.md §2).

shorts: runs the SAME render prep as stage 3 (assemble_audio -> extract_segments ->
align_subtitles -> validate_subtitles -> gen-props) so the stills are what the final will be,
then renders one `npx remotion still` per beat and per cover candidate (every Remotion call
through `queue`, one at a time, with the render-qc.md preflight). A still whose content hash
matches an earlier rev's is copied, not re-rendered.

clips: beats are source frames at each segment start; preview is a 480p straight cut.

Writes `storyboard/rev<N>/`: beats.json, beat-<k>.png, cover-<k>.png, preview.mp4, a clip.yaml
snapshot (the next rev diffs against it) and per-still render logs.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import cv2
import numpy as np
import typer
from loguru import logger
from rich.console import Console

from storyboard_lib import (
    SCRIPTS_DIR,
    SKILL_DIR,
    Ctx,
    OutWord,
    fmt_ts,
    load_ctx,
    load_words,
    output_duration,
    place_words,
    run,
    treatment_label,
)

console = Console()
app = typer.Typer(add_completion=False)

TEMPLATE_DIR = SKILL_DIR / "remotion"
CACHE_BYTES = 209_715_200
COVER_COUNT = 3
COVER_MIN_SEPARATION_S = 6.0
COVER_MAX_CANDIDATES = 40
PREVIEW_W, PREVIEW_H = 360, 640
CLIP_PREVIEW_H = 480

# One queued still: the render-qc.md preflight, then the render. `shel[l]` keeps pgrep from matching
# the shell that is running this very command line.
PREFLIGHT = r"""
n=$(pgrep -f 'chrome-headless-shel[l]' | wc -l | tr -d ' '); echo "headless chromes: $n"
[ "$n" -eq 0 ] || { echo "REFUSING: a render is already live"; exit 75; }
load=$(sysctl -n vm.loadavg | awk '{print $2}'); perf=$(sysctl -n hw.perflevel0.physicalcpu)
echo "load1=$load performance_cores=$perf"
awk -v l="$load" -v p="$perf" 'BEGIN{exit !(l<p)}' || { echo "REFUSING: 1-minute load $load is not under the $perf performance cores"; exit 76; }
"""


# ---------------------------------------------------------------------------
# Revs, small helpers
# ---------------------------------------------------------------------------


def next_rev(clip_dir: Path, forced: int | None) -> int:
    existing = [int(m.group(1)) for d in (clip_dir / "storyboard").glob("rev*") if (m := re.fullmatch(r"rev(\d+)", d.name))]
    if forced is not None:
        if forced in existing:
            raise ValueError(f"rev{forced} already exists in {clip_dir / 'storyboard'} — revs are never overwritten")
        return forced
    return max(existing, default=0) + 1


@dataclass
class Caption:
    start: float
    end: float
    text: str


def parse_ass(path: Path) -> tuple[str, list[Caption]]:
    """(header text, events). Header = everything before [Events], for hashing."""
    text = path.read_text()
    header, _, events = text.partition("[Events]")
    caps = []
    for line in events.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        t = lambda s: sum(float(x) * m for x, m in zip(s.split(":"), (3600, 60, 1)))  # noqa: E731
        caps.append(Caption(t(parts[1]), t(parts[2]), parts[9]))
    return header, caps


def sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def template_hash() -> str:
    files = [p for d in ("src", "lib", "public") for p in sorted((TEMPLATE_DIR / d).rglob("*")) if p.is_file()]
    files += [TEMPLATE_DIR / n for n in ("gen-props.mjs", "package.json", "remotion.config.ts")]
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(TEMPLATE_DIR).as_posix().encode())
        h.update(p.read_bytes())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# Render prep (shorts)
# ---------------------------------------------------------------------------


def uv_script(name: str, *args: str) -> str:
    return run(["uv", "run", "--quiet", str(SCRIPTS_DIR / name), *args], what=name)


def sync_workspace(ctx: Ctx) -> Path:
    """One template copy per clip, refreshed only when the skill's template changed (stamp file)."""
    ws = ctx.clip_dir / "remotion"
    ws.mkdir(exist_ok=True)
    stamp, current = ws / ".template-hash", template_hash()
    if not stamp.exists() or stamp.read_text().strip() != current:
        run(["rsync", "-a", "--exclude=node_modules", "--exclude=props.json", "--exclude=out", "--exclude=public/clip",
             f"{TEMPLATE_DIR}/", f"{ws}/"], what="syncing the Remotion template")
        stamp.write_text(current)
    # Reinstall whenever the lockfile differs from the one node_modules was installed from — a template
    # that gained a dependency (e.g. @remotion/captions) must not render against stale node_modules.
    lock_stamp, lock = ws / ".lock-hash", hashlib.sha256((ws / "package-lock.json").read_bytes()).hexdigest()[:16]
    if not (ws / "node_modules" / ".bin" / "remotion").exists() or not lock_stamp.exists() or lock_stamp.read_text().strip() != lock:
        logger.info("npm ci in the clip's Remotion workspace (first run, or the template's lockfile changed)")
        queued(f"cd {ws} && npm ci --no-audit --no-fund", ctx.clip_dir / "storyboard" / "npm-ci.log", "npm ci")
        lock_stamp.write_text(lock)
    return ws


BUSY_EXIT_CODES = (75, 76)          # PREFLIGHT: a render is live / machine load too high
BUSY_BUDGET_S = 1200                # how long a still waits for the machine before failing loud
BUSY_POLL_S = 20


def queued(shell: str, log: Path, what: str, wait_if_busy: bool = False) -> None:
    """Run through `queue` as one quoted string. With `wait_if_busy`, a refused preflight (another render
    live / load above the performance cores) is waited out, polled every BUSY_POLL_S up to BUSY_BUDGET_S."""
    log.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + BUSY_BUDGET_S
    while True:
        proc = subprocess.run(["queue", shell], capture_output=True, text=True)
        log.write_text(proc.stdout + proc.stderr)
        busy = wait_if_busy and proc.returncode in BUSY_EXIT_CODES
        if not busy or time.monotonic() > deadline:
            break
        time.sleep(BUSY_POLL_S)
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-20:])
        raise RuntimeError(f"{what} failed (exit {proc.returncode}); full log {log}\n{tail}")


def prep_short(ctx: Ctx, rev_dir: Path, placed: list[OutWord]) -> tuple[Path, str, dict]:
    """assemble_audio -> extract_segments -> align_subtitles -> validate_subtitles -> gen-props.

    Skipped (not degraded) when clip.yaml (minus `review`/`status`, which the render path never reads),
    episode.yaml and the template match the last successful prep: the staged files are a pure function of those.
    """
    v = len(ctx.clip.get("render", {}).get("versions") or []) + 1
    stamp = ctx.clip_dir / "storyboard" / ".prep-stamp.json"
    key = sha([json.dumps({k: v for k, v in ctx.clip.items() if k not in ("review", "status")}, sort_keys=True, default=str), (ctx.root / "episode.yaml").read_text(), template_hash(), v,
                [(SCRIPTS_DIR / n).read_bytes().hex() for n in ("facelib.py", "framer.py", "extract_segments.py", "align_subtitles.py", "capplace.py", "validate_subtitles.py")]])
    if stamp.is_file() and json.loads(stamp.read_text())["key"] == key:
        saved = json.loads(stamp.read_text())
        if (ctx.clip_dir / "remotion" / "props.json").is_file():
            logger.info("render prep is current for this clip.yaml — reusing staged audio, captions, cuts and props")
            return ctx.clip_dir / "remotion", saved["ass"], saved["validation"]
    root = ["--episode-root", str(ctx.root)]
    audio, ass = f"renders/v{v}-audio.wav", f"subtitles/v{v}.ass"
    words_out = rev_dir / "words-output-time.json"
    words_out.write_text(json.dumps({"words": [
        {"w": w.text, "start": round(w.start, 3), "end": round(w.end, 3), "speaker": w.speaker} for w in placed]}))
    # v<N> here is the UNPUBLISHED attempt (render.versions is empty/append-only), so --force is correct:
    # the storyboard re-assembles it every rev; stage 3 re-runs it if clip.yaml changed since approval.
    uv_script("assemble_audio.py", str(ctx.clip_dir), "--version", str(v), "--force", *root)
    # extract_segments first: it measures where each mouth is (assets/aroll/layout.json), which caption placement needs
    uv_script("extract_segments.py", str(ctx.clip_dir), *root)
    uv_script("align_subtitles.py", str(ctx.clip_dir), "--audio", str(ctx.clip_dir / audio), "--version", str(v),
              "--words-json", str(words_out), *root)
    # Sweep-then-assert: a subtitle finding does not stop the stills (the reviewer should SEE the
    # captions), but it is recorded in beats.json and the run exits nonzero at the end — stage 3 would refuse it.
    check = subprocess.run(["uv", "run", "--quiet", str(SCRIPTS_DIR / "validate_subtitles.py"), str(ctx.clip_dir),
                            "--ass", str(ctx.clip_dir / ass), *root], capture_output=True, text=True)
    (rev_dir / "validate_subtitles.log").write_text(check.stdout + check.stderr)
    validation = {"passed": check.returncode == 0, "log": "validate_subtitles.log",
                  "summary": (check.stdout + check.stderr).strip().splitlines()[-1] if check.returncode else "ok"}
    ws = sync_workspace(ctx)
    run(["node", "gen-props.mjs", str(ctx.clip_dir), "--audio", audio, "--ass", ass,
         "--episode", str(ctx.root / "episode.yaml"), "--defaults", str(SKILL_DIR / "config" / "defaults.yaml")],
        what="gen-props.mjs", cwd=ws)
    stamp.write_text(json.dumps({"key": key, "ass": ass, "validation": validation}))
    return ws, ass, validation


# ---------------------------------------------------------------------------
# Beats
# ---------------------------------------------------------------------------


def segment_at(timeline: list[dict], t: float) -> dict:
    return next((s for s in timeline if s["output_in"] <= t < s["output_out"]), timeline[-1])


def caption_point(caps: list[Caption], t0: float, t1: float) -> float:
    """Midpoint of [t0, t1], nudged into the caption window that overlaps it most (so captions are visible)."""
    best = max(((min(c.end, t1) - max(c.start, t0), c) for c in caps), key=lambda x: x[0], default=(0, None))
    if best[1] is None or best[0] <= 0.3:
        return (t0 + t1) / 2
    lo, hi = max(best[1].start, t0), min(best[1].end, t1)
    return (lo + hi) / 2


def spoken_lines(ctx: Ctx, placed: list[OutWord], t0: float, t1: float, limit: int = 110) -> list[dict]:
    out: list[dict] = []
    for w in placed:
        if not (t0 <= (w.start + w.end) / 2 < t1):
            continue
        if out and out[-1]["speaker"] == w.speaker:
            out[-1]["text"] += " " + w.text
        else:
            out.append({"speaker": w.speaker, "name": ctx.name(w.speaker), "text": w.text})
    shown, used = [], 0
    for line in out[:3]:
        room = limit - used
        if room <= 0:
            break
        text = line["text"] if len(line["text"]) <= room else line["text"][:room].rsplit(" ", 1)[0] + "…"
        shown.append({**line, "text": text})
        used += len(text)
    return shown


def treatment_runs(timeline: list[dict]) -> list[dict]:
    runs: list[dict] = []
    for s in timeline:
        key = (s["visual"]["treatment"], tuple(s["visual"].get("speakers") or ()))
        if runs and runs[-1]["key"] == key:
            runs[-1]["t1"] = s["output_out"]
            runs[-1]["segments"].append(s["id"])
        else:
            runs.append({"key": key, "t0": s["output_in"], "t1": s["output_out"], "segments": [s["id"]], "first": s})
    return runs


def plan_beats(ctx: Ctx, placed: list[OutWord], caps: list[Caption]) -> list[dict]:
    timeline, dur = ctx.clip["timeline"], output_duration(ctx.clip)
    beats: list[dict] = []

    def add(kind: str, t0: float, t1: float, run: dict, t: float) -> None:
        v = run["first"]["visual"]
        beats.append({
            "kind": kind, "t_start": round(t0, 3), "t_end": round(t1, 3), "t_still": round(t, 3),
            "treatment": v["treatment"], "speakers": v.get("speakers"),
            "framing": treatment_label(ctx, v["treatment"], v.get("speakers")),
            "reason": v.get("reason"), "locked": bool(v.get("locked")), "segments": run["segments"],
            "lines": spoken_lines(ctx, placed, t0, t1),
        })

    runs = treatment_runs(timeline)
    if ctx.fmt == "clip":
        for s in timeline:
            r = {"segments": [s["id"]], "first": s}
            add("segment", s["output_in"], s["output_out"], r, s["output_in"] + min(0.5, (s["output_out"] - s["output_in"]) / 2))
    else:
        add("open", 0.0, min(1.0, dur), runs[0], caption_point(caps, 0.0, min(1.0, dur)))
        for r in runs:
            add("change", r["t0"], r["t1"], r, caption_point(caps, r["t0"], r["t1"]))
        add("close", max(dur - 1.0, 0.0), dur, runs[-1], caption_point(caps, max(dur - 1.0, 0.0), dur))
    for k, b in enumerate(beats, 1):
        b["k"] = k
        if b["kind"] in ("open", "close"):
            b["lines"] = spoken_lines(ctx, placed, b["t_start"], b["t_end"] + 2.0 if b["kind"] == "open" else b["t_end"])
    return beats


# ---------------------------------------------------------------------------
# Covers: largest face, between words
# ---------------------------------------------------------------------------

_FACE = None


def face_fraction(png: bytes) -> float:
    global _FACE
    if _FACE is None:
        _FACE = cv2.CascadeClassifier(str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml"))
        if _FACE.empty():
            raise RuntimeError("OpenCV could not load its bundled Haar face cascade")
    img = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    faces = _FACE.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5, minSize=(max(20, img.shape[1] // 14),) * 2)
    return max((w * h for _, _, w, h in faces), default=0) / (img.shape[0] * img.shape[1])


def grab(video: Path, t: float, width: int) -> bytes:
    proc = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1", "-vf", f"scale={width}:-2",
         "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(f"ffmpeg could not grab a frame from {video} at {t:.3f}s: {proc.stderr.decode()[-300:]}")
    return proc.stdout


def score_candidate(ctx: Ctx, t: float) -> tuple[float, bool]:
    """(largest face as a fraction of the OUTPUT frame, is-solo) at output time t."""
    seg = segment_at(ctx.clip["timeline"], t)
    local = min(t - seg["output_in"], seg["output_out"] - seg["output_in"] - 0.15)   # a seek at/after EOF yields no frame
    if ctx.fmt == "clip":
        src = ctx.root / seg["source_file"]
        probe = grab(src, seg["source_in"] + local, 640)
        return face_fraction(probe), True
    base = ctx.clip_dir / "assets" / "aroll"
    if seg["visual"]["treatment"] == "splitscreen":
        # panels are 1080x960 inside a 1080x1920 frame: normalise to the whole frame
        scores = [face_fraction(grab(base / f"{seg['id']}-{p}.mp4", local, 270)) / 2 for p in ("top", "bottom")]
        return max(scores), False
    return face_fraction(grab(base / f"{seg['id']}.mp4", local, 270)), True


def cover_candidates(ctx: Ctx, placed: list[OutWord]) -> list[dict]:
    gaps = [(placed[i].start + placed[i - 1].end) / 2 for i in range(1, len(placed)) if placed[i].start - placed[i - 1].end >= 0.12]
    dur = output_duration(ctx.clip)
    gaps = [t for t in gaps if 0.5 < t < dur - 0.5]
    if len(gaps) > COVER_MAX_CANDIDATES:
        step = len(gaps) / COVER_MAX_CANDIDATES
        gaps = [gaps[int(i * step)] for i in range(COVER_MAX_CANDIDATES)]
    if len(gaps) < COVER_COUNT:
        raise ValueError(f"only {len(gaps)} pauses between words — cannot choose {COVER_COUNT} cover moments (clip too short/continuous)")
    scored = sorted(((*score_candidate(ctx, t), t) for t in gaps), key=lambda x: (x[0], x[1]), reverse=True)
    picked: list[tuple[float, bool, float]] = []
    for cand in scored:
        if all(abs(cand[2] - p[2]) >= COVER_MIN_SEPARATION_S for p in picked):
            picked.append(cand)
        if len(picked) == COVER_COUNT:
            break
    if len(picked) < COVER_COUNT:
        raise ValueError(f"found {len(picked)} cover moments {COVER_MIN_SEPARATION_S:g}s apart, need {COVER_COUNT}")
    return [{"k": k, "t_still": round(t, 3), "face_fraction": round(score, 4), "solo": solo}
            for k, (score, solo, t) in enumerate(sorted(picked, key=lambda x: x[2]), 1)]


# ---------------------------------------------------------------------------
# Stills
# ---------------------------------------------------------------------------


def still_hash(ctx: Ctx, t: float, header: str, caps: list[Caption], tmpl: str) -> str:
    seg = segment_at(ctx.clip["timeline"], t)
    local = t - seg["output_in"]
    # the staged cuts ARE the framing (crops are computed per segment): hash their bytes, not any stored crop
    cuts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ctx.clip_dir / "assets" / "aroll").glob(f"{seg['id']}*.mp4"))}
    visible = [c.text for c in caps if c.start <= t < c.end]
    return sha({
        "tmpl": tmpl, "fmt": ctx.fmt, "output": ctx.clip["output"], "ass_header": sha(header),
        "src": [seg["source_file"], round(seg["source_in"] + local, 2)],
        "visual": {k: seg["visual"].get(k) for k in ("treatment", "speakers", "crop", "motion")},
        "cuts": cuts, "captions": visible,
    })


def earlier_stills(clip_dir: Path) -> dict[str, Path]:
    found: dict[str, Path] = {}
    for beats_json in sorted((clip_dir / "storyboard").glob("rev*/beats.json")):
        data = json.loads(beats_json.read_text())
        for item in data["beats"] + data["covers"]:
            png = beats_json.parent / item["still"]
            if png.is_file():
                found[item["hash"]] = png
    return found


def render_still(ctx: Ctx, ws: Path | None, t: float, out: Path, log: Path, total_frames: int | None) -> None:
    if ctx.fmt == "clip":
        seg = segment_at(ctx.clip["timeline"], t)
        out.write_bytes(grab(ctx.root / seg["source_file"], seg["source_in"] + (t - seg["output_in"]), 960))
        return
    fps = float(ctx.clip["output"]["fps"])
    frame = min(int(round(t * fps)), total_frames - 1)
    out.unlink(missing_ok=True)
    shell = (
        f"{PREFLIGHT}\ncd {ws} && npx remotion still Short {out} --props=props.json --frame={frame} "
        f"--timeout=300000 --offthreadvideo-cache-size-in-bytes={CACHE_BYTES} --concurrency=1 --overwrite"
    )
    queued(shell, log, f"remotion still at {t:.2f}s (frame {frame})", wait_if_busy=True)
    if not out.is_file():
        raise RuntimeError(f"remotion reported success but {out} does not exist; log {log}")


def produce_stills(ctx: Ctx, ws: Path | None, rev_dir: Path, items: list[tuple[str, dict]], header: str,
                   caps: list[Caption]) -> tuple[int, int]:
    tmpl = template_hash()
    prior = earlier_stills(ctx.clip_dir)
    total_frames = None
    if ws is not None:
        total_frames = json.loads((ws / "props.json").read_text())["durationInFrames"]
    rendered = reused = 0
    for prefix, item in items:
        item["hash"] = still_hash(ctx, item["t_still"], header, caps, tmpl)
        name = f"{prefix}-{item['k']}.png"
        item["still"] = name
        if item["hash"] in prior:
            shutil.copyfile(prior[item["hash"]], rev_dir / name)
            item["reused"] = True
            reused += 1
            continue
        render_still(ctx, ws, item["t_still"], rev_dir / name, rev_dir / f"{prefix}-{item['k']}.log", total_frames)
        item["reused"] = False
        rendered += 1
    return rendered, reused


# ---------------------------------------------------------------------------
# Rough preview
# ---------------------------------------------------------------------------


def preview_short(ctx: Ctx, rev_dir: Path, v: int) -> Path:
    timeline, base = ctx.clip["timeline"], ctx.clip_dir / "assets" / "aroll"
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    n = 0
    for i, seg in enumerate(timeline):
        d = seg["output_out"] - seg["output_in"]
        fit = f"tpad=stop_mode=clone:stop_duration=0.2,trim=duration={d:.3f},setpts=PTS-STARTPTS,setsar=1,fps=30"
        if seg["visual"]["treatment"] == "splitscreen":
            files = [base / f"{seg['id']}-top.mp4", base / f"{seg['id']}-bottom.mp4"]
            for f in files:
                inputs += ["-i", str(f)]
            filters += [f"[{n}:v]{fit},scale={PREVIEW_W}:{PREVIEW_H // 2}[p{i}a]", f"[{n + 1}:v]{fit},scale={PREVIEW_W}:{PREVIEW_H // 2}[p{i}b]",
                        f"[p{i}a][p{i}b]vstack[v{i}]"]
            n += 2
        else:
            inputs += ["-i", str(base / f"{seg['id']}.mp4")]
            filters.append(f"[{n}:v]{fit},scale={PREVIEW_W}:{PREVIEW_H}[v{i}]")
            n += 1
        labels.append(f"[v{i}]")
    inputs += ["-i", str(ctx.clip_dir / "renders" / f"v{v}-audio.wav")]
    out = rev_dir / "preview.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=1:a=0[v]",
         "-map", "[v]", "-map", f"{n}:a", "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-shortest", "-movflags", "+faststart", str(out)], what="building the 360p preview")
    return out


def preview_clip(ctx: Ctx, rev_dir: Path) -> Path:
    inputs, filters, labels = [], [], []
    for i, seg in enumerate(ctx.clip["timeline"]):
        d = seg["source_out"] - seg["source_in"]
        inputs += ["-ss", f"{seg['source_in']:.3f}", "-t", f"{d:.3f}", "-i", str(ctx.root / seg["source_file"])]
        filters += [f"[{i}:v]scale=-2:{CLIP_PREVIEW_H},setsar=1,fps=30[v{i}]", f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo[a{i}]"]
        labels.append(f"[v{i}][a{i}]")
    out = rev_dir / "preview.mp4"
    run(["ffmpeg", "-v", "error", "-y", *inputs, "-filter_complex", ";".join(filters) + f";{''.join(labels)}concat=n={len(labels)}:v=1:a=1[v][a]",
         "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "27", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", str(out)], what="building the 480p straight cut")
    return out


def probed_duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)], what="ffprobe").strip())


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Clip directory containing clip.yaml"),
    episode_root: Path = typer.Option(None, "--episode-root", help="Episode root (default: CLIP_DIR/../..)"),
    rev: int = typer.Option(None, "--rev", help="Revision number (default: next free)"),
) -> None:
    """Render prep + stills + rough preview for CLIP_DIR into storyboard/rev<N>/."""
    t_start, timings = time.monotonic(), {}
    ctx = load_ctx(clip_dir, episode_root)
    n = next_rev(ctx.clip_dir, rev)
    rev_dir = ctx.clip_dir / "storyboard" / f"rev{n}"
    rev_dir.mkdir(parents=True)
    placed = place_words(ctx, load_words(ctx))
    dur = output_duration(ctx.clip)

    def lap(name: str, since: float) -> float:
        timings[name] = round(time.monotonic() - since, 1)
        return time.monotonic()

    t = time.monotonic()
    ws, header, caps, v = None, "", [], len(ctx.clip.get("render", {}).get("versions") or []) + 1
    validation = {"passed": True, "summary": "n/a (clip)"}
    if ctx.fmt == "short":
        ws, ass, validation = prep_short(ctx, rev_dir, placed)
        header, caps = parse_ass(ctx.clip_dir / ass)
    t = lap("prep", t)

    beats = plan_beats(ctx, placed, caps)
    covers = cover_candidates(ctx, placed)
    t = lap("plan_and_covers", t)

    rendered, reused = produce_stills(ctx, ws, rev_dir, [("beat", b) for b in beats] + [("cover", c) for c in covers], header, caps)
    t = lap("stills", t)

    preview = preview_short(ctx, rev_dir, v) if ctx.fmt == "short" else preview_clip(ctx, rev_dir)
    got = probed_duration(preview)
    expected = dur if ctx.fmt == "short" else sum(s["source_out"] - s["source_in"] for s in ctx.clip["timeline"])
    if abs(got - expected) > 0.25:
        raise RuntimeError(f"{preview} is {got:.2f}s but the timeline is {expected:.2f}s")
    t = lap("preview", t)

    shutil.copyfile(ctx.clip_yaml, rev_dir / "clip.yaml")
    timings["total"] = round(time.monotonic() - t_start, 1)
    (rev_dir / "beats.json").write_text(json.dumps({
        "rev": n, "format": ctx.fmt, "duration_s": dur, "fps": ctx.clip["output"]["fps"], "preview": preview.name,
        "beats": beats, "covers": covers, "stills": {"rendered": rendered, "reused": reused}, "timings_s": timings,
        "subtitle_validation": validation,
    }, indent=2))
    console.print(
        f"[green]rev{n}[/] {ctx.clip['clip']['id']}: {len(beats)} beats, {len(covers)} covers "
        f"({rendered} rendered, {reused} reused), preview {preview.stat().st_size / 1e6:.1f} MB — "
        f"{timings} -> {rev_dir}"
    )
    console.print("beats: " + ", ".join(f"{b['k']}@{fmt_ts(b['t_still'])} {b['framing']}" for b in beats))
    if not validation["passed"]:
        console.print(f"[bold red]SUBTITLE VALIDATION FAILED[/] ({validation['summary']}) — see {rev_dir / validation['log']}; "
                      "the stills and preview are built, but stage 3 will refuse these captions")
        raise typer.Exit(2)


if __name__ == "__main__":
    app()
