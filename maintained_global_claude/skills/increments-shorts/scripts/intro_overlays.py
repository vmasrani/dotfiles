#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pydantic>=2.9", "pyyaml>=6.0", "typer>=0.12", "loguru>=0.7", "rich>=13.7"]
# ///
"""Intro title card + speaker name tags for a horizontal clip, generated from episode.yaml.

Reads `show:` (name, hosts, guest, own_show), `speakers[].full_name/role` and `layout_timeline:`
(which gallery tile each speaker occupies at which SOURCE time) and writes text overlays into the
clip's `overlays:` — no hand-typed overlay text:

* `T0`  card, word-revealed: `<SHOW> / <hosts> / with <guest>` (no "with" line on the owner's own show)
* `T1…` lower-thirds for everyone on screen (speakers at their first line, silent hosts right after the
  intro), each on the tile that person occupies AT THAT MOMENT (`tile-left|mid|right`), staggered so the text layer never overlaps itself.

The blurred opening footage + cover art (`P0`, the picture half of the intro) is a B-roll file and
is NOT generated here: references/broll-horizontal.md § Intro.

    intro_overlays.py CLIP_DIR            # print the overlays
    intro_overlays.py CLIP_DIR --apply    # append them to clip.yaml (then run validate_clip.py)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
from rich.console import Console

from pslib import (
    BrollSpec,
    Clip,
    Episode,
    Overlay,
    Speaker,
    TextLine,
    TextRun,
    load_clip,
    load_episode,
    save_clip,
)
from psmedia import episode_root_for

console = Console()
app = typer.Typer(add_completion=False)

TAG_SECONDS = 4.0
TAG_GAP_S = 0.3   # gap between consecutive text-layer overlays
FIRST_WORD_LEAD_S = 0.5  # a tag lands this long after its speaker's first word


def intro_card(episode: Episode, intro_s: float) -> Overlay:
    show = episode.show
    if show is None:
        raise ValueError("episode.yaml has no `show:` block (name, hosts, guest, own_show) — add it before generating the intro card")
    lines = [
        TextLine(runs=[TextRun(text=show.name.upper(), color="accent", weight=800)]),
        TextLine(runs=[TextRun(text=" & ".join(show.hosts), at=0.7)]),
    ]
    if show.guest and not show.own_show:
        lines.append(TextLine(runs=[TextRun(text=f"with {show.guest}", color="muted", at=1.3)]))
    return Overlay(
        id="T0", mode="card", start=0.4, end=round(intro_s - 0.3, 3), lines=lines, reveal="words", reveal_s=1.4,
        placement="title-center", fade_in_frames=8, fade_out_frames=10, note="intro title (episode.yaml show:)",
    )


def tag_order(clip: Clip, episode: Episode) -> list[tuple[Speaker, float, float]]:
    """(speaker, desired tag time, source time) for everyone on screen, in tag order.

    A speaker who talks in the clip is tagged when they first speak; a host on a tile who never talks
    in the clip is tagged right after the intro (the owner tags everybody early)."""
    by_id = {s.id: s for s in episode.speakers}
    spoke: dict[str, tuple[Speaker, float, float]] = {}
    for seg in clip.timeline:
        if not seg.is_insert and seg.speaker in by_id and seg.speaker not in spoke:
            spoke[seg.speaker] = (by_id[seg.speaker], seg.output_in, seg.source_in)
    first_src = clip.timeline[0].source_in
    silent = [(s, 0.0, first_src) for s in episode.speakers
              if s.id not in spoke and episode.tile_of(s.id, first_src) is not None]
    return sorted([*spoke.values(), *silent], key=lambda t: t[1])  # stable: speakers before silent hosts on ties


def name_tags(episode: Episode, clip: Clip, after_s: float) -> list[Overlay]:
    if not episode.layout_timeline:
        raise ValueError("episode.yaml has no `layout_timeline:` — record which gallery tile each speaker sits on "
                         "(from face tracks, confirmed on source frames) before generating name tags")
    tags: list[Overlay] = []
    cursor = after_s
    for i, (speaker, out_in, src_in) in enumerate(tag_order(clip, episode), start=1):
        tile = episode.tile_of(speaker.id, src_in)
        if tile is None:
            raise ValueError(f"layout_timeline places {speaker.id!r} on no tile at source {src_in:.1f}s")
        start = round(max(out_in + FIRST_WORD_LEAD_S, cursor), 3)
        runs = [TextLine(runs=[TextRun(text=speaker.full_name or speaker.name)])]
        if speaker.role:
            runs.append(TextLine(runs=[TextRun(text=speaker.role, color="muted")]))
        tags.append(Overlay(
            id=f"T{i}", mode="lowerthird", start=start, end=round(start + TAG_SECONDS, 3), lines=runs,
            placement=f"tile-{tile}", fade_in_frames=6, fade_out_frames=8, note=f"name tag, {tile} tile",
        ))
        cursor = start + TAG_SECONDS + TAG_GAP_S
    return tags


def build_intro_overlays(episode: Episode, clip: Clip, intro_s: float) -> list[Overlay]:
    """The card (when intro_s > 0) and one name tag per speaker; refuses to collide with existing overlay ids."""
    card = [intro_card(episode, intro_s)] if intro_s > 0 else []
    made = [*card, *name_tags(episode, clip, after_s=intro_s + TAG_GAP_S if intro_s > 0 else 0.0)]
    clash = {o.id for o in made} & {o.id for o in clip.overlays}
    if clash:
        raise ValueError(f"clip already has overlay id(s) {sorted(clash)} — remove them or rename before generating")
    return made


@app.command()
def main(
    clip_dir: Path = typer.Argument(..., help="Horizontal clip directory"),
    intro_s: float = typer.Option(5.0, "--intro-s", help="Length of the P0 intro picture; 0 = no title card, tags only"),
    apply: bool = typer.Option(False, "--apply", help="Append to clip.yaml (default: print)"),
    protected_tail_s: float = typer.Option(45.0, "--protected-tail-s", help="Used only if the clip has no `broll:` block yet"),
    episode_root: Path = typer.Option(None, "--episode-root"),
) -> None:
    """Generate the intro card and name tags for CLIP_DIR from episode.yaml."""
    clip_dir = clip_dir.expanduser().resolve()
    root = episode_root_for(clip_dir, episode_root)
    episode, clip = load_episode(root / "episode.yaml"), load_clip(clip_dir / "clip.yaml")
    if clip.clip.format != "clip":
        raise typer.BadParameter("intro cards and name tags are for horizontal clips (format: clip)")
    made = build_intro_overlays(episode, clip, intro_s)
    for o in made:
        console.print(f"{o.id:3} {o.mode:10} {o.start:7.2f}-{o.end:7.2f}  {o.placement:12} "
                      f"{' / '.join(r.text for ln in o.lines for r in ln.runs)}")
    if not apply:
        return
    clip.overlays = sorted([*clip.overlays, *made], key=lambda o: o.start)
    if clip.broll is None:
        clip.broll = BrollSpec(protected_tail_s=protected_tail_s)
    save_clip(clip_dir / "clip.yaml", clip)
    console.print(f"[green]wrote {len(made)} overlays[/] -> {clip_dir / 'clip.yaml'}; now run validate_clip.py")


if __name__ == "__main__":
    app()
