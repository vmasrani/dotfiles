#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "httpx>=0.27",
#   "typer>=0.12",
#   "loguru>=0.7",
#   "rich>=13.7",
#   "pydantic>=2.9",
#   "pyyaml>=6.0",
# ]
# ///
"""Word timings for an insert segment's source file (horizontal clips).

An insert (schemas.md § Insert segments) plays a non-episode source's own audio, so its words
are not in the episode transcript. This transcribes the insert file with AssemblyAI (needs
`ASSEMBLYAI_API_KEY`; there is no fallback engine) and writes
`broll/<file stem>.words.json` = `{"words": [{w, start, end}]}` in the FILE's own time, which
`insert.words` in clip.yaml points at. Captions for a third party's speech must still be checked
by ear before delivery — auto-transcripts mishear ("unambiguous" → "an ambiguous").
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parent))

import httpx
import typer
from rich.console import Console

from psmedia import run_ffmpeg

console = Console()
app = typer.Typer(add_completion=False)
BASE = "https://api.assemblyai.com/v2"


def assemblyai_words(audio: Path, language: str) -> list[dict]:
    key = os.environ.get("ASSEMBLYAI_API_KEY")
    if not key:
        raise RuntimeError("ASSEMBLYAI_API_KEY is not set — export it and re-run")
    headers = {"authorization": key}
    with httpx.Client(timeout=httpx.Timeout(600.0)) as client:
        up = client.post(f"{BASE}/upload", headers=headers, content=audio.read_bytes())
        up.raise_for_status()
        created = client.post(f"{BASE}/transcript", headers=headers, json={
            "audio_url": up.json()["upload_url"], "language_code": language, "punctuate": True, "format_text": True})
        created.raise_for_status()
        tid = created.json()["id"]
        while True:
            body = client.get(f"{BASE}/transcript/{tid}", headers=headers).raise_for_status().json()
            if body["status"] == "completed":
                break
            if body["status"] == "error":
                raise RuntimeError(f"assemblyai transcript {tid} failed: {body.get('error')}")
            time.sleep(3)
    if not body["words"]:
        raise RuntimeError(f"assemblyai returned no words for {audio} — is the audio track silent?")
    return [{"w": w["text"], "start": w["start"] / 1000.0, "end": w["end"] / 1000.0} for w in body["words"]]


@app.command()
def main(
    media: Path = typer.Argument(..., help="The insert's source file (inside CLIP_DIR/broll/)"),
    language: str = typer.Option("en", "--language"),
) -> None:
    media = media.resolve()
    if not media.is_file():
        raise typer.BadParameter(f"no such file: {media}")
    out = media.with_suffix(".words.json")
    with TemporaryDirectory(prefix="ps-insert-") as tmp:
        wav = Path(tmp) / "insert.wav"
        run_ffmpeg(["-i", str(media), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav)],
                   what=f"extracting {media.name} audio")
        words = assemblyai_words(wav, language)
    out.write_text(json.dumps({"engine": "assemblyai", "file": media.name, "words": words}, indent=1) + "\n")
    for w in words:
        console.print(f"{w['start']:7.3f} {w['end']:7.3f} {w['w']}")
    console.print(f"[bold green]OK[/] {len(words)} words -> {out}")


if __name__ == "__main__":
    app()
