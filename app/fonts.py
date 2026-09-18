from __future__ import annotations

from pathlib import Path

import requests


FONT_SOURCES = {
    ("Poppins", "bold"): "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-ExtraBold.ttf",
    ("Poppins", "regular"): "https://raw.githubusercontent.com/google/fonts/main/ofl/poppins/Poppins-Medium.ttf",
    ("Inter", "regular"): "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter_18pt-Medium.ttf",
    ("Inter", "bold"): "https://raw.githubusercontent.com/google/fonts/main/ofl/inter/Inter_18pt-SemiBold.ttf",
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
    ("Inter", "bold"): [
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ],
}


def get_font_path(cache_dir: Path, family: str, weight: str) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{family.lower()}-{weight.lower()}.ttf"
    if dest.exists() and dest.stat().st_size > 10_000:
        return dest

    url = FONT_SOURCES.get((family, weight))
    if url:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            dest.write_bytes(response.content)
            if dest.stat().st_size > 10_000:
                return dest
        except Exception:
            dest.unlink(missing_ok=True)

    for fallback in SYSTEM_FALLBACKS.get((family, weight), []):
        if fallback.exists():
            return fallback

    return Path("DejaVuSans.ttf")
