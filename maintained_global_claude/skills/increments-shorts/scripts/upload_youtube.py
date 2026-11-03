#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["google-api-python-client>=2.120", "google-auth-oauthlib>=1.2", "google-auth-httplib2>=0.2", "typer>=0.12", "loguru>=0.7", "platformdirs>=4", "rich>=13.7"]
# ///
"""Optional final step: upload a finished video to YOUR YouTube channel as a PRIVATE video.

  upload_youtube.py auth                      # one-time browser consent (needs client_secret.json; see references/youtube-setup.md)
  upload_youtube.py upload deliverables/<slug>.mp4 --meta deliverables/<slug>.txt [--thumbnail deliverables/<slug>-thumbnail.jpg]
  upload_youtube.py upload ... --publish-at 2026-11-04T19:00:00-08:00   # schedule (stays private until then; offset REQUIRED)
  upload_youtube.py schedule VIDEO_ID --at 2026-11-04T19:00:00-08:00    # schedule an existing private video
  upload_youtube.py thumbnail VIDEO_ID FILE   # only works once processing has succeeded
  upload_youtube.py delete VIDEO_ID           # asks you to type the id back

Privacy is ALWAYS private — publishing is done by a human in YouTube Studio. YouTube cannot replace a video's
file: to fix a video, upload a new one, then `delete` the old one.
"""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
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


def parse_publish_at(value: str) -> datetime:
    """ISO 8601 with an explicit UTC offset -> aware UTC datetime in the future."""
    try:
        when = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as e:
        raise typer.BadParameter(f"not ISO 8601: {e}")
    if when.tzinfo is None:
        raise typer.BadParameter(f"{value!r} has no UTC offset; the machine's timezone is not the viewer's. Add one, e.g. 2026-11-04T19:00:00-08:00")
    when = when.astimezone(timezone.utc)
    if when <= datetime.now(timezone.utc):
        raise typer.BadParameter(f"{value!r} is not in the future")
    return when


def utc_z(when: datetime) -> str:
    return when.strftime("%Y-%m-%dT%H:%M:%SZ")


def schedule_body(video_id: str, when: datetime, status: dict) -> dict:
    return {"id": video_id, "status": {"privacyStatus": "private", "publishAt": utc_z(when),
                                       "selfDeclaredMadeForKids": status.get("madeForKids", False)}}


def require_processed(item: dict) -> None:
    state = item.get("processingDetails", {}).get("processingStatus")
    if state != "succeeded":
        raise RuntimeError(f"video is still processing (processingStatus={state!r}); YouTube replaces thumbnails set before processing succeeds. Retry in a few minutes.")


def build_body(meta: dict, language: str = "en", publish_at: datetime | None = None) -> dict:
    body = {
        "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"], "categoryId": CATEGORY_PEOPLE_AND_BLOGS,
                    "defaultLanguage": language, "defaultAudioLanguage": language},
        "status": {"privacyStatus": "private", "selfDeclaredMadeForKids": False},
    }
    if publish_at is not None:
        body["status"]["publishAt"] = utc_z(publish_at)
    return body


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
           language: str = typer.Option("en", "--language", help="snippet.defaultLanguage and defaultAudioLanguage"),
           publish_at: str = typer.Option(None, "--publish-at", help="ISO 8601 WITH UTC offset, e.g. 2026-11-04T19:00:00-08:00; stays private until then")) -> None:
    """Upload VIDEO as a private video with the title/description/tags from --meta."""
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    if not video.is_file():
        raise FileNotFoundError(video)
    when = parse_publish_at(publish_at) if publish_at else None
    body = build_body(parse_meta(meta.read_text()), language, when)
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
        print(f"WARNING: thumbnail set during processing may be replaced by YouTube — re-set it once processing finishes: upload_youtube.py thumbnail {vid} {thumbnail}")
    if when:
        print(f"scheduled for {resp['status'].get('publishAt', utc_z(when))} UTC (given: {publish_at})")
    print(f"https://studio.youtube.com/video/{vid}/edit   (private — publish it yourself; set 'Related video' to the full episode)")


@app.command()
def schedule(video_id: str = typer.Argument(...), at: str = typer.Option(..., "--at", help="ISO 8601 WITH UTC offset, e.g. 2026-11-04T19:00:00-08:00")) -> None:
    """Schedule an existing PRIVATE video to go public at --at."""
    when = parse_publish_at(at)
    yt = service()
    items = yt.videos().list(part="status", id=video_id).execute().get("items", [])
    if not items:
        raise RuntimeError(f"video {video_id} not found")
    status = items[0]["status"]
    if status["privacyStatus"] != "private":
        raise RuntimeError(f"video is {status['privacyStatus']!r}; only private videos can be scheduled")
    resp = yt.videos().update(part="status", body=schedule_body(video_id, when, status)).execute()
    print(f"publishAt (UTC): {resp['status']['publishAt']}   given: {at}")


@app.command()
def thumbnail(video_id: str = typer.Argument(...), file: Path = typer.Argument(...)) -> None:
    """Set a thumbnail — refused until the video has finished processing."""
    from googleapiclient.http import MediaFileUpload  # noqa: PLC0415

    if not file.is_file():
        raise FileNotFoundError(file)
    yt = service()
    items = yt.videos().list(part="processingDetails", id=video_id).execute().get("items", [])
    if not items:
        raise RuntimeError(f"video {video_id} not found")
    require_processed(items[0])
    yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(file))).execute()
    print(f"thumbnail set for {video_id}")


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
