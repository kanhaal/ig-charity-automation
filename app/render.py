from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import random
import subprocess

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from app.content import ReelCopy
from app.fonts import get_font_path
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
        "name": "insta_orange",
        "top": (255, 184, 100),
        "bottom": (255, 104, 86),
        "accent": (255, 255, 255),
        "body": (255, 247, 244),
        "cta": (255, 255, 255),
        "align": "center",
    },
    {
        "name": "peach_pink",
        "top": (255, 194, 121),
        "bottom": (255, 91, 131),
        "accent": (255, 255, 255),
        "body": (255, 245, 242),
        "cta": (255, 255, 255),
        "align": "center",
    },
    {
        "name": "sunset_coral",
        "top": (255, 202, 125),
        "bottom": (246, 112, 104),
        "accent": (255, 255, 255),
        "body": (255, 248, 245),
        "cta": (255, 255, 255),
        "align": "center",
    },
    {
        "name": "soft_instagram",
        "top": (255, 178, 100),
        "bottom": (238, 88, 127),
        "accent": (255, 255, 255),
        "body": (255, 246, 243),
        "cta": (255, 255, 255),
        "align": "left",
    },
    {
        "name": "light_coral",
        "top": (255, 191, 135),
        "bottom": (255, 111, 106),
        "accent": (255, 255, 255),
        "body": (255, 247, 244),
        "cta": (255, 255, 255),
        "align": "center",
    },
]


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

    for _ in range(8):
        cx = rng.randint(-140, WIDTH + 140)
        cy = rng.randint(-160, HEIGHT + 160)
        radius = rng.randint(180, 380)
        alpha = rng.randint(8, 22)
        color = rng.choice(
            [
                (255, 255, 255, alpha),
                (255, 224, 198, alpha),
                (255, 206, 171, alpha),
            ]
        )
        draw.ellipse(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            fill=color,
        )

    overlay = overlay.filter(ImageFilter.GaussianBlur(120))
    return Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")


def _font(
    cache_dir: Path,
    family: str,
    weight: str,
    size: int,
) -> ImageFont.FreeTypeFont:
    path = get_font_path(cache_dir, family, weight)
    return ImageFont.truetype(str(path), size=size)


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> str:
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


def _text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    spacing: int,
) -> int:
    bbox = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing)
    return bbox[3] - bbox[1]


def _fit_body(
    draw: ImageDraw.ImageDraw,
    cache_dir: Path,
    text: str,
    width: int,
    max_height: int,
) -> tuple[ImageFont.FreeTypeFont, str, int]:
    for size in range(50, 35, -2):
        font = _font(cache_dir, "Inter", "regular", size)
        wrapped = _wrap(draw, text, font, width)
        spacing = max(11, int(size * 0.34))
        if _text_height(draw, wrapped, font, spacing) <= max_height:
            return font, wrapped, spacing

    font = _font(cache_dir, "Inter", "regular", 34)
    return font, _wrap(draw, text, font, width), 11


def _default_font_cache(out: Path) -> Path:
    # Keep cache beside the normal output tree. This makes direct/test callers
    # work without having to know about the font-cache implementation detail.
    return Path(out).parent / ".cache" / "fonts"


def create_cover(
    copy: ReelCopy,
    slot_id: str,
    out: Path,
    font_cache_dir: Path | None = None,
) -> tuple[Path, str]:
    out = Path(out)
    font_cache = Path(font_cache_dir) if font_cache_dir is not None else _default_font_cache(out)

    seed = int(hashlib.sha256((slot_id + ":style").encode()).hexdigest()[:16], 16)
    rng = random.Random(seed)
    style = rng.choice(STYLES)

    image = _decorate(_gradient(style["top"], style["bottom"]), seed)
    draw = ImageDraw.Draw(image)

    margin = 88
    max_width = WIDTH - margin * 2
    align = style["align"]
    anchor_x = WIDTH // 2 if align == "center" else margin
    anchor = "ma" if align == "center" else "la"

    hook_font = _font(
        font_cache,
        "Poppins",
        "bold",
        72 if align == "center" else 66,
    )
    hook = _wrap(draw, copy.hook, hook_font, max_width)
    hook_spacing = 14

    body_font, body, body_spacing = _fit_body(
        draw,
        font_cache,
        copy.body,
        max_width,
        620,
    )

    cta_font = _font(font_cache, "Poppins", "bold", 41)
    cta = _wrap(draw, copy.cta, cta_font, max_width)
    cta_spacing = 12

    hook_h = _text_height(draw, hook, hook_font, hook_spacing)
    body_h = _text_height(draw, body, body_font, body_spacing)
    cta_h = _text_height(draw, cta, cta_font, cta_spacing)

    total_h = hook_h + 72 + body_h + 72 + cta_h
    y = max(220, (HEIGHT - total_h) // 2 - 12)

    shadow_fill = (47, 34, 39)
    draw.multiline_text(
        (anchor_x + 3, y + 4),
        hook,
        font=hook_font,
        fill=shadow_fill,
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

    y += hook_h + 72
    draw.multiline_text(
        (anchor_x, y),
        body,
        font=body_font,
        fill=style["body"],
        spacing=body_spacing,
        align=align,
        anchor=anchor,
    )

    y += body_h + 72
    draw.multiline_text(
        (anchor_x + 2, y + 2),
        cta,
        font=cta_font,
        fill=shadow_fill,
        spacing=cta_spacing,
        align=align,
        anchor=anchor,
    )
    draw.multiline_text(
        (anchor_x, y),
        cta,
        font=cta_font,
        fill=style["cta"],
        spacing=cta_spacing,
        align=align,
        anchor=anchor,
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
    font_cache_dir: Path | None = None,
) -> RenderResult:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    font_cache = (
        Path(font_cache_dir)
        if font_cache_dir is not None
        else out_dir.parent / ".cache" / "fonts"
    )

    cover, style_name = create_cover(
        copy,
        slot_id,
        out_dir / f"{slot_id}.jpg",
        font_cache,
    )
    video = out_dir / f"{slot_id}.mp4"

    fade_out = max(0.0, float(duration_seconds) - 1.0)
    vf = (
        f"scale={WIDTH}:{HEIGHT},"
        "fade=t=in:st=0:d=0.35,"
        f"fade=t=out:st={fade_out:.2f}:d=0.85,"
        "format=yuv420p"
    )
    af = (
        "volume=0.24,"
        "afade=t=in:st=0:d=0.8,"
        f"afade=t=out:st={fade_out:.2f}:d=0.85"
    )

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
        "21",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(video),
    ]

    try:
        subprocess.run(
            command,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"FFmpeg Reel render failed: {detail}") from exc

    if not video.exists() or video.stat().st_size < 150_000:
        raise RuntimeError("rendered reel is missing or unexpectedly small")

    return RenderResult(
        video=video,
        cover=cover,
        style_name=style_name,
    )
