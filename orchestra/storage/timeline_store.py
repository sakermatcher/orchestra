"""
Timeline store — CRUD operations on timeline JSON files.

Each timeline is stored as data/timelines/<uuid>.json.
Operations are synchronous (called from Qt main thread or engine).
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Optional

from orchestra.models.timeline import Timeline
from orchestra.storage.config_store import get_timelines_dir


class TimelineNotFoundError(Exception):
    pass


def _timeline_path(timeline_id: str) -> Path:
    return get_timelines_dir() / f"{timeline_id}.json"


def save_timeline(timeline: Timeline) -> None:
    """Persist a timeline. Creates or overwrites the file."""
    timeline.recompute_start_times()
    timeline.touch()
    path = _timeline_path(timeline.id)
    with path.open("w", encoding="utf-8") as f:
        json.dump(timeline.to_dict(), f, indent=2, ensure_ascii=False)


def load_timeline(timeline_id: str) -> Timeline:
    """Load a timeline by ID. Raises TimelineNotFoundError if missing."""
    path = _timeline_path(timeline_id)
    if not path.exists():
        raise TimelineNotFoundError(f"Timeline {timeline_id!r} not found at {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return Timeline.from_dict(data)


def list_timelines() -> List[Timeline]:
    """Return all timelines, sorted by updated_at descending (most recent first)."""
    timelines_dir = get_timelines_dir()
    timelines = []
    for path in timelines_dir.glob("*.json"):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            timelines.append(Timeline.from_dict(data))
        except Exception:
            # Skip corrupt files silently — they will be visible as missing in the UI
            pass
    timelines.sort(key=lambda t: t.updated_at, reverse=True)
    return timelines


def delete_timeline(timeline_id: str) -> None:
    """Delete a timeline file. Silent if it does not exist."""
    path = _timeline_path(timeline_id)
    if path.exists():
        path.unlink()
