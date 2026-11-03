#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "platformdirs>=4"]
# ///
"""Stamp speaker ids onto a transcript that has none (faster-whisper engine has no diarizer).

  assign_speakers.py EPISODE_DIR turns.json

turns.json: {"turns": [{"start": 0.0, "end": 41.2, "speaker": "host1"}, ...]} — time spans, built in chat
from sample lines the user confirmed (who speaks where). Every word must fall in exactly one turn
(by midpoint) and every speaker must exist in episode.yaml; otherwise it fails and names the gaps.
Rewrites transcript.json and transcript.md (segments rebuilt, split at speaker changes).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
import yaml

app = typer.Typer(add_completion=False)
GAP_S, MAX_SEG_S = 0.8, 25.0


def stamp(words: list[dict], turns: list[dict], known: set[str]) -> list[dict]:
    bad = sorted({t["speaker"] for t in turns} - known)
    if bad:
        raise ValueError(f"turns name speakers {bad} not in episode.yaml speakers {sorted(known)}")
    out, missing = [], []
    for i, w in enumerate(words):
        mid = (w["start"] + w["end"]) / 2
        hit = [t["speaker"] for t in turns if t["start"] <= mid < t["end"]]
        if len(hit) != 1:
            missing.append((i, w["w"], round(w["start"], 1), len(hit)))
            continue
        out.append({**w, "speaker": hit[0]})
    if missing:
        raise ValueError(f"{len(missing)} word(s) fall in 0 or >1 turns (index, word, start, matches): {missing[:8]}")
    return out


def segments(words: list[dict]) -> list[dict]:
    segs: list[dict] = []
    for w in words:
        s = segs[-1] if segs else None
        if s and s["speaker"] == w["speaker"] and w["start"] - s["end"] <= GAP_S and w["end"] - s["start"] <= MAX_SEG_S:
            s["end"], s["text"] = w["end"], s["text"] + " " + w["w"]
        else:
            segs.append({"start": w["start"], "end": w["end"], "speaker": w["speaker"], "text": w["w"]})
    return segs


@app.command()
def main(episode_dir: Path = typer.Argument(...), turns_json: Path = typer.Argument(...)) -> None:
    root = episode_dir.expanduser().resolve()
    ep = yaml.safe_load((root / "episode.yaml").read_text())
    tpath = root / ep["transcript"]["json"]
    tr = json.loads(tpath.read_text())
    tr["words"] = stamp(tr["words"], json.loads(turns_json.read_text())["turns"], {s["id"] for s in ep["speakers"]})
    tr["segments"] = segments(tr["words"])
    tpath.write_text(json.dumps(tr, ensure_ascii=False))
    md = root / ep["transcript"]["md"]
    mm = lambda s: f"{int(s) // 60}:{int(s) % 60:02d}"  # noqa: E731
    md.write_text("\n".join(f"[{mm(s['start'])}] {s['speaker']}: {s['text']}" for s in tr["segments"]) + "\n")
    print(f"{len(tr['words'])} words, {len(tr['segments'])} segments stamped")


if __name__ == "__main__":
    app()
