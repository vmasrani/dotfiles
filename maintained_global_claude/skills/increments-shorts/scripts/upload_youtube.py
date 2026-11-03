#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client>=2.120", "google-auth-oauthlib>=1.2", "google-auth-httplib2>=0.2", "typer>=0.12", "loguru>=0.7", "platformdirs>=4", "rich>=13.7"]
# ///
"""Optional final step: upload a finished video to YOUR YouTube channel as a PRIVATE video.

  upload_youtube.py auth                      # one-time browser consent (needs client_secret.json; see references/youtube-setup.md)
  upload_youtube.py upload deliverables/<slug>.mp4 --meta deliverables/<slug>.txt [--thumbnail deliverables/<slug>-thumbnail.jpg]
  upload_youtube.py delete VIDEO_ID           # asks you to type the id back

Privacy is ALWAYS private — publishing is done by a human in YouTube Studio. YouTube cannot replace a video's
file: to fix a video, upload a new one, then `delete` the old one.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import typer
from loguru import logger
from platformdirs import user_config_dir

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
CONFIG = Path(user_config_dir("increments-shorts"))
CLIENT_SECRET = CONFIG / "client_secret.json"
TOKEN = CONFIG / "token.json"
CATEGORY_PEOPLE_AND_BLOGS = "22"
app = typer.Typer(add_completion=False, no_args_is_help=True)


def parse_meta(text: str) -> dict:
    """Parse the deliverables <slug>.txt (TITLE / DESCRIPTION / TAGS sections)."""
    m = re.fullmatch(r"TITLE:\n(.+?)\n\nDESCRIPTION:\n(.+?)\n\nTAGS:\n(.+?)\s*", text, re.S)
    if not m:
        raise ValueError("metadata file must have TITLE:, DESCRIPTION:, TAGS: sections (as written by deliver.py)")
    title, desc, tags = m.groups()
    return {"title": title.strip(), "description": desc.strip(), "tags": [t.strip() for t in tags.split(",") if t.strip()]}


def build_body(meta: dict, language: str = "en") -> dict:
    return {
        "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"], "categoryId": CATEGORY_PEOPLE_AND_BLOGS,
                    "defaultLanguage": language, "defaultAudioLanguage": language},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }


def credentials():
    from google.auth.transport.requests import Request  # noqa: PLC0415
    from google.oauth2.credentials import Credentials  # noqa: PLC0415

    if not TOKEN.is_file():
        raise RuntimeError(f"not authorised yet — run `upload_youtube.py auth` first (setup: references/youtube-setup.md). Expected token at {TOKEN}")
    creds = Credentials.from_authorized_user_file(str(TOKEN), SCOPES)
    if not creds.valid:
        if not (creds.expired and creds.refresh_token):
            raise RuntimeError("stored token is invalid and cannot refresh — run `upload_youtube.py auth` again")
        creds.refresh(Request())
        TOKEN.write_text(creds.to_json())
    return creds


def service():
    from googleapiclient.discovery import build  # noqa: PLC0415
    return build("youtube", "v3", credentials=credentials())


@app.command()
def auth() -> None:
    """One-time OAuth consent in the browser; caches the token in the per-user config dir."""
    from google_auth_oauthlib.flow import InstalledAppFlow  # noqa: PLC0415

    if not CLIENT_SECRET.is_file():
        raise RuntimeError(f"{CLIENT_SECRET} missing. Create an OAuth 'Desktop app' client and save its JSON there — see references/youtube-setup.md")
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN.write_text(creds.to_json())
    print(f"token saved to {TOKEN}")


@app.command()
def upload(video: Path = typer.Argument(...), meta: Path = typer.Option(..., "--meta"), thumbnail: Path = typer.Option(None, "--thumbnail"),
           language: str = typer.Option("en", "--language", help="snippet.defaultLanguage and defaultAudioLanguage")) -> None:
    """Upload VIDEO as a private video with the title/description/tags from --meta."""
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    if not video.is_file():
        raise FileNotFoundError(video)
    body = build_body(parse_meta(meta.read_text()), language)
    yt = service()
    req = yt.videos().insert(part="snippet,status", body=body, media_body=MediaFileUpload(str(video), chunksize=8 * 1024 * 1024, resumable=True))
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            logger.info(f"uploaded {int(status.progress() * 100)}%")
    vid = resp["id"]
    if thumbnail:
        yt.thumbnails().set(videoId=vid, media_body=MediaFileUpload(str(thumbnail))).execute()
    print(f"https://studio.youtube.com/video/{vid}/edit   (private — publish it yourself; set 'Related video' to the full episode)")


@app.command()
def delete(video_id: str = typer.Argument(...)) -> None:
    """Delete a video — only after you type its id back."""
    typed = typer.prompt(f"Type the video id {video_id} to confirm PERMANENT deletion")
    if typed.strip() != video_id:
        raise typer.Exit("ids do not match; nothing deleted")
    service().videos().delete(id=video_id).execute()
    print(f"deleted {video_id}")


if __name__ == "__main__":
    app()
