"""Where each speaker's face is, per segment — the shared front end of plan_framing.py and frame_segments.py.

Not executable. `Framer` resolves which video (the speaker's own synced camera, or the segment's shared
frame) holds a speaker's face for a timeline segment, samples it with `facelib`, caches the detections under
`clips/<slug>/assets/faces/`, and turns them into crop `Shot`s. Galleries (shared-frame identities) live at
`<episode root>/faces/`. Both consumers hit the same cache keys, so detection runs once per (segment, speaker).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import facelib
from pslib import EPSILON, Episode, Speaker, SyncEntry, TimelineSegment, fmt_range, load_transcript
from psmedia import media_path, probe_dims, probed_duration

FACE_SAMPLE_FPS = (6.0, 8.0)     # (steady rate, ceiling for very short segments)
FACE_MIN_SAMPLES = 6
FACE_CACHE_VERSION = 5   # 5: tile bounds at SEAM_COVERAGE 0.5 with seam slack, refused when they hold another person


def speaker_by_id(episode: Episode, sid: str, where: str) -> Speaker:
    match = [s for s in episode.speakers if s.id == sid]
    if not match:
        raise ValueError(f"{where}: speaker {sid!r} is not in episode.yaml speakers ({sorted(episode.speaker_ids())})")
    return match[0]


def sync_for(episode: Episode, camera_file: str) -> SyncEntry | None:
    match = [s for s in episode.sync if s.file == camera_file]
    if len(match) > 1:
        raise ValueError(f"episode.yaml has {len(match)} sync entries for {camera_file}")
    return match[0] if match else None


def camera_range(sync: SyncEntry, seg: TimelineSegment) -> tuple[float, float]:
    """Episode-time range → camera-time range. Camera t0 occurs `offset_s` after episode t0."""
    return seg.source_in - sync.offset_s, seg.source_out - sync.offset_s


def resolve_source(seg: TimelineSegment, episode: Episode, sid: str | None) -> tuple[str, float, float, str, list[str], bool]:
    """(source_rel, source_in, source_out, origin, refusals, isolated) for one speaker's frames in a segment.

    `isolated` is True when the frames come from the speaker's own camera file.
    """
    if sid is None:
        return seg.source_file, seg.source_in, seg.source_out, "segment source_file", [], False

    speaker = speaker_by_id(episode, sid, seg.id)
    if speaker.camera_file is None:
        return seg.source_file, seg.source_in, seg.source_out, f"segment source_file (shared frame, {sid} has no camera)", [], False

    sync = sync_for(episode, speaker.camera_file)
    if sync is None:
        return "", 0.0, 0.0, "", [
            f"{seg.id}: speaker {sid} has camera_file {speaker.camera_file} but episode.yaml has no sync "
            f"entry for it — run scripts/sync_cameras.py and verify it before rendering"
        ], True
    if not sync.verified:
        return "", 0.0, 0.0, "", [
            f"{seg.id}: sync for {sync.file} is not verified (confidence {sync.confidence:.2f}, "
            f"method {sync.method}) — verify it (`sync_cameras.py verify`, then set verified: true) "
            f"or change {seg.id}'s treatment away from {seg.visual.treatment}"
        ], True

    cam_in, cam_out = camera_range(sync, seg)
    refusals = []
    if cam_in < -EPSILON:
        refusals.append(
            f"{seg.id}: source range {fmt_range(seg.source_in, seg.source_out)} maps to camera time "
            f"{cam_in:.3f}s in {sync.file} at offset {sync.offset_s:+.3f}s — before the camera started rolling"
        )
    cam_duration = probed_duration(episode, sync.file)
    if cam_out > cam_duration + EPSILON:
        refusals.append(
            f"{seg.id}: maps to camera time {cam_out:.3f}s in {sync.file}, past its probed "
            f"duration {cam_duration:.3f}s"
        )
    for gap in sync.gaps:
        if cam_in < gap.camera_s + gap.duration_s and cam_out > gap.camera_s:
            refusals.append(
                f"{seg.id}: camera range {cam_in:.3f}-{cam_out:.3f}s crosses a recorded discontinuity in "
                f"{sync.file} at {gap.camera_s:.3f}s (+{gap.duration_s:.3f}s) — the sync offset is not valid there"
            )
    origin = f"{sync.file} @ offset {sync.offset_s:+.3f}s"
    return sync.file, cam_in, cam_out, origin, refusals, True



# ---------------------------------------------------------------------------
# Framer
# ---------------------------------------------------------------------------


class Framer:
    """Face tracks and crop shots for one clip."""

    def __init__(self, clip_dir: Path, root: Path, episode: Episode) -> None:
        self.clip_dir, self.root, self.episode = clip_dir, root, episode
        self.faces_dir = clip_dir / "assets" / "faces"
        self.transcript = load_transcript(root / episode.transcript.json_file)
        self.galleries: dict[str, dict] = {}

    def gallery(self, source_rel: str) -> dict:
        if source_rel not in self.galleries:
            shared = [s.id for s in self.episode.speakers if s.camera_file is None]
            self.galleries[source_rel] = facelib.speaker_gallery(
                self.root / "faces" / f"gallery-{Path(source_rel).stem}.json", media_path(self.root, source_rel), source_rel,
                probe_dims(self.episode, source_rel), self.transcript, shared)
        return self.galleries[source_rel]

    def track(self, seg: TimelineSegment, sid: str, source: tuple) -> facelib.SpeakerTrack:
        """`source` is `resolve_source(...)` (already checked for refusals)."""
        source_rel, src_in, src_out, _origin, _refusals, isolated = source
        dur = src_out - src_in
        fps = min(FACE_SAMPLE_FPS[1], max(FACE_SAMPLE_FPS[0], FACE_MIN_SAMPLES / dur))
        gallery = None if isolated else self.gallery(source_rel)
        ident = "isolated" if gallery is None else hashlib.sha256(gallery[sid].tobytes()).hexdigest()[:16]
        key = hashlib.sha256(json.dumps([FACE_CACHE_VERSION, source_rel, round(src_in, 3), round(src_out, 3), fps, sid, ident,
                                         facelib.MODELS["yunet"][2], facelib.MODELS["sface"][2]]).encode()).hexdigest()
        cache = self.faces_dir / f"{seg.id}-{sid}.json"
        if cache.is_file():
            blob = json.loads(cache.read_text())
            if blob["key"] == key:
                return facelib.track_from_json(blob["track"])
        track = facelib.locate_speaker(media_path(self.root, source_rel), probe_dims(self.episode, source_rel), src_in, dur, fps,
                                       gallery, sid)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key, "source": source_rel, "range": [src_in, src_out], "speaker": sid,
                                     "track": track.to_json()}, indent=1))
        return track

    def shots(self, seg: TimelineSegment, sid: str, source: tuple, kind: str, out_w: int, out_h: int, max_upscale: float) -> list[facelib.Shot]:
        """Crop shots (source/camera time) for `sid` in `seg`; raises facelib.FaceError when they cannot be framed."""
        source_rel = source[0]
        return facelib.plan_shots(self.track(seg, sid, source), probe_dims(self.episode, source_rel), out_w, out_h, kind,
                                  max_upscale, f"{seg.id} ({sid})")
