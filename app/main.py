from __future__ import annotations

import argparse
import json

from app.config import ROOT, music_config, profile
from app.content import build_copy
from app.music import choose_track, ensure_music_library
from app.render import render_reel
from app.state import DueSlot, load_state, mark_published, next_due_slot, save_state


def _forced_slot(slot_id: str) -> DueSlot:
    date_text = slot_id.rsplit("-", 1)[0]
    index = int(slot_id.rsplit("-", 1)[1]) - 1
    return DueSlot(
        slot_id=slot_id,
        local_date=date_text,
        slot_index=index,
        scheduled_time="forced",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--render-only",
        action="store_true",
        help="render the next/forced slot without publishing",
    )
    parser.add_argument("--force-slot", help="force a slot id such as 2026-09-18-1")
    args = parser.parse_args()

    cfg = profile()
    if not cfg["account"].get("enabled", False):
        print("automation disabled in config/profile.yml")
        return 0

    state_path = ROOT / "state" / "posted.json"
    state = load_state(state_path)
    slot = _forced_slot(args.force_slot) if args.force_slot else next_due_slot(cfg, state)
    if slot is None:
        print("no reel is due right now")
        return 0
    if slot.slot_id in state["published"] and not args.render_only:
        print(f"slot already published: {slot.slot_id}")
        return 0

    copy = build_copy(cfg, slot.slot_id, state.get("recent_signatures", []))
    library = ensure_music_library(music_config(), ROOT / ".cache" / "music")
    track = choose_track(
        library,
        mood=copy.mood,
        slot_id=slot.slot_id,
        last_music_id=state.get("last_music_id"),
    )
    render = render_reel(
        copy=copy,
        music=track,
        slot_id=slot.slot_id,
        duration_seconds=int(cfg["account"].get("reel_seconds", 12)),
        out_dir=ROOT / "output",
    )

    if args.render_only:
        print(
            json.dumps(
                {
                    "status": "rendered",
                    "slot": slot.slot_id,
                    "video": str(render.video),
                    "cover": str(render.cover),
                    "music": track.id,
                    "style": render.style_name,
                    "caption": copy.caption,
                },
                indent=2,
            )
        )
        return 0

    from app.publish import publish_reel

    result = publish_reel(
        video=render.video,
        slot_id=slot.slot_id,
        caption=copy.caption,
        share_to_feed=bool(cfg["account"].get("share_to_feed", True)),
    )
    mark_published(
        state,
        slot=slot,
        buffer_post_id=result.buffer_post_id,
        music_id=track.id,
        signature=copy.signature,
        media_url=result.media_url,
    )
    save_state(state_path, state)
    print(
        json.dumps(
            {
                "status": "published",
                "slot": slot.slot_id,
                "buffer_post_id": result.buffer_post_id,
                "music": track.id,
                "style": render.style_name,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
