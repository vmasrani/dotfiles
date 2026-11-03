#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest>=8", "platformdirs>=4", "httpx>=0.27", "typer>=0.12", "loguru>=0.7", "rich>=13.7", "rapidfuzz>=3.9", "yt-dlp[default]>=2026.8.19", "youtube-transcript-api>=1.2"]
# ///
"""Published-shorts overlap check — run: `uv run --script scripts/test_published_shorts.py -q`. No network: fakes only."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest
from typer.testing import CliRunner

import published_shorts as ps

EP_WORDS = [{"w": f"w{i}", "start": float(i), "end": i + 0.5, "speaker": "a"} for i in range(300)]


def episode() -> ps.Episode:
    return ps.Episode(EP_WORDS)


def short_doc(vid: str, tokens: list[str], status: str = ps.OK) -> dict:
    segs = [{"text": " ".join(tokens[i : i + 5]), "start": i * 0.4, "duration": 2.0} for i in range(0, len(tokens), 5)]
    return {"video_id": vid, "title": f"title {vid}", "url": f"https://www.youtube.com/shorts/{vid}",
            "status": status, "reason": None if status == ps.OK else "x", "segments": segs if status == ps.OK else None}


def span(a: int, b: int) -> list[str]:
    return [f"w{i}" for i in range(a, b)]


# ------------------------------------------------------------------ matching


def test_short_copied_from_episode_is_found_with_time_range_and_full_coverage():
    [r] = ps.match_short(episode(), short_doc("A", span(100, 140)))
    assert (r.start_word, r.end_word) == (100, 139)
    assert (r.source_start, r.source_end) == (100.0, 139.5)
    assert r.short_coverage == 1.0 and r.match_score > 0.9


def test_caption_noise_is_tolerated():
    noisy = span(100, 120) + ["uh"] + span(121, 124) + span(125, 140)  # one inserted token, one dropped
    [r] = ps.match_short(episode(), short_doc("A", noisy))
    assert r.start_word == 100 and r.end_word >= 138 and r.match_score > 0.8


def test_unrelated_short_has_no_regions():
    assert ps.match_short(episode(), short_doc("Z", [f"z{i}" for i in range(40)])) == []


def test_tiny_coincidental_overlap_is_not_a_region():
    assert ps.match_short(episode(), short_doc("A", [f"z{i}" for i in range(30)] + span(50, 54))) == []


def test_min_score_filters_regions():
    docs = [short_doc("A", span(100, 140))]
    assert len(ps.match_episode(episode(), docs, 0.6)) == 1
    assert ps.match_episode(episode(), docs, 0.999) == []


def test_shorts_without_transcripts_are_skipped_not_crashed():
    docs = [short_doc("N", [], ps.NO_TRANSCRIPT), short_doc("E", [], ps.ERROR), short_doc("A", span(10, 40))]
    assert [r.video_id for r in ps.match_episode(episode(), docs, 0.6)] == ["A"]


def test_regions_sorted_by_episode_position():
    docs = [short_doc("late", span(200, 240)), short_doc("early", span(10, 50))]
    assert [r.video_id for r in ps.match_episode(episode(), docs, 0.6)] == ["early", "late"]


# ------------------------------------------------------------------ picks


def region(a: int, b: int) -> ps.Region:
    return ps.Region("A", "t", "u", float(a), b + 0.5, a, b, 0.9, 1.0)


def test_pick_verdicts():
    pick = lambda a, b, **kw: {"id": "S1", "title": "t", "ranges": [{"start": a, "end": b}], **kw}  # noqa: E731
    assert ps.check_pick(EP_WORDS, pick(100, 140), [region(100, 139)])["verdict"] == "duplicate"
    assert ps.check_pick(EP_WORDS, pick(100, 140), [region(100, 110)])["verdict"] == "partial"
    clear = ps.check_pick(EP_WORDS, pick(100, 140), [region(200, 240)])
    assert clear["verdict"] == "clear" and clear["shorts"] == []


def test_pick_cuts_are_excluded_from_the_overlap_denominator():
    pick = {"id": "S1", "title": "t", "ranges": [{"start": 100, "end": 140}], "cuts": [{"start": 120, "end": 140}]}
    res = ps.check_pick(EP_WORDS, pick, [region(100, 119)])
    assert res["overlap_pct"] == 100.0 and res["verdict"] == "duplicate" and res["shorts"] == ["A"]


def test_pick_without_words_fails_loud():
    with pytest.raises(SystemExit, match="no transcript words"):
        ps.check_pick(EP_WORDS, {"id": "S9", "ranges": [{"start": 900, "end": 950}]}, [])


# ------------------------------------------------------------------ cache incrementality


class FakeFetcher:
    def __init__(self, plan: dict[str, dict] | None = None):
        self.calls: list[str] = []
        self.plan = plan or {}

    def __call__(self, vid: str) -> dict:
        self.calls.append(vid)
        return self.plan.get(vid, {"status": ps.OK, "segments": [{"text": f"hello {vid}", "start": 0, "duration": 1}], "reason": None})


def listing(*ids: str) -> list[dict]:
    return [{"video_id": i, "title": f"t{i}", "url": f"https://www.youtube.com/shorts/{i}"} for i in ids]


def test_only_new_ids_are_fetched(tmp_path):
    f = FakeFetcher()
    ps.sync_index(tmp_path, listing("a", "b"), f)
    assert sorted(f.calls) == ["a", "b"]
    f.calls.clear()
    summary = ps.sync_index(tmp_path, listing("a", "b", "c"), f)
    assert f.calls == ["c"] and summary["total"] == 3 and summary["fetched"] == 1


def test_second_run_with_nothing_new_fetches_nothing(tmp_path):
    f = FakeFetcher()
    ps.sync_index(tmp_path, listing("a"), f)
    f.calls.clear()
    ps.sync_index(tmp_path, listing("a"), f)
    assert f.calls == []


def test_failed_short_is_recorded_and_retried_but_absence_is_not(tmp_path):
    plan = {"bad": {"status": ps.ERROR, "segments": None, "reason": "IpBlocked: nope"},
            "off": {"status": ps.NO_TRANSCRIPT, "segments": None, "reason": "TranscriptsDisabled"}}
    f = FakeFetcher(plan)
    s1 = ps.sync_index(tmp_path, listing("ok", "bad", "off"), f)
    assert (s1[ps.OK], s1[ps.ERROR], s1[ps.NO_TRANSCRIPT]) == (1, 1, 1)
    assert ps.load_short(tmp_path, "bad")["reason"] == "IpBlocked: nope"
    f.calls.clear()
    f.plan = {}  # network is back
    s2 = ps.sync_index(tmp_path, listing("ok", "bad", "off"), f)
    assert f.calls == ["bad"] and (s2[ps.OK], s2[ps.ERROR], s2[ps.NO_TRANSCRIPT]) == (2, 0, 1)


def test_refresh_refetches_everything(tmp_path):
    f = FakeFetcher()
    ps.sync_index(tmp_path, listing("a", "b"), f)
    f.calls.clear()
    ps.sync_index(tmp_path, listing("a", "b"), f, refresh=True)
    assert sorted(f.calls) == ["a", "b"]


def test_load_docs_without_index_fails_loud(tmp_path):
    with pytest.raises(SystemExit, match="run `uv run scripts/published_shorts.py index`"):
        ps.load_docs(tmp_path)


def test_channel_cache_is_per_channel(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "cache_dir", lambda: tmp_path)
    a = ps.channel_cache("https://www.youtube.com/@One")
    b = ps.channel_cache("https://www.youtube.com/@Two")
    assert a != b and a.parent == tmp_path / "published-shorts"


def test_shorts_tab_url():
    assert ps.shorts_tab("https://www.youtube.com/@X") == "https://www.youtube.com/@X/shorts"
    assert ps.shorts_tab("https://www.youtube.com/@X/shorts/") == "https://www.youtube.com/@X/shorts"


# ------------------------------------------------------------------ transcript classification (fake API)


def test_fetch_transcript_classifies_failures(monkeypatch):
    import youtube_transcript_api as yta

    class Fake:
        outcome: Exception | list = []

        def fetch(self, vid, languages):
            if isinstance(self.outcome, Exception):
                raise self.outcome
            return self.outcome

    monkeypatch.setattr(yta, "YouTubeTranscriptApi", Fake)
    Fake.outcome = yta.TranscriptsDisabled("vid")
    assert ps.fetch_transcript("vid")["status"] == ps.NO_TRANSCRIPT
    Fake.outcome = ConnectionError("boom")
    res = ps.fetch_transcript("vid")
    assert res["status"] == ps.ERROR and "ConnectionError: boom" in res["reason"]
    Fake.outcome = []
    assert ps.fetch_transcript("vid")["status"] == ps.ERROR


# ------------------------------------------------------------------ CLI end to end


def test_match_cli_writes_overlap_json_and_flags_unchecked(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "cache_dir", lambda: tmp_path / "cache")
    root = ps.channel_cache(ps.DEFAULT_CHANNEL)
    docs = [short_doc("DUP", span(100, 140)), short_doc("BAD", [], ps.ERROR), short_doc("OFF", [], ps.NO_TRANSCRIPT)]
    for d in docs:
        (root / f"{d['video_id']}.json").write_text(json.dumps(d))
    (root / "index.json").write_text(json.dumps({"shorts": [{k: d[k] for k in ("video_id", "title", "url", "status", "reason")} for d in docs]}))
    ep_dir = tmp_path / "episode-x"
    (ep_dir / "transcript").mkdir(parents=True)
    (ep_dir / "transcript" / "transcript.json").write_text(json.dumps({"words": EP_WORDS}))
    picks = tmp_path / "picks.json"
    picks.write_text(json.dumps({"picks": [{"id": "S1", "title": "dup", "ranges": [{"start": 100, "end": 140}]},
                                           {"id": "S2", "title": "fresh", "ranges": [{"start": 200, "end": 240}]}]}))

    res = CliRunner().invoke(ps.app, ["match", str(ep_dir), "--picks", str(picks)])
    assert res.exit_code == 0, res.output
    out = json.loads((ep_dir / "published-overlap.json").read_text())
    assert [o["video_id"] for o in out["overlaps"]] == ["DUP"]
    assert {u["video_id"]: u["status"] for u in out["unchecked"]} == {"BAD": ps.ERROR, "OFF": ps.NO_TRANSCRIPT}
    assert {p["id"]: p["verdict"] for p in out["picks"]} == {"S1": "duplicate", "S2": "clear"}
    assert "could NOT be compared" in res.output


def test_match_cli_fails_when_nothing_is_checkable(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "cache_dir", lambda: tmp_path / "cache")
    root = ps.channel_cache(ps.DEFAULT_CHANNEL)
    bad = short_doc("BAD", [], ps.ERROR)
    (root / "BAD.json").write_text(json.dumps(bad))
    (root / "index.json").write_text(json.dumps({"shorts": [{k: bad[k] for k in ("video_id", "title", "url", "status", "reason")}]}))
    ep_dir = tmp_path / "episode-x"
    (ep_dir / "transcript").mkdir(parents=True)
    (ep_dir / "transcript" / "transcript.json").write_text(json.dumps({"words": EP_WORDS}))
    res = CliRunner().invoke(ps.app, ["match", str(ep_dir)])
    assert res.exit_code != 0 and not (ep_dir / "published-overlap.json").exists()


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q", "-p", "no:cacheprovider"]))
