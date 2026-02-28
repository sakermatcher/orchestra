"""Vibration event data model."""
from __future__ import annotations
from dataclasses import dataclass, field
import uuid


@dataclass
class VibrationEvent:
    """
    A haptic alert scheduled relative to a block's end time.

    seconds_before_end: positive means fire X seconds before block ends.
    type: 'short' (200ms buzz) or 'long' (500ms buzz).
    """
    id: str
    label: str
    seconds_before_end: float
    type: str  # 'short' | 'long'

    def __post_init__(self):
        if self.type not in ("short", "long"):
            raise ValueError(f"VibrationEvent.type must be 'short' or 'long', got {self.type!r}")
        if self.seconds_before_end < 0:
            raise ValueError("seconds_before_end must be non-negative")

    @classmethod
    def create(cls, label: str, seconds_before_end: float, vtype: str) -> "VibrationEvent":
        return cls(id=str(uuid.uuid4()), label=label,
                   seconds_before_end=seconds_before_end, type=vtype)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "seconds_before_end": self.seconds_before_end,
            "type": self.type,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "VibrationEvent":
        return cls(
            id=d["id"],
            label=d.get("label", ""),
            seconds_before_end=float(d["seconds_before_end"]),
            type=d["type"],
        )

    @property
    def pattern_ms(self) -> list[int]:
        from orchestra.constants import VIBRATION_SHORT_PATTERN_MS, VIBRATION_LONG_PATTERN_MS
        return VIBRATION_SHORT_PATTERN_MS if self.type == "short" else VIBRATION_LONG_PATTERN_MS
