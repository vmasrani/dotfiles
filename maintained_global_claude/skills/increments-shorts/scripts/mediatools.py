"""The ONE place ffmpeg/ffprobe are resolved. Cross-platform via the `static-ffmpeg` PyPI package.

Every script that shells out to ffmpeg/ffprobe calls `ffmpeg_tool("ffmpeg" | "ffprobe")`.
Fails loud when the binaries are missing or the build lacks a feature the pipeline needs
(libx264 for encoding, libass for burned captions, drawtext, loudnorm).
"""

from __future__ import annotations

import platform
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

REQUIRED_ENCODERS = ("libx264",)
REQUIRED_FILTERS = ("subtitles", "ass", "overlay", "loudnorm")


class MediaToolError(RuntimeError):
    pass


def _feature_lines(binary: str, flag: str) -> list[str]:
    proc = subprocess.run([binary, "-hide_banner", flag], capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaToolError(f"`{binary} {flag}` failed (exit {proc.returncode}): {proc.stderr.strip()[:300]}")
    return proc.stdout.splitlines()


def check_features(ffmpeg: str) -> None:
    """Raise unless the build has libx264 + the filters we use."""
    encoders = " ".join(_feature_lines(ffmpeg, "-encoders"))
    filters = {ln.split()[1] for ln in _feature_lines(ffmpeg, "-filters") if len(ln.split()) > 1}
    missing = [e for e in REQUIRED_ENCODERS if e not in encoders] + [f for f in REQUIRED_FILTERS if f not in filters]
    if missing:
        raise MediaToolError(
            f"ffmpeg at {ffmpeg} lacks required features: {missing}. "
            "Run `uv pip install --upgrade static-ffmpeg` (its bundled build has libx264 + libass)."
        )


def _cache_bin_dir() -> Path:
    from platformdirs import user_cache_dir  # noqa: PLC0415
    return Path(user_cache_dir("increments-shorts")) / "ffmpeg" / f"{platform.system()}-{platform.machine()}".lower()


def _exe(name: str) -> str:
    return name + (".exe" if platform.system() == "Windows" else "")


@lru_cache(maxsize=1)
def _resolve() -> dict[str, str]:
    """Binaries live ONCE per machine in the user cache (copied from the static-ffmpeg package on first use),
    so the many per-script uv environments never each re-download ~30 MB."""
    cache = _cache_bin_dir()
    paths = {n: cache / _exe(n) for n in ("ffmpeg", "ffprobe")}
    if not all(p.is_file() for p in paths.values()):
        try:
            import static_ffmpeg  # noqa: PLC0415
        except ImportError as e:
            raise MediaToolError(
                "static-ffmpeg is not installed. Scripts declare it in their PEP 723 header; run them with "
                "`uv run <script>` (not bare python)."
            ) from e
        static_ffmpeg.add_paths()  # downloads the platform build, then puts it on PATH
        found = {n: shutil.which(n) for n in ("ffmpeg", "ffprobe")}
        absent = [n for n, p in found.items() if not p]
        if absent:
            raise MediaToolError(f"static-ffmpeg did not provide: {absent}. Re-run `uv run` with network access once.")
        check_features(found["ffmpeg"])  # type: ignore[arg-type]
        cache.mkdir(parents=True, exist_ok=True)
        for n, src in found.items():
            shutil.copy2(src, paths[n])  # type: ignore[arg-type]
    return {n: str(p) for n, p in paths.items()}


def ffmpeg_tool(name: str = "ffmpeg") -> str:
    """Absolute path of `ffmpeg` or `ffprobe`."""
    if name not in ("ffmpeg", "ffprobe"):
        raise MediaToolError(f"unknown tool {name!r}; expected ffmpeg or ffprobe")
    return _resolve()[name]
