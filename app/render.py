from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.content import ReelCopy
from app.music import MusicTrack


WIDTH = 1080
HEIGHT = 1920


@dataclass(frozen=True)
class RenderResult:
    video: Path
    cover: Path
    style_name: str


STYLES = [
    {
        "name": "charcoal",
        "top": (25, 27, 33),
        "bottom": (43, 46, 54),
        "accent": (255, 255, 255),
        "muted": (226, 229, 235),
        "align": "center",
    },
    {
        "name": "warm_gradient",
        "top": (246, 75, 36),
        "bottom": (255, 38, 91),
        "accent": (255, 255, 255),
        "muted": (255, 247, 241),
        "align": "center",
    },
    {
        "name": "dusk",
        "top": (53, 44, 82),
        "bottom": (18, 23, 42),
        "accent": (255, 255, 255),
        "muted": (233, 229, 244),
        "align": "center",
    },
    {
        "name": "blue_fog",
        "top": (36, 72, 99),
        "bottom": (20, 28, 39),
        "accent": (247, 251, 255),
        "muted": (220, 233, 242),
        "align": "left",
    },
    {
        "name": "soft_rose",
        "top": (118, 65, 78),
        "bottom": (36, 27, 37),
        "accent": (255, 250, 250),
        "muted": (244, 224, 229),
        "align": "center",
    },
    {
        "name": "midnight",
        "top": (7, 11, 18),
        "bottom": (24, 35, 49),
        "accent": (255, 255, 255),
        "muted": (210, 220, 232),
        "align": "left",
    },
]


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/dejavu") / name,
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.truetype(name, size=size)


def _gradient(top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    image = Image.new("RGB", (WIDTH, HEIGHT), top)
    draw = ImageDraw.Draw(image)
    for y in range(HEIGHT):
        ratio = y / max(1, HEIGHT - 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        draw.line((0, y, WIDTH, y), fill=color)
    return image


def _decorate(image: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed)
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    for _ in range(5):
        cx = rng.randint(-150, WIDTH + 150)
        cy = rng.randint(-200, HEIGHT + 200)
        r = rng.randint(160, 360)
        alpha = rng.randint(10, 24)
        draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(255, 255, 255, alpha))
    overlay = overlay.filter(ImageFilter.GaussianBlur(110))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> str:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width or not current:
            current.append(word)
        else:
            lines.append(" ".join(current))
            current = [word]
    if current:
        lines.append(" ".join(current))
    return "\n".join(lines)


def _text_block_height(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, spacing: int
) -> int:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def _fit_body(
    draw: ImageDraw.ImageDraw, text: str, width: int, max_height: int
) -> tuple[ImageFont.FreeTypeFont, str, int]:
    for size in range(49, 34, -2):
        font = _font(False, size)
        wrapped = _wrap(draw, text, font, width)
        spacing = max(12, int(size * 0.34))
        if _text_block_height(draw, wrapped, font, spacing) <= max_height:
            return font, wrapped, spacing
    font = _font(False, 34)
    return font, _wrap(draw, text, font, width), 12


def create_cover(copy: ReelCopy, slot_id: str, out: Path) -> tuple[Path, str]:
    seed = int(hashlib.sha256((slot_id + ":style").encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    style = rng.choice(STYLES)

    image = _decorate(_gradient(style["top"], style["bottom"]), seed)
    draw = ImageDraw.Draw(image)
    margin = 92
    max_width = WIDTH - margin * 2
    align = style["align"]
    anchor_x = WIDTH // 2 if align == "center" else margin
    anchor = "ma" if align == "center" else "la"

    hook_font = _font(True, 64 if align == "center" else 58)
    hook = _wrap(draw, copy.hook, hook_font, max_width)
    hook_spacing = 14

    body_font, body, body_spacing = _fit_body(draw, copy.body, max_width, 740)
    cta_font = _font(True, 38)
    cta = _wrap(draw, copy.cta, cta_font, max_width)
    cta_spacing = 12

    hook_h = _text_block_height(draw, hook, hook_font, hook_spacing)
    body_h = _text_block_height(draw, body, body_font, body_spacing)
    cta_h = _text_block_height(draw, cta, cta_font, cta_spacing)
    gaps = 54 + 58
    total_h = hook_h + body_h + cta_h + gaps
    y = max(260, (HEIGHT - total_h) // 2 - 10)

    shadow = (0, 0, 0)
    draw.multiline_text(
        (anchor_x + 2, y + 3),
        hook,
        font=hook_font,
        fill=shadow,
        spacing=hook_spacing,
        align=align,
        anchor=anchor,
    )
    draw.multiline_text(
        (anchor_x, y),
        hook,
        font=hook_font,
        fill=style["accent"],
        spacing=hook_spacing,
        align=align,
        anchor=anchor,
    )
    y += hook_h + 54

    draw.multiline_text(
        (anchor_x, y),
        body,
        font=body_font,
        fill=style["muted"],
        spacing=body_spacing,
        align=align,
        anchor=anchor,
    )
    y += body_h + 58

    draw.multiline_text(
        (anchor_x, y),
        cta,
        font=cta_font,
        fill=style["accent"],
        spacing=cta_spacing,
        align=align,
        anchor=anchor,
    )

    footer_font = _font(False, 27)
    footer = "@kiaraprmd  •  link in bio"
    draw.text(
        (WIDTH // 2, HEIGHT - 126),
        footer,
        font=footer_font,
        fill=(226, 230, 236),
        anchor="mm",
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=95)
    return out, style["name"]


def render_reel(
    *,
    copy: ReelCopy,
    music: MusicTrack,
    slot_id: str,
    duration_seconds: int,
    out_dir: Path,
) -> RenderResult:
    out_dir.mkdir(parents=True, exist_ok=True)
    cover, style_name = create_cover(copy, slot_id, out_dir / f"{slot_id}.jpg")
    video = out_dir / f"{slot_id}.mp4"

    fade_out = max(0.0, float(duration_seconds) - 1.2)
    vf = f"fade=t=in:st=0:d=0.45,fade=t=out:st={fade_out:.2f}:d=1.0,format=yuv420p"
    af = f"volume=0.22,afade=t=in:st=0:d=1.0,afade=t=out:st={fade_out:.2f}:d=1.0"

    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-i",
        str(cover),
        "-stream_loop",
        "-1",
        "-i",
        str(music.path),
        "-t",
        str(duration_seconds),
        "-vf",
        vf,
        "-af",
        af,
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "22",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(video),
    ]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if not video.exists() or video.stat().st_size < 150_000:
        raise RuntimeError("rendered reel is missing or unexpectedly small")
    return RenderResult(video=video, cover=cover, style_name=style_name)
