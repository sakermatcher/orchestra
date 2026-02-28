"""
ActiveSession — in-memory session state snapshot.

Created when a session starts. Copied to disk (session_recovery.json) for
crash recovery. Immutable once created except for per-block state updates.
"""
from __future__ import annotations
import copy
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

from orchestra.models.timeline import Timeline


@dataclass
class BlockState:
    block_id: str
    state: str = "pending"              # pending | active | completed | skipped
    actual_start_epoch: float = 0.0    # time.time() when block activated
    actual_end_epoch: Optional[float] = None
    overrun_seconds: float = 0.0
    vibrations_fired: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "block_id": self.block_id,
            "state": self.state,
            "actual_start_epoch": self.actual_start_epoch,
            "actual_end_epoch": self.actual_end_epoch,
            "overrun_seconds": self.overrun_seconds,
            "vibrations_fired": list(self.vibrations_fired),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BlockState":
        return cls(
            block_id=d["block_id"],
            state=d.get("state", "pending"),
            actual_start_epoch=float(d.get("actual_start_epoch", 0)),
            actual_end_epoch=d.get("actual_end_epoch"),
            overrun_seconds=float(d.get("overrun_seconds", 0)),
            vibrations_fired=list(d.get("vibrations_fired", [])),
        )


@dataclass
class ActiveSession:
    id: str
    timeline: Timeline                 # full snapshot at session start (immutable)
    state: str                         # mirrors EngineState string
    started_at: str                    # ISO8601
    session_elapsed_seconds: float
    current_block_index: int
    block_states: List[BlockState]

    # Not persisted — monotonic clock reference for accurate timing
    block_start_monotonic: float = field(default_factory=time.monotonic)
    pause_start_monotonic: Optional[float] = field(default=None)
    total_paused_monotonic: float = field(default=0.0)

    @classmethod
    def create(cls, timeline: Timeline) -> "ActiveSession":
        from datetime import datetime, timezone
        now_iso = datetime.now(timezone.utc).isoformat()
        timeline_copy = Timeline.from_dict(timeline.to_dict())
        return cls(
            id=str(uuid.uuid4()),
            timeline=timeline_copy,
            state="warmup",
            started_at=now_iso,
            session_elapsed_seconds=0.0,
            current_block_index=0,
            block_states=[
                BlockState(block_id=b.id) for b in timeline_copy.blocks
            ],
        )

    @property
    def current_block_state(self) -> Optional[BlockState]:
        if 0 <= self.current_block_index < len(self.block_states):
            return self.block_states[self.current_block_index]
        return None

    @property
    def current_block(self):
        t = self.timeline
        if 0 <= self.current_block_index < len(t.blocks):
            return t.blocks[self.current_block_index]
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timeline_id": self.timeline.id,
            "timeline_snapshot": self.timeline.to_dict(),
            "state": self.state,
            "started_at": self.started_at,
            "session_elapsed_seconds": self.session_elapsed_seconds,
            "current_block_index": self.current_block_index,
            "block_states": [bs.to_dict() for bs in self.block_states],
        }
