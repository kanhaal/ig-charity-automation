from __future__ import annotations

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def profile() -> dict:
    return load_yaml(ROOT / "config" / "profile.yml")


def music_config() -> dict:
    return load_yaml(ROOT / "config" / "music.yml")
