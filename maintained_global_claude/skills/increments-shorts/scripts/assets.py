"""Cached downloadable assets: Anton font (OFL) and the Increments end tag. Cross-platform cache dir
via platformdirs (macOS ~/Library/Caches, Linux ~/.cache, Windows %LOCALAPPDATA%). Fails loud on bad downloads."""

from __future__ import annotations

from pathlib import Path

import httpx
from platformdirs import user_cache_dir

APP = "increments-shorts"
ANTON_URL = "https://github.com/google/fonts/raw/main/ofl/anton/Anton-Regular.ttf"
ANTON_MIN_BYTES = 30_000
ENDTAG_URL = "https://drive.usercontent.google.com/download?id=1Ch1zdxdXnbFjWkdpViDvCyHXn1dC49Fd&export=download"
ENDTAG_BYTES = 13_736_348
ENDTAG_SHARED_FOLDER = "https://drive.google.com/drive/folders/1Ik7EnTVXMMVH06qzJDWCDPvecm7FkNsI"


def cache_dir() -> Path:
    d = Path(user_cache_dir(APP))
    d.mkdir(parents=True, exist_ok=True)
    return d


def download(url: str, dest: Path, expect_bytes: int | None, min_bytes: int = 1) -> Path:
    """Download to dest (atomic), verify size. Existing correct file is reused."""
    ok = lambda p: p.is_file() and (p.stat().st_size == expect_bytes if expect_bytes else p.stat().st_size >= min_bytes)  # noqa: E731
    if ok(dest):
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=120.0) as r:
        if r.status_code != 200:
            raise RuntimeError(f"download of {url} failed: HTTP {r.status_code}")
        with tmp.open("wb") as fh:
            for chunk in r.iter_bytes():
                fh.write(chunk)
    tmp.replace(dest)
    if not ok(dest):
        size = dest.stat().st_size
        dest.unlink()
        raise RuntimeError(f"{url} downloaded {size} bytes; expected {expect_bytes or '>=' + str(min_bytes)} — "
                           "the file may have moved. Check the shared folder: " + ENDTAG_SHARED_FOLDER)
    return dest


def anton_font() -> Path:
    return download(ANTON_URL, cache_dir() / "Anton-Regular.ttf", None, ANTON_MIN_BYTES)


def end_tag() -> Path:
    """increments-end-tag.mov — ProRes 4444 + alpha, 1080x1920, 30 fps, 2.333 s, AAC stereo."""
    return download(ENDTAG_URL, cache_dir() / "increments-end-tag.mov", ENDTAG_BYTES)
