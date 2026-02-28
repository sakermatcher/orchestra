"""Block data model."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List
import uuid

from orchestra.models.vibration import VibrationEvent


class EndCondition(str, Enum):
    TIME = "time"
    CLICK = "click"
    EITHER = "either"


class OverrunBehavior(str, Enum):
    AUTO_ADVANCE = "auto_advance"
    ALERT_ONLY = "alert_only"


@dataclass
class Block:
    """
    A single sequential presentation segment.

    start_time is derived from block order and stored for fast reading.
    It is recomputed by Timeline.recompute_start_times() on every mutation.
    """
    id: str
    presenter_id: str
    slide_start: int           # 1-indexed
    slide_end: int             # 1-indexed, inclusive
    start_time: float          # seconds from session start (derived, stored for reads)
    duration: float            # seconds
    end_condition: EndCondition
    overrun_behavior: OverrunBehavior
    notes: str
    vibrations: List[VibrationEvent]

    @classmethod
    def create(
        cls,
        presenter_id: str,
        slide_start: int,
        slide_end: int,
        duration: float,
        end_condition: EndCondition = EndCondition.EITHER,
        overrun_behavior: OverrunBehavior = OverrunBehavior.AUTO_ADVANCE,
        notes: str = "",
    ) -> "Block":
        return cls(
            id=str(uuid.uuid4()),
            presenter_id=presenter_id,
            slide_start=slide_start,
            slide_end=slide_end,
            start_time=0.0,
            duration=duration,
            end_condition=end_condition,
            overrun_behavior=overrun_behavior,
            notes=notes,
            vibrations=[],
        )

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "presenter_id": self.presenter_id,
            "slide_start": self.slide_start,
            "slide_end": self.slide_end,
            "start_time": self.start_time,
            "duration": self.duration,
            "end_condition": self.end_condition.value,
            "overrun_behavior": self.overrun_behavior.value,
            "notes": self.notes,
            "vibrations": [v.to_dict() for v in self.vibrations],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Block":
        return cls(
            id=d["id"],
            presenter_id=d["presenter_id"],
            slide_start=int(d["slide_start"]),
            slide_end=int(d["slide_end"]),
            start_time=float(d.get("start_time", 0.0)),
            duration=float(d["duration"]),
            end_condition=EndCondition(d.get("end_condition", "either")),
            overrun_behavior=OverrunBehavior(d.get("overrun_behavior", "auto_advance")),
            notes=d.get("notes", ""),
            vibrations=[VibrationEvent.from_dict(v) for v in d.get("vibrations", [])],
        )
