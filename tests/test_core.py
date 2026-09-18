from datetime import datetime
from zoneinfo import ZoneInfo

from app.content import build_copy
from app.state import next_due_slot


PROFILE = {
    "account": {
        "timezone": "Asia/Kolkata",
        "posting_times": ["11:37", "20:07"],
    },
    "approved_facts": {
        "student": "student fact",
        "finances": "finance fact",
        "father": "father fact",
        "mother_health": "mother fact",
        "education": "education fact",
        "wellbeing": "wellbeing fact",
        "intent": "intent fact",
    },
    "cta": {"donation": "donation cta", "share": "share cta"},
    "hashtags": ["HelpAStudent"],
}


def test_no_slot_before_first_time():
    now = datetime(2026, 9, 18, 10, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    assert next_due_slot(PROFILE, {"published": {}}, now) is None


def test_morning_slot_is_due_in_morning_window():
    now = datetime(2026, 9, 18, 12, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    slot = next_due_slot(PROFILE, {"published": {}}, now)
    assert slot.slot_id == "2026-09-18-1"


def test_evening_slot_replaces_missed_morning_slot():
    now = datetime(2026, 9, 18, 21, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    slot = next_due_slot(PROFILE, {"published": {}}, now)
    assert slot.slot_id == "2026-09-18-2"


def test_no_duplicate_when_latest_slot_already_published():
    now = datetime(2026, 9, 18, 21, 0, tzinfo=ZoneInfo("Asia/Kolkata"))
    state = {"published": {"2026-09-18-2": {}}}
    assert next_due_slot(PROFILE, state, now) is None


def test_copy_is_deterministic_and_source_locked():
    one = build_copy(PROFILE, "2026-09-18-1", [])
    two = build_copy(PROFILE, "2026-09-18-1", [])
    assert one == two
    assert any(value in one.body for value in PROFILE["approved_facts"].values())
    assert "donation cta" in one.caption
    assert "Razorpay link" in one.cta
