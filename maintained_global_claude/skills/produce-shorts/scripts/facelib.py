"""Face detection, speaker identity and crop geometry for the shorts framing path.

Not executable: sibling entry scripts (`extract_segments.py`) import it the way they import
`pslib`; the importing script declares the dependencies (opencv-python-headless, numpy).

Why this exists: one static crop per speaker cannot follow people who move over a 99-minute
recording, and a gallery-view recording (Zoom-style tiles) has no per-speaker crop at all — the
speaker is a small tile whose position changes with the layout. So the crop is computed PER
SEGMENT from where the speaker's face actually is in that segment's source frames.

Models (OpenCV Zoo, pinned by sha256, fetched once into ~/.cache/produce-shorts/models):

* **YuNet** (`cv2.FaceDetectorYN`) — face boxes + 5 landmarks, ~20 ms/frame on CPU. Chosen over
  MediaPipe BlazeFace: it is the OpenCV-maintained detector, scores higher on hard faces
  (small tiles, glasses, headphones), needs no extra runtime, and `opencv-python-headless` is
  already a dependency of the stage-2 scripts.
* **SFace** int8 (`cv2.FaceRecognizerSF`) — a 128-d identity embedding, used only on shared
  (multi-person) sources to tell which detected face is which speaker.

Two source kinds, one code path (`locate_speaker`):

* **isolated camera** (`speakers[].camera_file`): the frame holds one person — take the largest face.
* **shared frame** (gallery/tiles): identify the speaker's face by embedding against a per-source
  gallery built from the transcript's solo turns (`speaker_gallery`): faces are clustered by
  identity, and each speaker is paired with the cluster whose mouth region moves while that
  speaker is the only one talking. Layouts may change mid-recording; identity does not.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import math
import subprocess
import urllib.request
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterator

import cv2
import numpy as np
from loguru import logger

from pslib import Transcript

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

MODEL_DIR = Path.home() / ".cache" / "produce-shorts" / "models"
_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"
MODELS = {
    "yunet": (
        "face_detection_yunet_2023mar.onnx",
        f"{_ZOO}/face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
    ),
    "sface": (
        "face_recognition_sface_2021dec_int8.onnx",
        f"{_ZOO}/face_recognition_sface/face_recognition_sface_2021dec_int8.onnx",
        "2b0e941e6f16cc048c20aee0c8e31f569118f65d702914540f7bfdc14048d78a",
    ),
}


def model_path(key: str) -> Path:
    name, url, digest = MODELS[key]
    path = MODEL_DIR / name
    if not path.is_file():
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"fetching face model {name} -> {path}")
        urllib.request.urlretrieve(url, path)
    got = hashlib.sha256(path.read_bytes()).hexdigest()
    if got != digest:
        raise RuntimeError(
            f"face model {path} has sha256 {got}, expected {digest} — delete it and re-run to refetch from {url}"
        )
    return path


DETECT_SCORE = 0.7
SAME_PERSON_COSINE = 0.363   # OpenCV Zoo's recommended SFace same-identity threshold


@lru_cache(maxsize=1)
def _detector() -> "cv2.FaceDetectorYN":
    return cv2.FaceDetectorYN.create(str(model_path("yunet")), "", (320, 320), DETECT_SCORE, 0.3, 5000)


@lru_cache(maxsize=1)
def _recognizer() -> "cv2.FaceRecognizerSF":
    return cv2.FaceRecognizerSF.create(str(model_path("sface")), "")


class FaceError(RuntimeError):
    """One segment's speaker cannot be framed (per-case failure; callers sweep these and report them all)."""


@dataclass(frozen=True)
class Face:
    t: float                # source time of the frame (seconds)
    x: float
    y: float
    w: float
    h: float
    score: float
    lm: tuple[float, ...]   # right eye, left eye, nose, right mouth corner, left mouth corner (x, y each)
    row: tuple[float, ...]  # the raw 15-float YuNet row (alignCrop input)
    bounds: tuple[float, float, float, float] | None = None   # tile rectangle (left, top, right, bottom) on a shared frame

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    @property
    def eye_y(self) -> float:
        return (self.lm[1] + self.lm[3]) / 2

    def to_json(self) -> dict:
        return {"t": round(self.t, 3), "box": [round(v, 1) for v in (self.x, self.y, self.w, self.h)],
                "eye_y": round(self.eye_y, 1), "score": round(self.score, 3),
                "bounds": None if self.bounds is None else [round(v, 1) for v in self.bounds]}


def detect(frame: np.ndarray, t: float) -> list[Face]:
    h, w = frame.shape[:2]
    det = _detector()
    det.setInputSize((w, h))
    _, rows = det.detect(frame)
    if rows is None:
        return []
    return [Face(t, *map(float, r[:4]), float(r[14]), tuple(map(float, r[4:14])), tuple(map(float, r)))
            for r in rows]


def embed(frame: np.ndarray, face: Face) -> np.ndarray:
    rec = _recognizer()
    vec = rec.feature(rec.alignCrop(frame, np.array(face.row, dtype=np.float32))).flatten().astype(np.float64)
    return vec / np.linalg.norm(vec)


# ---------------------------------------------------------------------------
# Frames
# ---------------------------------------------------------------------------


def iter_frames(video: Path, dims: tuple[int, int], start: float, duration: float, fps: float) -> Iterator[tuple[float, np.ndarray]]:
    """Stream BGR frames at `fps` from [start, start+duration) as (source time, frame)."""
    if start < -0.01:
        raise ValueError(f"{video}: cannot sample before the start of the file (start={start:.3f}s)")
    w, h = dims
    cmd = ["ffmpeg", "-hide_banner", "-nostdin", "-loglevel", "error", "-ss", f"{max(start, 0.0):.6f}", "-i", str(video),
           "-t", f"{duration:.6f}", "-an", "-vf", f"fps={fps:g}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    size = w * h * 3
    k = 0
    while (raw := proc.stdout.read(size)) and len(raw) == size:
        yield start + k / fps, np.frombuffer(raw, np.uint8).reshape(h, w, 3)
        k += 1
    proc.stdout.close()
    err = proc.stderr.read().decode(errors="replace").strip()
    if proc.wait() != 0:
        raise RuntimeError(f"ffmpeg failed sampling {video} [{start:.2f}+{duration:.2f}s]: {err or '<empty>'}")
    if k == 0:
        raise RuntimeError(f"ffmpeg returned no frames from {video} [{start:.2f}+{duration:.2f}s] — range outside the file?")


# ---------------------------------------------------------------------------
# Speaker gallery (shared frames only)
# ---------------------------------------------------------------------------

GALLERY_WINDOWS = 10           # solo windows per speaker
GALLERY_MIN_SOLO_S = 5.0
GALLERY_WINDOW_S = 3.0
GALLERY_FPS = 6
GALLERY_MIN_ACTIVITY = 0.3     # mean z-score of the paired cluster's mouth motion while its speaker talks
GALLERY_MIN_MARGIN = 0.25      # ... and its lead over every other cluster


def _solo_windows(transcript: Transcript, speaker: str) -> list[tuple[float, float]]:
    segs = sorted(transcript.segments, key=lambda s: s.start)
    clean = []
    for i, s in enumerate(segs):
        if s.speaker != speaker or s.end - s.start < GALLERY_MIN_SOLO_S:
            continue
        overlapped = any(o.speaker != speaker and o.start < s.end and o.end > s.start for o in segs[max(0, i - 3): i + 4])
        if not overlapped:
            clean.append(s)
    step = max(1, len(clean) / GALLERY_WINDOWS)
    picked = [clean[int(k * step)] for k in range(min(GALLERY_WINDOWS, len(clean)))]
    return [((s.start + s.end) / 2 - GALLERY_WINDOW_S / 2, GALLERY_WINDOW_S) for s in picked]


def _mouth_motion(prev: np.ndarray, cur: np.ndarray, face: Face) -> float:
    """Mean absolute grey change in the mouth region between two consecutive frames."""
    mx = (face.lm[6] + face.lm[8]) / 2
    my = (face.lm[7] + face.lm[9]) / 2
    mw = max(abs(face.lm[8] - face.lm[6]), 4.0)
    ys, ye = int(max(0, my - 0.5 * mw)), int(my + 0.7 * mw)
    xs, xe = int(max(0, mx - 0.8 * mw)), int(mx + 0.8 * mw)
    return float(np.abs(cur[ys:ye, xs:xe] - prev[ys:ye, xs:xe]).mean())


def _window_tracks(video: Path, dims: tuple[int, int], start: float) -> list[tuple[np.ndarray, float]]:
    """(identity embedding, mean mouth motion) for every face present through the whole window."""
    tracks: list[dict] = []
    prev_gray = None
    n = 0
    for t, frame in iter_frames(video, dims, start, GALLERY_WINDOW_S, GALLERY_FPS):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
        n += 1
        used: set[int] = set()
        for face in detect(frame, t):
            best = min((k for k, tr in enumerate(tracks) if k not in used and tr["last_n"] == n - 1),
                       key=lambda k: np.hypot(tracks[k]["last"].cx - face.cx, tracks[k]["last"].cy - face.cy), default=None)
            if best is not None and np.hypot(tracks[best]["last"].cx - face.cx, tracks[best]["last"].cy - face.cy) < 0.6 * face.w:
                tr = tracks[best]
            else:
                tr = {"emb": embed(frame, face), "motion": [], "count": 0}
                tracks.append(tr)
                best = len(tracks) - 1
            used.add(best)
            if prev_gray is not None and tr["count"] > 0:
                tr["motion"].append(_mouth_motion(prev_gray, gray, face))
            tr["last"], tr["last_n"] = face, n
            tr["count"] += 1
        prev_gray = gray
    return [(tr["emb"], float(np.mean(tr["motion"]))) for tr in tracks if tr["count"] >= 0.7 * n and tr["motion"]]


def _cluster(embs: list[np.ndarray]) -> list[int]:
    centroids: list[np.ndarray] = []
    labels: list[int] = []
    for e in embs:
        sims = [float(c @ e) for c in centroids]
        k = int(np.argmax(sims)) if sims and max(sims) >= SAME_PERSON_COSINE else None
        if k is None:
            centroids.append(e.copy())
            labels.append(len(centroids) - 1)
        else:
            labels.append(k)
            centroids[k] = centroids[k] + e
            centroids[k] /= np.linalg.norm(centroids[k])
    # one reassignment pass against the final centroids
    return [int(np.argmax([float(c @ e) for c in centroids])) for e in embs]


def speaker_gallery(cache: Path, video: Path, video_rel: str, dims: tuple[int, int], transcript: Transcript,
                    speakers: list[str]) -> dict[str, np.ndarray]:
    """Identity embedding per speaker for a shared (multi-person) frame. Cached at `cache`."""
    key = hashlib.sha256(json.dumps([video_rel, video.stat().st_size, sorted(speakers), MODELS["sface"][2],
                                     MODELS["yunet"][2], GALLERY_WINDOWS, len(transcript.segments)]).encode()).hexdigest()
    if cache.is_file():
        blob = json.loads(cache.read_text())
        if blob["key"] == key:
            return {sid: np.array(v["embedding"]) for sid, v in blob["speakers"].items()}
        logger.info(f"gallery {cache.name} is stale — rebuilding")

    logger.info(f"building speaker gallery for {video_rel}: {GALLERY_WINDOWS} solo windows x {len(speakers)} speakers")
    obs: list[tuple[str, int, np.ndarray, float]] = []   # speaker, window id, embedding, motion
    wid = 0
    for sid in speakers:
        windows = _solo_windows(transcript, sid)
        if len(windows) < 5:
            raise RuntimeError(f"speaker {sid!r} has only {len(windows)} clean solo turns >= {GALLERY_MIN_SOLO_S:g}s in the "
                               f"transcript — cannot learn which face is theirs in {video_rel}")
        for start, _ in windows:
            obs += [(sid, wid, e, m) for e, m in _window_tracks(video, dims, start)]
            wid += 1

    labels = _cluster([o[2] for o in obs])
    support = np.bincount(labels)
    keep = [int(k) for k in np.argsort(support)[::-1][: len(speakers)]]
    if len(keep) < len(speakers) or any(support[k] < 5 for k in keep):
        raise RuntimeError(f"found {int((support >= 5).sum())} distinct faces in {video_rel}'s solo turns but {len(speakers)} "
                           f"speakers share it (support per face: {support.tolist()}) — is someone off camera?")

    motions = {k: np.array([o[3] for o, l in zip(obs, labels) if l == k]) for k in keep}
    z = {k: (m - m.mean()) / (m.std() + 1e-6) for k, m in motions.items()}
    z_by_obs = {i: z[l][sum(1 for ll in labels[:i] if ll == l)] for i, l in enumerate(labels) if l in keep}
    matrix = np.zeros((len(speakers), len(keep)))
    for si, sid in enumerate(speakers):
        for ci, k in enumerate(keep):
            vals = [z_by_obs[i] for i, o in enumerate(obs) if o[0] == sid and labels[i] == k]
            matrix[si, ci] = np.mean(vals) if vals else -9.0
    best = max(itertools.permutations(range(len(keep))), key=lambda p: sum(matrix[s, c] for s, c in enumerate(p)))
    diag = "\n".join(f"  {sid}: " + "  ".join(f"face{c}={matrix[si, c]:+.2f}" for c in range(len(keep))) for si, sid in enumerate(speakers))
    for si, sid in enumerate(speakers):
        mine, rest = matrix[si, best[si]], max(matrix[si, c] for c in range(len(keep)) if c != best[si])
        if mine < GALLERY_MIN_ACTIVITY or mine - rest < GALLERY_MIN_MARGIN:
            raise RuntimeError(f"cannot tell which face is {sid!r} in {video_rel}: mouth-motion while they talk "
                               f"(mean z-score per face):\n{diag}\nneeds paired score >= {GALLERY_MIN_ACTIVITY} and a lead >= {GALLERY_MIN_MARGIN}")
    logger.info(f"gallery mouth-motion matrix (rows = speaker talking, cols = face cluster):\n{diag}\n  pairing: "
                + ", ".join(f"{sid}=face{best[si]}" for si, sid in enumerate(speakers)))

    vectors: dict[str, np.ndarray] = {}
    for si, sid in enumerate(speakers):
        k = keep[best[si]]
        v = np.sum([o[2] for o, l in zip(obs, labels) if l == k], axis=0)
        vectors[sid] = v / np.linalg.norm(v)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"key": key, "video": video_rel, "speakers": {
        sid: {"embedding": vectors[sid].tolist(), "faces_seen": int(support[keep[best[si]]]),
              "activity_z": round(float(matrix[si, best[si]]), 2)} for si, sid in enumerate(speakers)}}, indent=1))
    return vectors


# ---------------------------------------------------------------------------
# Locating one speaker across one segment
# ---------------------------------------------------------------------------

SEAM_GRADIENT = 24.0     # grey-level step that counts as a tile seam pixel
SEAM_COVERAGE = 0.9      # fraction of the probe band the step must span
Bounds = tuple[float, float, float, float]   # left, top, right, bottom


def _seam_bounds(gray: np.ndarray, f: Face) -> Bounds:
    """The tile rectangle around a face: the nearest long straight colour seam on each side (else the frame edge)."""
    H, W = gray.shape
    band_y0, band_y1 = int(max(0, f.cy - 0.8 * f.h)), int(min(H, f.cy + 0.8 * f.h))
    band_x0, band_x1 = int(max(0, f.cx - 0.8 * f.w)), int(min(W, f.cx + 0.8 * f.w))
    cols = (np.abs(gray[band_y0:band_y1, 4:] - gray[band_y0:band_y1, :-4]) > SEAM_GRADIENT).mean(0)   # col i: step between i and i+4
    rows = (np.abs(gray[4:, band_x0:band_x1] - gray[:-4, band_x0:band_x1]) > SEAM_GRADIENT).mean(1)
    seam_x = [i + 2 for i in np.nonzero(cols >= SEAM_COVERAGE)[0]]
    seam_y = [i + 2 for i in np.nonzero(rows >= SEAM_COVERAGE)[0]]
    left = max((x for x in seam_x if x <= f.x), default=0)
    right = min((x for x in seam_x if x >= f.x + f.w), default=W)
    top = max((y for y in seam_y if y <= f.y), default=0)
    bottom = min((y for y in seam_y if y >= f.y + f.h), default=H)
    return float(left), float(top), float(right), float(bottom)


@dataclass
class Sample:
    t: float                 # source time
    face: Face | None        # the speaker's face in that frame (None: not found)


@dataclass
class SpeakerTrack:
    """The speaker's face over one segment's source range, sampled at `fps` (denser around layout changes)."""

    start: float
    duration: float
    fps: float
    samples: list[Sample]

    def to_json(self) -> dict:
        return {"start": self.start, "duration": self.duration, "fps": self.fps,
                "samples": [{"t": round(s.t, 4), "face": None if s.face is None else s.face.to_json()} for s in self.samples]}


def _face_from_json(d: dict) -> Face:
    x, y, w, h = d["box"]
    ey = d["eye_y"]
    return Face(d["t"], x, y, w, h, d["score"], (0, ey, 0, ey, 0, 0, 0, 0, 0, 0), (),
                None if d["bounds"] is None else tuple(d["bounds"]))


def track_from_json(blob: dict) -> SpeakerTrack:
    return SpeakerTrack(blob["start"], blob["duration"], blob["fps"],
                        [Sample(s["t"], None if s["face"] is None else _face_from_json(s["face"])) for s in blob["samples"]])


def _pick_face(frame: np.ndarray, t: float, gallery: dict[str, np.ndarray] | None, speaker: str) -> Face | None:
    """The speaker's face in one frame, or None. `gallery=None` = isolated camera: the largest face."""
    faces = detect(frame, t)
    if not faces:
        return None
    if gallery is None:
        return max(faces, key=lambda f: f.w * f.h)
    sims = [(float(gallery[speaker] @ embed(frame, f)), f) for f in faces]
    sim, pick = max(sims, key=lambda p: p[0])
    emb = embed(frame, pick)
    if sim < SAME_PERSON_COSINE * 0.6 or any(float(v @ emb) > sim for s, v in gallery.items() if s != speaker):
        return None
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
    return Face(pick.t, pick.x, pick.y, pick.w, pick.h, pick.score, pick.lm, pick.row, _seam_bounds(gray, pick))


def _jumped(a: Face, b: Face) -> bool:
    """The face moved too far between two samples to be the same shot (a layout change, not head movement)."""
    return float(np.hypot(a.cx - b.cx, a.cy - b.cy)) > 0.6 * (a.w + b.w) / 2


REFINE_FPS = 30.0


def locate_speaker(video: Path, dims: tuple[int, int], start: float, duration: float, fps: float,
                   gallery: dict[str, np.ndarray] | None, speaker: str) -> SpeakerTrack:
    """Sample the segment, then re-sample every layout change at the video's frame rate so a cut lands on the right frame."""
    samples = [Sample(t, _pick_face(frame, t, gallery, speaker)) for t, frame in iter_frames(video, dims, start, duration, fps)]
    refined: list[Sample] = []
    for a, b in zip(samples, samples[1:]):
        changed = (a.face is None) != (b.face is None) or (a.face is not None and b.face is not None and _jumped(a.face, b.face))
        if changed:
            refined += [Sample(t, _pick_face(frame, t, gallery, speaker))
                        for t, frame in iter_frames(video, dims, a.t, b.t - a.t, REFINE_FPS) if a.t + 1e-6 < t < b.t - 1e-6]
    return SpeakerTrack(start, duration, fps, sorted(samples + refined, key=lambda s: s.t))


# ---------------------------------------------------------------------------
# Shots and crop geometry
# ---------------------------------------------------------------------------

MAX_HOLE_S = 0.6             # longest stretch with no face between two different layouts
MAX_HOLE_SAME_PLACE_S = 2.5  # ... between two sightings in the same place (head turned, hand over the face)
MAX_EDGE_HOLE_S = 1.0        # ... at the start/end of a segment (layout assumed unchanged)
MIN_SHOT_S = 0.4             # shorter layout flashes are absorbed into the neighbouring shot
FACE_WIDTH_FACTOR = {"panel": 2.8}   # crop width / face width for split-screen panels (closeups use CLOSEUP_FACE_HEIGHT)
EYE_LINE = 0.33               # eye line as a fraction of crop height (upper third)
CLOSEUP_FACE_HEIGHT = 0.30    # closeup: detected face box height as a fraction of output height (head and shoulders: 25-35%)
CLOSEUP_EYE_BAND = (0.30, 0.36)   # closeup: the eye line may drift this far inside a tile before the shot goes blur-fill
MOUTH_ZONE = (0.62, 1.0)      # nose-base to chin, as fractions of the face box height: what a caption must not cover
BLUR_SCALE = 4                # the blur-fill backdrop is rendered at 1/BLUR_SCALE size, blurred, then scaled up
BLUR_SIGMA = 12.0             # gaussian sigma at that reduced size (~48px at full size, as the Remotion blur-fill treatment)
BLUR_BRIGHTNESS = 0.55        # backdrop luma multiplier: an undimmed blur competes with the sharp foreground
MIN_FACE_FRAMES = 1.6         # a crop narrower than this many face widths cuts the face
HEADROOM_FACES = 0.15        # least hair room above the detected box, in face heights (the eye line normally gives more)
SMOOTH_S = 1.0               # pan smoothing window
STATIC_TRAVEL = 0.06         # a path that moves less than this fraction of the crop width stays a static crop
KEY_EVERY_S = 0.5
FACE_INSIDE_MIN = 0.85       # fraction of a face box that must sit inside the crop ...
FRAMES_INSIDE_MIN = 0.9      # ... in this fraction of the frames


@dataclass
class Shot:
    """One continuous framing: a fixed-size crop window whose top-left follows `keys` (source time, x, y) linearly.

    `dst` is None when the crop fills the whole output frame. When set (x, y, w, h in output px) the crop is a
    blur-fill foreground: it is drawn at that rectangle, sharp, over a blurred, darkened copy of itself.
    `mouth` is the (top, bottom) output-frame y of the nose-to-chin band over the shot — what a caption must not cover.
    """

    t0: float
    t1: float
    w: int
    h: int
    keys: list[tuple[float, int, int]]
    dst: tuple[int, int, int, int] | None = None
    scale: float = 1.0          # output px per source px
    face_frac: float = 0.0      # median face box height / output height
    eye_frac: float = 0.0       # median eye line / output height
    mouth: tuple[float, float] = (0.0, 0.0)

    @property
    def static(self) -> bool:
        return len(self.keys) == 1

    @property
    def blur_fill(self) -> bool:
        return self.dst is not None

    def at(self, t: float) -> tuple[float, float]:
        ts = [k[0] for k in self.keys]
        return float(np.interp(t, ts, [k[1] for k in self.keys])), float(np.interp(t, ts, [k[2] for k in self.keys]))


def _smooth(ts: np.ndarray, vs: np.ndarray, t0: float, t1: float) -> tuple[np.ndarray, np.ndarray]:
    grid = np.arange(t0, t1 + 1e-6, 0.1)
    v = np.interp(grid, ts, vs)
    n = max(1, int(round(SMOOTH_S / 0.1)))
    padded = np.pad(v, (n // 2, n - n // 2 - 1), mode="edge")
    return grid, np.convolve(padded, np.ones(n) / n, mode="valid")


def _tile(faces: list[Face], dims: tuple[int, int]) -> tuple[int, int, int, int]:
    """The speaker's tile (left, top, right, bottom): median seam bounds across the faces, else the whole frame."""
    tiles = [f.bounds for f in faces if f.bounds is not None] or [(0.0, 0.0, float(dims[0]), float(dims[1]))]
    return (math.ceil(float(np.median([b[0] for b in tiles]))), math.ceil(float(np.median([b[1] for b in tiles]))),
            math.floor(float(np.median([b[2] for b in tiles]))), math.floor(float(np.median([b[3] for b in tiles]))))


def _path(faces: list[Face], t0: float, t1: float, w: int, h: int, tile: tuple[int, int, int, int],
          eye_line: float) -> list[tuple[float, int, int]]:
    """Smoothed top-left of a w x h window that follows the face, kept inside `tile`: one key (static) or a pan."""
    lb, tb, rb, bb = tile
    ts = np.array([f.t for f in faces])
    want_x = np.array([f.cx - w / 2 for f in faces])
    want_y = np.array([min(f.eye_y - eye_line * h, f.y - HEADROOM_FACES * f.h) for f in faces])
    grid, xs = _smooth(ts, want_x, t0, t1)
    _, ys = _smooth(ts, want_y, t0, t1)
    xs, ys = np.clip(xs, lb, rb - w), np.clip(ys, tb, bb - h)
    if np.ptp(xs) < STATIC_TRAVEL * w and np.ptp(ys) < STATIC_TRAVEL * w:
        return [(t0, int(round(float(np.median(xs)))), int(round(float(np.median(ys)))))]
    idx = sorted({0, len(grid) - 1, *range(0, len(grid), int(KEY_EVERY_S / 0.1))})
    return [(float(grid[i]), int(round(float(xs[i]))), int(round(float(ys[i])))) for i in idx]


def _finish(shot: Shot, faces: list[Face], out_h: int, tile: tuple[int, int, int, int], where: str) -> Shot:
    """Check the face stays inside the shot's visible crop, then fill in the measured geometry."""
    lb, tb, rb, bb = tile

    def covered(f: Face) -> bool:
        x, y = shot.at(f.t)
        ox = max(0.0, min(f.x + f.w, x + shot.w) - max(f.x, x))
        oy = max(0.0, min(f.y + f.h, y + shot.h) - max(f.y, y))
        return ox * oy >= FACE_INSIDE_MIN * f.w * f.h

    inside = float(np.mean([covered(f) for f in faces]))
    if inside < FRAMES_INSIDE_MIN:
        raise FaceError(
            f"{where}: a {shot.w}x{shot.h} crop holds the face in only {inside:.0%} of frames {shot.t0:.2f}-{shot.t1:.2f}s "
            f"(tile ({lb},{tb})-({rb},{bb}), face ~{np.median([f.w for f in faces]):.0f}px) — the speaker moves too much for their tile"
        )

    dx, dy = (0, 0) if shot.dst is None else shot.dst[:2]
    def out_y(f: Face, src_y: float) -> float:
        return dy + (src_y - shot.at(f.t)[1]) * shot.scale

    shot.face_frac = float(np.median([f.h for f in faces])) * shot.scale / out_h
    shot.eye_frac = float(np.median([out_y(f, f.eye_y) for f in faces])) / out_h
    shot.mouth = (min(out_y(f, f.y + MOUTH_ZONE[0] * f.h) for f in faces), max(out_y(f, f.y + MOUTH_ZONE[1] * f.h) for f in faces))
    return shot


def _panel_geometry(faces: list[Face], t0: float, t1: float, dims: tuple[int, int], out_w: int, out_h: int, where: str) -> Shot:
    """A split-screen panel: crop width = FACE_WIDTH_FACTOR x the face, eyes on the upper third, inside the tile."""
    g = math.gcd(out_w, out_h)
    p, q = out_w // g, out_h // g
    step = 1 if p % 2 == 0 and q % 2 == 0 else 2          # keeps both crop sides even
    aspect = out_w / out_h
    fw = float(np.median([f.w for f in faces]))
    tile = _tile(faces, dims)
    lb, tb, rb, bb = tile
    # the eyes sit on EYE_LINE of the crop, so the crop is made only as tall as the room below the lowest eyes allows
    # (otherwise the tile edge clamps the window upward and the eyes drift out of the upper third) — but never so
    # tight that it cuts the face: a narrow crop in a tile whose face sits low settles for eyes a little lower
    eye_low = float(np.percentile([f.eye_y for f in faces], 95))
    room = (bb - eye_low) / (1.0 - EYE_LINE) * aspect
    cw = min(FACE_WIDTH_FACTOR["panel"] * fw, rb - lb, (bb - tb) * aspect, max(room, MIN_FACE_FRAMES * fw))
    k = int(cw // (p * step)) * step
    if k < step:
        raise FaceError(f"{where}: the speaker's tile ({lb},{tb})-({rb},{bb}) is too small for a {out_w}x{out_h} crop")
    w, h = p * k, q * k
    shot = Shot(t0, t1, w, h, _path(faces, t0, t1, w, h, tile, EYE_LINE), scale=out_w / w)
    return _finish(shot, faces, out_h, tile, where)


def _closeup_geometry(faces: list[Face], t0: float, t1: float, dims: tuple[int, int], out_w: int, out_h: int,
                      max_upscale: float, where: str) -> Shot:
    """Head and shoulders: face box ~CLOSEUP_FACE_HEIGHT of the frame, eye line in CLOSEUP_EYE_BAND, never upscaled past
    `max_upscale`. When the speaker's tile cannot supply a full 9:16 window at that scale the crop is placed as a sharp
    foreground over a blurred, darkened copy of itself (`Shot.dst`) rather than zoomed in until it blurs."""
    g = math.gcd(out_w, out_h)
    p, q = out_w // g, out_h // g
    step = 1 if p % 2 == 0 and q % 2 == 0 else 2
    tile = _tile(faces, dims)
    lb, tb, rb, bb = tile
    face_h = float(np.median([f.h for f in faces]))
    scale = min(CLOSEUP_FACE_HEIGHT * out_h / face_h, max_upscale)
    k = math.ceil(out_w / scale / (p * step)) * step      # ceil: the realised upscale never exceeds `scale`
    w, h = p * k, q * k
    scale = out_w / w

    if w <= rb - lb and h <= bb - tb:
        keys = _path(faces, t0, t1, w, h, tile, (CLOSEUP_EYE_BAND[0] + CLOSEUP_EYE_BAND[1]) / 2)
        shot = Shot(t0, t1, w, h, keys, scale=scale)
        eye = float(np.median([(f.eye_y - shot.at(f.t)[1]) * scale / out_h for f in faces]))
        if CLOSEUP_EYE_BAND[0] - 1e-3 <= eye <= CLOSEUP_EYE_BAND[1] + 1e-3:
            return _finish(shot, faces, out_h, tile, where)

    # blur-fill: the 9:16 window the framing wants, intersected with the tile, drawn at its true scale; static
    wx = float(np.median([f.cx - w / 2 for f in faces]))
    wy = float(np.median([f.eye_y for f in faces])) - (CLOSEUP_EYE_BAND[0] + CLOSEUP_EYE_BAND[1]) / 2 * h
    x0, y0 = math.ceil(max(wx, lb)), math.ceil(max(wy, tb))
    x1, y1 = math.floor(min(wx + w, rb)), math.floor(min(wy + h, bb))
    fw, fh = (x1 - x0) // 2 * 2, (y1 - y0) // 2 * 2
    if fw < 2 or fh < 2:
        raise FaceError(f"{where}: the speaker's tile ({lb},{tb})-({rb},{bb}) does not overlap the framing window")
    ow, oh = min(out_w, round(fw * scale / 2) * 2), min(out_h, round(fh * scale / 2) * 2)
    dx, dy = round((x0 - wx) * scale), round((y0 - wy) * scale)
    # vertically centred, so the blurred backdrop shows equally above and below the sharp crop
    dx, dy = max(0, min(dx, out_w - ow)), (out_h - oh) // 4 * 2
    face_top = float(np.median([f.y for f in faces]))
    if tb > face_top - 0.1 * face_h:
        logger.warning(f"{where}: the speaker's tile starts at y={tb} but the face box at y={face_top:.0f} "
                       f"({face_h:.0f}px tall) — the source tile itself cuts the top of the head")
    shot = Shot(t0, t1, fw, fh, [(t0, x0, y0)], dst=(dx, dy, ow, oh), scale=scale)
    return _finish(shot, faces, out_h, tile, where)


def _shot_geometry(faces: list[Face], t0: float, t1: float, dims: tuple[int, int], out_w: int, out_h: int,
                   kind: str, max_upscale: float, where: str) -> Shot:
    if kind == "panel":
        return _panel_geometry(faces, t0, t1, dims, out_w, out_h, where)
    if kind == "closeup":
        return _closeup_geometry(faces, t0, t1, dims, out_w, out_h, max_upscale, where)
    raise ValueError(f"{where}: unknown shot kind {kind!r}")


def plan_shots(track: SpeakerTrack, dims: tuple[int, int], out_w: int, out_h: int, kind: str, max_upscale: float, where: str) -> list[Shot]:
    """Split a track at layout changes and frame each shot; fail (naming the range) wherever the face is missing."""
    end = track.start + track.duration
    found = [s for s in track.samples if s.face is not None]
    if not found:
        raise FaceError(f"{where}: the speaker's face is not in the frame at any point of {track.start:.2f}-{end:.2f}s")
    dt = 1.0 / track.fps
    if found[0].t - track.start > MAX_EDGE_HOLE_S:
        raise FaceError(f"{where}: no face for the speaker during {track.start:.2f}-{found[0].t:.2f}s")
    if end - found[-1].t > MAX_EDGE_HOLE_S + dt:
        raise FaceError(f"{where}: no face for the speaker during {found[-1].t:.2f}-{end:.2f}s")
    for a, b in zip(found, found[1:]):
        hole = b.t - a.t - dt
        # a turned head or a hand across the face leaves the detector blind while the speaker is still there
        # (same place on both sides); a hole between two DIFFERENT places is a layout change and must be short
        limit = MAX_HOLE_SAME_PLACE_S if not _jumped(a.face, b.face) else MAX_HOLE_S
        if hole > limit:
            raise FaceError(f"{where}: no face for the speaker during {a.t:.2f}-{b.t:.2f}s")

    runs: list[list[Face]] = [[found[0].face]]
    for a, b in zip(found, found[1:]):
        if _jumped(a.face, b.face):
            runs.append([])
        runs[-1].append(b.face)
    bounds = [track.start] + [(r0[-1].t + r1[0].t) / 2 for r0, r1 in zip(runs, runs[1:])] + [end]
    spans = list(zip(bounds, bounds[1:]))
    # absorb flashes shorter than MIN_SHOT_S into a neighbour (their faces are not used for framing)
    while len(runs) > 1 and (short := [i for i, (a, b) in enumerate(spans) if b - a < MIN_SHOT_S]):
        i = short[0]
        j = i - 1 if i > 0 else 1
        lo, hi = min(i, j), max(i, j)
        spans[lo:hi + 1] = [(spans[lo][0], spans[hi][1])]
        runs[lo:hi + 1] = [runs[j]]
    return [_shot_geometry(r, a, b, dims, out_w, out_h, kind, max_upscale, f"{where} {a:.2f}-{b:.2f}s") for r, (a, b) in zip(runs, spans)]
