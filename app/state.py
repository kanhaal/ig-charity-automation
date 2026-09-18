from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, time
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DueSlot:
    slot_id: str
    local_date: str
    slot_index: int
    scheduled_time: str


def load_state(path: Path) -> dict:
    if not path.exists():
        return {"published": {}, "recent_signatures": [], "last_music_id": None}
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("published", {})
    data.setdefault("recent_signatures", [])
    data.setdefault("last_music_id", None)
    return data


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _parse_hhmm(value: str) -> time:
    hour, minute = (int(part) for part in value.split(":", 1))
    return time(hour=hour, minute=minute)


def next_due_slot(profile_cfg: dict, state: dict, now: datetime | None = None) -> DueSlot | None:
    account = profile_cfg["account"]
    tz = ZoneInfo(account["timezone"])
    local_now = now.astimezone(tz) if now else datetime.now(tz)
    date_text = local_now.date().isoformat()
    current_time = local_now.time().replace(tzinfo=None)

    for idx, scheduled in enumerate(account["posting_times"]):
        slot_id = f"{date_text}-{idx + 1}"
        if slot_id in state["published"]:
            continue
        if current_time >= _parse_hhmm(scheduled):
            return DueSlot(slot_id, date_text, idx, scheduled)
    return None


def mark_published(
    state: dict,
    *,
    slot: DueSlot,
    buffer_post_id: str,
    music_id: str,
    signature: str,
    media_url: str,
) -> None:
    state["published"][slot.slot_id] = {
        "buffer_post_id": buffer_post_id,
        "music_id": music_id,
        "signature": signature,
        "media_url": media_url,
    }
    state["last_music_id"] = music_id
    recent = [x for x in state.get("recent_signatures", []) if x != signature]
    recent.append(signature)
    state["recent_signatures"] = recent[-120:]

    if len(state["published"]) > 400:
        for key in sorted(state["published"])[:-400]:
            state["published"].pop(key, None)
