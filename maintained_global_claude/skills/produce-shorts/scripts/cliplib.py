"""Shared helpers for `plan_framing.py` and `prep_short.py` (clip.yaml/episode.yaml context, transcript words
in output time). Not executable.

Deliberately dict-based: clip.yaml and episode.yaml are read as plain YAML so these
scripts do not break when `pslib.py`'s strict models move; the invariants these scripts
rely on are asserted where they are used. Everything fails loudly with the offending
file / segment / value named.
"""

from __future__ import annotations

import bisect
import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

SCRIPTS_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPTS_DIR.parent
DEFAULTS_YAML = SKILL_DIR / "config" / "defaults.yaml"
EPS = 0.01

TERMINAL_RE = re.compile(r"[.?!][\"')\]]*$")
QUESTION_RE = re.compile(r"\?[\"')\]]*$")


# ---------------------------------------------------------------------------
# YAML
# ---------------------------------------------------------------------------


def read_yaml(path: Path) -> Any:
    if not path.is_file():
        raise FileNotFoundError(f"missing file: {path}")
    return yaml.safe_load(path.read_text())


def write_yaml(path: Path, payload: Any) -> None:
    """Write via a temp file + rename so an interrupted run never leaves a torn clip.yaml."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=10_000))
    tmp.replace(path)


# ---------------------------------------------------------------------------
# Models for the pieces of the manifest these scripts consume
# ---------------------------------------------------------------------------


class Word(BaseModel):
    model_config = ConfigDict(extra="ignore")

    w: str
    start: float
    end: float
    speaker: str
    conf: float | None = None


class FramingConfig(BaseModel):
    """`framing:` of config/defaults.yaml (episode.yaml may override per key)."""

    model_config = ConfigDict(extra="forbid")

    exchange_gap_s: float
    exchange_turn_s: float
    max_dwell_s: float
    max_upscale: float = 2.0           # closeup source crops are never magnified past this (frame_segments.py)
    # Optional refinements; the defaults are stated here, not hidden in the algorithm.
    min_block_s: float = 1.2           # no treatment flashes shorter than this
    backchannel_max_words: int = 3     # "yeah", "right, right" inside someone's speech
    backchannel_max_s: float = 1.2


@dataclass
class Ctx:
    clip_dir: Path
    root: Path
    clip: dict
    episode: dict
    defaults: dict

    @property
    def fmt(self) -> str:
        return self.clip["clip"]["format"]

    @property
    def speakers(self) -> list[dict]:
        return self.episode["speakers"]

    @property
    def speaker_ids(self) -> list[str]:
        return [s["id"] for s in self.speakers]

    def name(self, speaker_id: str) -> str:
        return {s["id"]: s["name"] for s in self.speakers}[speaker_id]

    @property
    def clip_yaml(self) -> Path:
        return self.clip_dir / "clip.yaml"

    def save_clip(self) -> None:
        write_yaml(self.clip_yaml, self.clip)

    def framing(self) -> FramingConfig:
        merged = {**self.defaults.get("framing", {}), **(self.episode.get("framing") or {})}
        return FramingConfig.model_validate(merged)

    def review_account(self) -> str:
        review = {**self.defaults.get("review", {}), **(self.episode.get("review") or {})}
        if not review.get("account"):
            raise ValueError("no review.account in episode.yaml or config/defaults.yaml")
        return review["account"]


def load_ctx(clip_dir: Path, episode_root: Path | None = None) -> Ctx:
    clip_dir = clip_dir.resolve()
    if not (clip_dir / "clip.yaml").is_file():
        raise FileNotFoundError(f"{clip_dir}/clip.yaml not found — pass the clip directory")
    root = (episode_root or clip_dir.parent.parent).resolve()
    clip = read_yaml(clip_dir / "clip.yaml")
    for key in ("clip", "timeline", "output"):
        if key not in clip:
            raise ValueError(f"{clip_dir}/clip.yaml has no `{key}:` block")
    if clip["clip"].get("format") not in ("short", "clip"):
        raise ValueError(f"{clip_dir}/clip.yaml clip.format must be short|clip, got {clip['clip'].get('format')!r}")
    return Ctx(clip_dir, root, clip, read_yaml(root / "episode.yaml"), read_yaml(DEFAULTS_YAML))


def load_words(ctx: Ctx) -> list[Word]:
    path = ctx.root / ctx.episode["transcript"]["json"]
    if not path.is_file():
        raise FileNotFoundError(f"transcript not found: {path}")
    return [Word.model_validate(w) for w in json.loads(path.read_text())["words"]]


# ---------------------------------------------------------------------------
# Words in output time
# ---------------------------------------------------------------------------


@dataclass
class OutWord:
    """One transcript word placed on the clip's output timeline."""

    idx: int          # position in the clip-wide word list
    seg: int          # index into clip["timeline"]
    text: str
    speaker: str
    src_start: float
    src_end: float
    start: float      # output time
    end: float


def norm_token(token: str) -> str:
    return re.sub(r"[^a-z0-9']", "", token.lower())


def dialogue_tokens(dialogue: str) -> list[str]:
    """Whitespace tokens of the verbatim dialogue; pure-punctuation tokens (— …) glue to the previous."""
    out: list[str] = []
    for tok in dialogue.split():
        if out and not norm_token(tok):
            out[-1] = f"{out[-1]} {tok}"
        else:
            out.append(tok)
    return out


def segment_words(words: list[Word], starts: list[float], seg: dict) -> list[Word]:
    lo = bisect.bisect_left(starts, seg["source_in"] - 1.0)
    picked = []
    for w in words[lo:]:
        if w.start > seg["source_out"]:
            break
        mid = (w.start + w.end) / 2
        if seg["source_in"] <= mid < seg["source_out"]:
            picked.append(w)
    return picked


def place_words(ctx: Ctx, words: list[Word]) -> list[OutWord]:
    """Every transcript word under the timeline, in output time, verified against `dialogue`."""
    starts = [w.start for w in words]
    placed: list[OutWord] = []
    for si, seg in enumerate(ctx.clip["timeline"]):
        inside = segment_words(words, starts, seg)
        expect = [norm_token(t) for t in dialogue_tokens(seg["dialogue"])]
        got = [norm_token(w.w) for w in inside]
        if expect != got:
            n = next((i for i, (a, b) in enumerate(zip(expect, got)) if a != b), min(len(expect), len(got)))
            raise ValueError(
                f"segment {seg['id']}: dialogue does not match the transcript words in "
                f"[{seg['source_in']:.2f}, {seg['source_out']:.2f}] — {len(expect)} dialogue tokens vs "
                f"{len(got)} words; first difference at token {n}: "
                f"dialogue {expect[n:n + 3]} vs transcript {got[n:n + 3]}. Fix `dialogue:` (verbatim) or the range."
            )
        shift = seg["output_in"] - seg["source_in"]
        for w in inside:
            placed.append(
                OutWord(len(placed), si, w.w, w.speaker, w.start, w.end, w.start + shift, w.end + shift)
            )
    return placed


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------


def fmt_ts(seconds: float) -> str:
    s = int(round(seconds))
    return f"{s // 60}:{s % 60:02d}"


def treatment_label(ctx: Ctx, treatment: str, speakers: list[str] | None) -> str:
    """Human wording for a treatment: 'close-up (Kasra)', 'split screen (Kasra / Ben)'."""
    if treatment == "splitscreen":
        return "split screen (" + " / ".join(ctx.name(s) for s in speakers or []) + ")"
    if treatment.startswith("closeup-"):
        return f"close-up ({ctx.name(treatment.removeprefix('closeup-'))})"
    return treatment.replace("-", " ")


def run(cmd: list[str], what: str, cwd: Path | None = None) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if proc.returncode != 0:
        tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-25:])
        raise RuntimeError(f"{what} failed (exit {proc.returncode}): {' '.join(cmd)}\n{tail}")
    return proc.stdout
