from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import settings


def data_dir() -> Path:
    return Path(settings.data_dir)


def readings_cache_dir() -> Path:
    path = data_dir() / "readings_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def tts_cache_dir() -> Path:
    path = data_dir() / "tts_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_cache_dirs() -> tuple[Path, Path]:
    return readings_cache_dir(), tts_cache_dir()


def seed_readings_cache_if_empty(seed_source: Path | None = None) -> None:
    """
    Seed readings cache with bundled JSON files on first run.
    This keeps /readings working in fresh Fly volumes.
    """
    target = readings_cache_dir()

    has_seed_data = any(target.glob("month-*.json")) and (target / "latest.json").exists()
    if has_seed_data:
        return

    source = seed_source or Path("app/data")
    if not source.exists():
        return

    for item in source.glob("month-*.json"):
        destination = target / item.name
        if not destination.exists():
            shutil.copy2(item, destination)

    latest_src = source / "latest.json"
    latest_dst = target / "latest.json"
    if latest_src.exists() and not latest_dst.exists():
        shutil.copy2(latest_src, latest_dst)
