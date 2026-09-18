from __future__ import annotations

from pathlib import Path

import requests


# Static Poppins weights are available directly in google/fonts. Inter is served
# there as a variable font, which Pillow can load normally for our body text.
FONT_SOURCES = {
    ("Poppins", "bold"): "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf",
    ("Poppins", "regular"): "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Medium.ttf",
    ("Inter", "regular"): "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter%5Bopsz%2Cwght%5D.ttf",
}

SYSTEM_FALLBACKS = {
    ("Poppins", "bold"): [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ],
    ("Poppins", "regular"): [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ],
    ("Inter", "regular"): [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans.ttf"),
    ],
}


def get_font_path(cache_dir: Path, family: str, weight: str) -> Path:
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)

    key = (family, weight)
    dest = cache_dir / f"{family.lower()}-{weight.lower()}.ttf"

    if dest.exists() and dest.stat().st_size > 10_000:
        return dest

    url = FONT_SOURCES.get(key)
    if url:
        try:
            response = requests.get(
                url,
                timeout=30,
                headers={"User-Agent": "ig-charity-automation/0.2"},
            )
            response.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".part")
            tmp.write_bytes(response.content)
            if tmp.stat().st_size <= 10_000:
                raise RuntimeError("downloaded font is unexpectedly small")
            tmp.replace(dest)
            return dest
        except Exception:
            dest.unlink(missing_ok=True)
            dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)

    for fallback in SYSTEM_FALLBACKS.get(key, []):
        if fallback.exists():
            return fallback

    raise RuntimeError(
        f"No usable font available for family={family!r}, weight={weight!r}"
    )
