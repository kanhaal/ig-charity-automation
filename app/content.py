from __future__ import annotations

from dataclasses import dataclass
import hashlib
import random


@dataclass(frozen=True)
class ReelCopy:
    hook: str
    body: str
    cta: str
    caption: str
    mood: str
    signature: str


HOOKS = [
    "please stop scrolling for 10 seconds.",
    "if you can spare 10 seconds, please read this.",
    "please read this before you scroll away.",
    "I know everyone has problems, but please hear me out.",
    "I never thought I'd make a page like this.",
    "this is difficult to write, but I need to try.",
    "I don't expect everyone to donate. Please just read this.",
    "even one share could help this reach the right person.",
    "some days everything feels too heavy, but I'm still trying.",
    "I'm asking for a little understanding, not a miracle.",
    "if this reaches the right person, it could genuinely help.",
    "I almost didn't post this, but I don't know what else to do.",
]

RECIPES = [
    ("sad", ["student", "finances", "education"]),
    ("vulnerable", ["student", "mother_health", "education"]),
    ("reflective", ["finances", "father", "intent"]),
    ("vulnerable", ["wellbeing", "education", "intent"]),
    ("sad", ["mother_health", "finances", "intent"]),
    ("calm", ["student", "education", "intent"]),
    ("hopeful", ["education", "student", "intent"]),
    ("reflective", ["student", "father", "education"]),
]

BRIDGES = [
    "I'm trying to keep showing up for my studies even when things at home feel overwhelming.",
    "I don't have a perfect way to explain everything, but this is what life feels like right now.",
    "I'm doing my best to stay focused even when family stress keeps following me into my studies.",
    "I'm trying to protect my future through education while also carrying everything happening at home.",
    "This page is my attempt to keep going without pretending everything is fine.",
]

CTA_TEMPLATES = [
    "If you can help in any small way, the Razorpay link is in my bio. If you can't donate, please consider sharing this instead.",
    "If you're able to help, even a small amount would mean a lot. The Razorpay link is in my bio. Sharing also helps.",
    "If you want to support me, the Razorpay link is in my bio. Even one share can help this reach someone who can donate.",
    "If you're in a position to help, the Razorpay link is in my bio. If not, sharing this page still helps a lot.",
]

CAPTION_OPENERS = [
    "Thank you for taking the time to read this.",
    "I'm trying to keep this page honest and simple.",
    "Posting this isn't easy, but staying silent isn't helping either.",
    "I don't expect help from everyone who sees this.",
    "Every share gives this page another chance to reach someone who can help.",
]


def _rng(slot_id: str) -> random.Random:
    seed = int(hashlib.sha256(slot_id.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def _compose_body(
    facts: dict,
    recipe_keys: list[str],
    rng: random.Random,
) -> str:
    selected = [facts[key] for key in recipe_keys]
    bridge = rng.choice(BRIDGES)

    # Keep the on-screen copy readable. The full story remains available in the
    # caption, while the Reel uses only three fact statements plus one bridge.
    return " ".join([selected[0], bridge, selected[1], selected[2]])


def build_copy(
    profile_cfg: dict,
    slot_id: str,
    recent_signatures: list[str],
) -> ReelCopy:
    facts = profile_cfg["approved_facts"]
    cta_cfg = profile_cfg["cta"]
    hashtags = " ".join(f"#{tag}" for tag in profile_cfg.get("hashtags", []))
    rng = _rng(slot_id)

    combinations: list[tuple[int, int]] = []
    for hook_idx in range(len(HOOKS)):
        for recipe_idx in range(len(RECIPES)):
            combinations.append((hook_idx, recipe_idx))
    rng.shuffle(combinations)

    chosen = combinations[0]
    signature = ""
    for hook_idx, recipe_idx in combinations:
        signature = f"h{hook_idx}-r{recipe_idx}"
        if signature not in recent_signatures:
            chosen = (hook_idx, recipe_idx)
            break

    hook_idx, recipe_idx = chosen
    mood, recipe_keys = RECIPES[recipe_idx]
    body = _compose_body(facts, recipe_keys, rng)
    cta = rng.choice(CTA_TEMPLATES)

    caption = (
        f"{rng.choice(CAPTION_OPENERS)}\n\n"
        f"{cta_cfg['donation']}\n"
        f"{cta_cfg['share']}\n\n"
        f"{hashtags}"
    ).strip()

    return ReelCopy(
        hook=HOOKS[hook_idx],
        body=body,
        cta=cta,
        caption=caption,
        mood=mood,
        signature=signature,
    )
