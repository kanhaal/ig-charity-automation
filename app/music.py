from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import hashlib
import random
import requests


@dataclass(frozen=True)
class MusicTrack:
    id: str
    path: Path
    mood: str
    source_page: str
    license: str


def _download_url(filename: str) -> str:
    return "https://commons.wikimedia.org/wiki/Special:Redirect/file/" + quote(filename, safe="")


def ensure_music_library(music_cfg: dict, cache_dir: Path) -> list[dict]:
    cache_dir.mkdir(parents=True, exist_ok=True)
    ready = []
    failures: list[str] = []
    session = requests.Session()
    session.headers.update({"User-Agent": "ig-charity-automation/0.1 (automated media fetch)"})

    for raw in music_cfg.get("tracks", []):
        suffix = Path(raw["filename"]).suffix or ".ogg"
        dest = cache_dir / f"{raw['id']}{suffix}"
        if not dest.exists() or dest.stat().st_size < 100_000:
            url = _download_url(raw["filename"])
            last_error: Exception | None = None
            for _attempt in range(3):
                try:
                    with session.get(url, stream=True, timeout=60, allow_redirects=True) as response:
                        response.raise_for_status()
                        tmp = dest.with_suffix(dest.suffix + ".part")
                        with tmp.open("wb") as handle:
                            for chunk in response.iter_content(chunk_size=1024 * 256):
                                if chunk:
                                    handle.write(chunk)
                        if tmp.stat().st_size < 100_000:
                            raise RuntimeError("downloaded file is unexpectedly small")
                        tmp.replace(dest)
                        last_error = None
                        break
                except Exception as exc:
                    last_error = exc
                    dest.with_suffix(dest.suffix + ".part").unlink(missing_ok=True)
            if last_error is not None:
                failures.append(f"{raw['id']}: {last_error}")
                continue

        item = dict(raw)
        item["path"] = dest
        ready.append(item)

    if not ready:
        raise RuntimeError("no music track could be downloaded: " + "; ".join(failures))
    return ready


def choose_track(
    tracks: list[dict], *, mood: str, slot_id: str, last_music_id: str | None
) -> MusicTrack:
    candidates = [track for track in tracks if mood in track.get("moods", [])]
    if not candidates:
        candidates = list(tracks)
    if len(candidates) > 1 and last_music_id:
        without_last = [track for track in candidates if track["id"] != last_music_id]
        if without_last:
            candidates = without_last

    seed = int(hashlib.sha256((slot_id + ":music").encode()).hexdigest()[:16], 16)
    track = random.Random(seed).choice(candidates)
    return MusicTrack(
        id=track["id"],
        path=Path(track["path"]),
        mood=mood,
        source_page=track["source_page"],
        license=track["license"],
    )
