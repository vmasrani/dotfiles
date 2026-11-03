#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pillow>=10", "pydantic>=2.9", "pyyaml>=6", "typer>=0.12", "loguru>=0.7", "static-ffmpeg>=2.7", "httpx>=0.27", "platformdirs>=4"]
# ///
"""Declarative thumbnail options + contact sheet (1080x1920, clean source frames, Anton text).

`thumbnails.yaml` (in the episode dir):

  shorts:
    <clip-slug>:
      title: "Does P(doom) make any sense?"        # used only to reject thumbnail text that repeats it
      options:
        - {id: a, style: bw, lines: ["I DON'T KNOW."], frame: {t: 1094.5, tile_x: 640}}
        - {id: b, style: split, lines: ["GIVE ME A NUMBER", "GO FIND OUT"], frame: {t: 1020, tile_x: 0}, frame2: {t: 1094.5, tile_x: 640}}

Styles: bw (B&W + yellow text, optional red strike) · color · stack (white line over red block) ·
banner (yellow banner) · sticker (tilted sticker) · quote (quote card) · split (two faces, diagonal, VS) ·
circles (two ringed portraits) · quoteshot (real quote screenshot card + face, needs `quote_image`).
`frame.tile_x` is the left edge of a speaker's tile in a 1920x1080 gallery frame (a 608x1080 strip is cut);
without it the frame's centre 9:16 strip is used. Frames come straight from the source video, so
captions are never burned in. Rules: text is 1-3 words per line and COMPLEMENTS the title; text never covers eyes
(keep text in the top 40% or bottom 25% — styles do this).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))

import typer
import yaml
from loguru import logger
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps
from pydantic import BaseModel, ConfigDict, Field, model_validator

from assets import anton_font
from mediatools import ffmpeg_tool

W, H = 1080, 1920
YELLOW, RED, WHITE, BLACK = (255, 214, 0), (226, 35, 35), (255, 255, 255), (0, 0, 0)
MAX_WORDS_PER_LINE = 3
STYLES = ("bw", "color", "stack", "banner", "sticker", "quote", "split", "circles", "quoteshot")
TWO_FACE = ("split", "circles")
app = typer.Typer(add_completion=False)


class Frame(BaseModel):
    model_config = ConfigDict(extra="forbid")
    t: float = Field(ge=0)
    tile_x: int | None = None


class Option(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    style: Literal[STYLES]  # type: ignore[valid-type]
    lines: list[str] = Field(min_length=1, max_length=2)
    kicker: str | None = None
    strike: bool = False
    frame: Frame | None = None
    frame2: Frame | None = None
    quote_image: str | None = None
    quote_crop: list[int] | None = None  # [left, top, right, bottom] in the quote image

    @model_validator(mode="after")
    def _check(self) -> "Option":
        for ln in self.lines:
            if len(ln.split()) > MAX_WORDS_PER_LINE:
                raise ValueError(f"option {self.id}: line {ln!r} has more than {MAX_WORDS_PER_LINE} words — thumbnail text is 1-3 words")
        if self.style != "quoteshot" and self.frame is None:
            raise ValueError(f"option {self.id}: style {self.style} needs `frame`")
        if self.style in TWO_FACE and (self.frame is None or self.frame2 is None):
            raise ValueError(f"option {self.id}: style {self.style} needs `frame` and `frame2` (two faces)")
        if self.style in ("stack", "split", "circles") and len(self.lines) != 2:
            raise ValueError(f"option {self.id}: style {self.style} needs exactly 2 lines")
        if self.style == "quoteshot" and not (self.quote_image and self.frame):
            raise ValueError(f"option {self.id}: quoteshot needs `quote_image` and `frame`")
        return self


class ShortSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str | None = None
    options: list[Option] = Field(min_length=1)

    @model_validator(mode="after")
    def _complement_title(self) -> "ShortSpec":
        ids = [o.id for o in self.options]
        if len(set(ids)) != len(ids):
            raise ValueError(f"duplicate option ids {ids}")
        if self.title:
            t = words(self.title)
            for o in self.options:
                text = words(" ".join(o.lines))
                if text and len(text & t) / len(text) >= 0.7:
                    raise ValueError(f"option {o.id}: thumbnail text {o.lines} repeats the title {self.title!r} — it must COMPLEMENT it")
        return self


class Spec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str | None = None
    shorts: dict[str, ShortSpec] = Field(min_length=1)


def words(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9']+", s.lower()))


def load_spec(path: Path) -> Spec:
    return Spec.model_validate(yaml.safe_load(path.read_text()))


# ---------------------------------------------------------------- drawing helpers

def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(anton_font()), size)


def fit(text: str, max_w: int, start: int = 400) -> ImageFont.FreeTypeFont:
    size = start
    while font(size).getlength(text) > max_w and size > 20:
        size -= 4
    return font(size)


def centered(d: ImageDraw.ImageDraw, y: float, text: str, f, fill, stroke: int = 0):
    x = (W - f.getlength(text)) / 2
    d.text((x, y), text, font=f, fill=fill, stroke_width=stroke, stroke_fill=BLACK)
    return d.textbbox((x, y), text, font=f)


def top_shade(img: Image.Image, span: float) -> Image.Image:
    mask = Image.new("L", (1, H))
    for y in range(H):
        mask.putpixel((0, y), int(230 * max(0, 1 - (y / H) / span)))
    return Image.composite(Image.new("RGB", (W, H), BLACK), img, mask.resize((W, H)))


def strike(d, bbox, size):
    mid = (bbox[1] + bbox[3]) / 2
    d.line((bbox[0], mid + 6, bbox[2], mid - 6), fill=RED, width=max(12, int(size * 0.07)))


def grab(video: Path, fr: Frame, out: Path, face: bool = False) -> Image.Image:
    """One clean frame: tile strip (or centre strip) scaled to 1080x1920, or a square face crop when face=True."""
    if face:
        vf = f"crop=640:640:{fr.tile_x or 0}:20,scale=1080:1080:flags=lanczos,unsharp=5:5:0.6"
    elif fr.tile_x is not None:
        vf = f"crop=608:1080:{fr.tile_x + 16}:0,scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6"
    else:
        vf = f"crop=ih*9/16:ih,scale={W}:{H}:flags=lanczos,unsharp=5:5:0.6"
    cmd = [ffmpeg_tool("ffmpeg"), "-hide_banner", "-nostdin", "-loglevel", "error", "-y", "-ss", f"{fr.t:.3f}", "-i", str(video),
           "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not out.is_file():
        raise RuntimeError(f"frame grab at t={fr.t} failed: {proc.stderr.strip()[-400:]}")
    return Image.open(out).convert("RGB")


# ---------------------------------------------------------------- styles (base image -> thumbnail)

def s_bw(o: Option, base, _b2):
    img = top_shade(ImageEnhance.Color(base).enhance(0.0), 0.5)
    d = ImageDraw.Draw(img)
    f = fit(o.lines[0], W - 80)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    centered(ImageDraw.Draw(shadow), 218, o.lines[0], f, (0, 0, 0, 255))
    blurred = shadow.filter(ImageFilter.GaussianBlur(12))
    img.paste(blurred, (14, 0), blurred)
    bbox = centered(d, 200, o.lines[0], f, YELLOW)
    if o.strike:
        strike(d, bbox, f.size)
    if o.kicker:
        centered(d, bbox[3] + 40, o.kicker, fit(o.kicker, W - 140, 110), WHITE, stroke=6)
    return img


def s_color(o: Option, base, _b2):
    img = top_shade(base, 0.45)
    d = ImageDraw.Draw(img)
    f = fit(o.lines[0], W - 80)
    bbox = centered(d, 150, o.lines[0], f, YELLOW, stroke=10)
    if o.strike:
        strike(d, bbox, f.size)
    if o.kicker:
        centered(d, bbox[3] + 40, o.kicker, fit(o.kicker, W - 140, 120), WHITE, stroke=6)
    return img


def s_stack(o: Option, base, _b2):
    img = top_shade(ImageEnhance.Brightness(base).enhance(0.9), 0.55)
    d = ImageDraw.Draw(img)
    f = min((fit(line, W - 120) for line in o.lines), key=lambda x: x.size)
    centered(d, 70, o.lines[0], f, WHITE, stroke=8)
    y2 = 70 + f.size * 1.08
    bbox = d.textbbox(((W - f.getlength(o.lines[1])) / 2, y2), o.lines[1], font=f)
    d.rectangle((bbox[0] - 30, bbox[1] - 30, bbox[2] + 30, bbox[3] + 30), fill=RED)
    centered(d, y2, o.lines[1], f, WHITE)
    return img


def s_banner(o: Option, base, _b2):
    img = top_shade(base, 0.3)
    d = ImageDraw.Draw(img)
    f = fit(o.lines[0], W - 140, 260)
    b = d.textbbox((0, 0), o.lines[0], font=f)
    y = 90
    d.rectangle((0, y, W, y + (b[3] - b[1]) + 70), fill=YELLOW)
    d.text(((W - f.getlength(o.lines[0])) / 2, y + 35 - b[1]), o.lines[0], font=f, fill=BLACK)
    return img


def s_sticker(o: Option, base, _b2):
    img = base.copy()
    f = fit(o.lines[0], W - 300, 240)
    b = f.getbbox(o.lines[0])
    tw, th = b[2] - b[0], b[3] - b[1]
    sticker = Image.new("RGBA", (tw + 120, th + 100), (0, 0, 0, 0))
    sd = ImageDraw.Draw(sticker)
    sd.rounded_rectangle((0, 0, sticker.width - 1, sticker.height - 1), 26, fill=YELLOW, outline=BLACK, width=8)
    sd.text((60, 50 - b[1]), o.lines[0], font=f, fill=BLACK)
    sticker = sticker.rotate(-6, expand=True, resample=Image.BICUBIC)
    img.paste(sticker, ((W - sticker.width) // 2, 140), sticker)
    return img


def s_quote(o: Option, base, _b2):
    img = top_shade(base, 0.55)
    d = ImageDraw.Draw(img)
    f = fit(o.lines[0], W - 220, 230)
    bbox = d.textbbox((0, 0), o.lines[0], font=f)
    card = (60, 110, W - 60, 110 + (bbox[3] - bbox[1]) + 120)
    d.rounded_rectangle(card, 30, fill=WHITE)
    d.text(((W - f.getlength(o.lines[0])) / 2, card[1] + 60 - bbox[1]), o.lines[0], font=f, fill=BLACK)
    d.text((card[0] + 30, card[1] - 40), "“", font=font(220), fill=YELLOW, stroke_width=6, stroke_fill=BLACK)
    return img


def label(d, y, text, bg, fg):
    f = fit(text, W - 220, 120)
    b = d.textbbox((0, 0), text, font=f)
    tw, th = b[2] - b[0], b[3] - b[1]
    x0 = (W - tw) / 2
    d.rectangle((x0 - 30, y - 22, x0 + tw + 30, y + th + 26), fill=bg)
    d.text((x0, y - b[1]), text, font=f, fill=fg)


def s_split(o: Option, top, bottom):
    img = Image.new("RGB", (W, H), BLACK)
    img.paste(top.resize((W, W)).crop((0, 60, W, 1040)), (0, 0))
    canvas = Image.new("RGB", (W, H), BLACK)
    canvas.paste(bottom.resize((W, W)), (0, H - W))
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon([(0, 1020), (W, 880), (W, H), (0, H)], fill=255)
    img = Image.composite(canvas, img, mask)
    d = ImageDraw.Draw(img)
    d.line((0, 1020, W, 880), fill=YELLOW, width=26)
    cx, cy = W / 2, 950
    d.ellipse((cx - 110, cy - 110, cx + 110, cy + 110), fill=RED, outline=WHITE, width=10)
    d.text((cx, cy), "VS", font=fit("VS", 150, 130), fill=WHITE, anchor="mm")
    label(d, 70, o.lines[0], WHITE, BLACK)
    label(d, H - 220, o.lines[1], YELLOW, BLACK)
    return img


def circle(img, size, ring):
    img = ImageOps.fit(img, (size, size))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size + 2 * ring, size + 2 * ring), (0, 0, 0, 0))
    ImageDraw.Draw(out).ellipse((0, 0, size + 2 * ring, size + 2 * ring), fill=WHITE)
    out.paste(img, (ring, ring), mask)
    return out


def s_circles(o: Option, a, b):
    bg = b.resize((W * 2, W * 2)).crop((W // 2, 0, W // 2 + W, H)).filter(ImageFilter.GaussianBlur(40))
    img = Image.blend(bg, Image.new("RGB", (W, H), BLACK), 0.55)
    e, v = circle(a, 640, 14), circle(b, 720, 14)
    img.paste(e, (40, 520), e)
    img.paste(v, (W - v.width - 30, 1060), v)
    d = ImageDraw.Draw(img)
    f = min((fit(line, W - 100) for line in o.lines), key=lambda x: x.size)
    centered(d, 90, o.lines[0], f, WHITE, stroke=8)
    centered(d, 90 + f.size * 1.1, o.lines[1], f, YELLOW, stroke=8)
    return img


def s_quoteshot(o: Option, base, _b2, root: Path | None = None):
    img = top_shade(base, 0.6)
    q = Image.open(root / o.quote_image if root else o.quote_image).convert("RGB")
    if o.quote_crop:
        q = q.crop(tuple(o.quote_crop))
    qw = W - 100
    q = q.resize((qw, int(q.height * qw / q.width)), Image.LANCZOS)
    card = Image.new("RGB", (qw + 24, q.height + 24), WHITE)
    card.paste(q, (12, 12))
    shadow = Image.new("RGBA", (card.width + 80, card.height + 80), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle((40, 40, 40 + card.width, 40 + card.height), fill=(0, 0, 0, 200))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18))
    card = card.convert("RGBA").rotate(-3, expand=True, resample=Image.BICUBIC)
    y = 200
    img.paste(shadow, ((W - shadow.width) // 2 + 10, y - 20), shadow)
    img.paste(card, ((W - card.width) // 2, y), card)
    f = fit(o.lines[0], W - 100, 220)
    centered(ImageDraw.Draw(img), y + card.height + 40, o.lines[0], f, YELLOW, stroke=10)
    return img


RENDERERS = {"bw": s_bw, "color": s_color, "stack": s_stack, "banner": s_banner, "sticker": s_sticker,
             "quote": s_quote, "split": s_split, "circles": s_circles, "quoteshot": s_quoteshot}


def render_option(o: Option, video: Path, work: Path, root: Path) -> Image.Image:
    base = grab(video, o.frame, work / f"base-{o.id}.jpg", face=o.style in TWO_FACE) if o.frame else Image.new("RGB", (W, H), BLACK)
    second = grab(video, o.frame2, work / f"base2-{o.id}.jpg", face=True) if o.frame2 else None
    if o.style == "quoteshot":
        return s_quoteshot(o, base, None, root)
    return RENDERERS[o.style](o, base, second)


def contact_sheet(items: list[tuple[str, Image.Image]], out: Path, cols: int = 4) -> Path:
    tw, th, pad, lab = 270, 480, 16, 34
    rows = (len(items) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + lab + pad) + pad), (40, 40, 40))
    d = ImageDraw.Draw(sheet)
    for i, (name, im) in enumerate(items):
        x, y = pad + (i % cols) * (tw + pad), pad + (i // cols) * (th + lab + pad)
        sheet.paste(im.resize((tw, th)), (x, y + lab))
        d.text((x, y + 4), name, font=font(24), fill=WHITE)
    sheet.save(out, quality=88)
    return out


@app.command()
def main(
    episode_dir: Path = typer.Argument(..., help="Episode directory"),
    spec: Path = typer.Option(None, "--spec", help="thumbnails.yaml (default EPISODE/thumbnails.yaml)"),
    only: list[str] = typer.Option(None, "--only", help="Only these clip slugs"),
) -> None:
    """Render every option to EPISODE/thumbnails/<slug>/<id>.jpg and write EPISODE/thumbnails/contact-sheet.jpg."""
    root = episode_dir.expanduser().resolve()
    sp = load_spec(spec or root / "thumbnails.yaml")
    ep = yaml.safe_load((root / "episode.yaml").read_text())
    video = root / (sp.source or ep["media"]["episode_video"])
    if not video.is_file():
        raise FileNotFoundError(f"source video not found: {video}")
    out_root = root / "thumbnails"
    items: list[tuple[str, Image.Image]] = []
    for slug, short in sp.shorts.items():
        if only and slug not in only:
            continue
        d = out_root / slug
        d.mkdir(parents=True, exist_ok=True)
        for o in short.options:
            im = render_option(o, video, d, root)
            im.save(d / f"{o.id}.jpg", quality=90)
            items.append((f"{slug[:8]}/{o.id} {o.style}", im))
            logger.info(f"{slug}/{o.id} ({o.style}) -> {d / (o.id + '.jpg')}")
    sheet = contact_sheet(items, out_root / "contact-sheet.jpg")
    print(sheet)


if __name__ == "__main__":
    app()
