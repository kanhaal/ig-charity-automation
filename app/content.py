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
    "please stop scrolling for a few seconds.",
    "if you can spare 10 seconds, please read this.",
    "I almost didn't post this, but I need to try.",
    "this is difficult to write, but I don't know what else to do.",
    "one share could put this in front of the right person.",
    "I know everyone has their own problems, but please hear me out.",
    "I'm trying to keep going without giving up on my studies.",
    "I don't expect everyone to donate. I just hope someone reads this.",
    "please read this before you scroll away.",
    "I'm asking for a little understanding, not a miracle.",
    "some days everything feels too heavy, but I'm still trying.",
    "I never thought I'd make a page like this.",
]

RECIPES = [
    ("vulnerable", ["student", "finances", "education"]),
    ("sad", ["student", "mother_health", "education"]),
    ("reflective", ["finances", "father", "intent"]),
    ("vulnerable", ["wellbeing", "student", "education"]),
    ("sad", ["mother_health", "finances", "intent"]),
    ("reflective", ["student", "father", "education"]),
    ("calm", ["student", "intent", "education"]),
    ("hopeful", ["education", "intent", "student"]),
]

BRIDGES = [
    "Right now, I'm trying to handle all of this while still showing up for school.",
    "I'm doing my best to stay focused, even when home and studies both feel overwhelming.",
    "I don't have a perfect solution; I'm just trying to keep moving forward one day at a time.",
    "I know a post can't explain everything, but this is the reality I'm trying to manage right now.",
    "I'm still trying to protect my education and be useful to my family at the same time.",
]

CTA_TEMPLATES = [
    "If you're able to help, even a small amount would mean a lot. The Razorpay link is in my bio. If donating isn't possible, a share still helps.",
    "If you want to support me, the Razorpay link is in my bio. Even sharing this page can help it reach someone who is able to donate.",
    "If you can help in any small way, the Razorpay link is in my bio. If you can't donate, please consider sharing this instead.",
    "Any support is appreciated, but there is no pressure to donate. The Razorpay link is in my bio, and sharing the page helps too.",
    "If you're in a position to help, the Razorpay link is in my bio. A donation or even a simple share can make a difference to this page.",
]

CAPTION_OPENERS = [
    "Thank you for taking the time to read this.",
    "I'm trying to keep this page honest and simple.",
    "I don't expect help from everyone who sees this.",
    "Posting this is uncomfortable, but staying silent isn't helping either.",
    "Every share gives this page another chance to reach someone who can help.",
]


def _rng(slot_id: str) -> random.Random:
    seed = int(hashlib.sha256(slot_id.encode("utf-8")).hexdigest()[:16], 16)
    return random.Random(seed)


def build_copy(profile_cfg: dict, slot_id: str, recent_signatures: list[str]) -> ReelCopy:
    facts = profile_cfg["approved_facts"]
    cta_cfg = profile_cfg["cta"]
    hashtags = " ".join(f"#{tag}" for tag in profile_cfg.get("hashtags", []))
    rng = _rng(slot_id)

    combinations = []
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
    mood, fact_ids = RECIPES[recipe_idx]
    selected = [facts[key] for key in fact_ids]
    bridge = rng.choice(BRIDGES)
    body = " ".join([selected[0], bridge, *selected[1:]])

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
