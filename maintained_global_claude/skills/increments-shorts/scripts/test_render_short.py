#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["static-ffmpeg>=2.7", "platformdirs>=4", "pytest>=8", "pydantic>=2.9", "pyyaml>=6.0", "typer>=0.12", "loguru>=0.7", "rich>=13.7", "pysubs2>=1.7"]
# ///
"""Pure parts of render_short.py + ffmpeg resolution — run: `uv run --script scripts/test_render_short.py`."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest

from psmedia import ffmpeg_tool, loudnorm_pass2_filter, parse_loudnorm_json
from render_short import encode_args, missing_prep, record_version, remotion_cmd
from qc_render import record_qc
from test_intro_overlays import clip, seg


def test_remotion_cmd_is_an_argv_with_the_required_flags():
    argv = remotion_cmd(3)
    assert argv[1:5] == ["remotion", "render", "Short", "../renders/v3-master.mp4"]
    for flag in ("--props=props.json", "--timeout=1800000", "--offthreadvideo-cache-size-in-bytes=209715200", "--concurrency=3"):
        assert flag in argv


def test_encode_args_match_the_owner_approved_settings():
    a = encode_args(Path("m.mp4"), Path("a.wav"), Path("o.mp4"), "loudnorm=X", 30.0, 41.7)
    joined = " ".join(a)
    assert "-vf scale=out_range=tv:out_color_matrix=bt709,format=yuv420p -color_range tv -colorspace bt709 -r 30" in joined
    assert "-c:v libx264 -preset slow -crf 18 -movflags +faststart" in joined
    assert "-c:a aac -b:a 192k -ar 48000 -t 41.700000 o.mp4" in joined
    assert a[a.index("-af") + 1] == "loudnorm=X" and a[:6] == ["-i", "m.mp4", "-i", "a.wav", "-map", "0:v"]


def test_loudnorm_pass2_filter_from_measurement_json():
    stderr = 'junk\n{\n "input_i" : "-20.1",\n "input_tp" : "-3.0",\n "input_lra" : "5.0",\n "input_thresh" : "-30.1",\n "target_offset" : "0.2"\n}\n'
    f = loudnorm_pass2_filter(parse_loudnorm_json(stderr), -14.0, -2.5)
    assert f == ("loudnorm=I=-14.0:TP=-2.5:LRA=11:measured_I=-20.1:measured_TP=-3.0:measured_LRA=5.0"
                 ":measured_thresh=-30.1:offset=0.2:linear=true")


def test_missing_prep_lists_every_absent_file_and_stale_props(tmp_path):
    assert len(missing_prep(tmp_path, 2)) == 3
    for rel in ("renders/v2-audio.wav", "subtitles/v2.ass"):
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / rel).write_text("x")
    (tmp_path / "remotion").mkdir()
    (tmp_path / "remotion/props.json").write_text(json.dumps({"audioSrc": "renders/v1-audio.wav"}))
    assert "audioSrc" in missing_prep(tmp_path, 2)[0]
    (tmp_path / "remotion/props.json").write_text(json.dumps({"audioSrc": "renders/v2-audio.wav"}))
    assert missing_prep(tmp_path, 2) == []


def test_record_version():
    c = clip([seg("S01", 100.0, 0.0, 5.0, "host1")])
    now = datetime(2026, 11, 2, 12, 30, 5, tzinfo=timezone.utc)
    e = record_version(c, 1, "youtube-shorts", now)
    assert (e.rendered_at, e.finals, e.preview) == (
        "2026-11-02T12:30:05Z", {"youtube-shorts": "renders/v1-youtube-shorts.mp4"}, "renders/v1-master.mp4")
    assert c.clip.status == "rendered"
    with pytest.raises(ValueError, match="next version is v2"):
        record_version(c, 3, "youtube-shorts", now)


def test_record_qc_points_at_the_report_and_promotes_only_on_green(tmp_path):
    c = clip([seg("S01", 100.0, 0.0, 5.0, "host1")])
    record_version(c, 1, "youtube-shorts", datetime(2026, 11, 2, tzinfo=timezone.utc))
    record_qc(c, tmp_path / "clip.yaml", 1, passed=False)
    assert c.render.versions[0].qc == "qc-v1.json" and c.clip.status == "rendered"
    record_qc(c, tmp_path / "clip.yaml", 1, passed=True)
    assert c.clip.status == "qc_passed" and (tmp_path / "clip.yaml").is_file()


def test_ffmpeg_tool_rejects_unknown_tool():
    from mediatools import MediaToolError
    with pytest.raises(MediaToolError, match="unknown tool"):
        ffmpeg_tool("ffplay")


def test_ffmpeg_missing_feature_fails_loud(monkeypatch):
    import mediatools
    monkeypatch.setattr(mediatools, "_feature_lines", lambda b, f: ["V..... h264_videotoolbox"] if f == "-encoders" else [])
    with pytest.raises(mediatools.MediaToolError, match="lacks required features"):
        mediatools.check_features("fake")


def test_bundled_ffmpeg_has_drawtext_libass_x264():
    import subprocess
    out = subprocess.run([ffmpeg_tool("ffmpeg"), "-hide_banner", "-filters"], capture_output=True, text=True).stdout
    assert "drawtext" in out and "subtitles" in out


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", *sys.argv[1:]]))
