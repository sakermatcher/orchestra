"""Timeline data model — the root aggregate."""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
import uuid

from orchestra.models.presenter import Presenter
from orchestra.models.block import Block


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Timeline:
    id: str
    name: str
    presentation_file_path: str   # Absolute path to .pptx (may be empty string if not yet set)
    created_at: str               # ISO 8601
    updated_at: str               # ISO 8601
    presenters: List[Presenter]
    blocks: List[Block]

    SCHEMA_VERSION = 1

    @classmethod
    def create(cls, name: str, presentation_file_path: str = "") -> "Timeline":
        now = _utcnow()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            presentation_file_path=presentation_file_path,
            created_at=now,
            updated_at=now,
            presenters=[],
            blocks=[],
        )

    # ------------------------------------------------------------------
    # Presenter helpers
    # ------------------------------------------------------------------

    def get_presenter(self, presenter_id: str) -> Optional[Presenter]:
        for p in self.presenters:
            if p.id == presenter_id:
                return p
        return None

    def add_presenter(self, presenter: Presenter) -> None:
        if self.get_presenter(presenter.id) is not None:
            raise ValueError(f"Presenter {presenter.id} already exists")
        self.presenters.append(presenter)
        self.touch()

    def remove_presenter(self, presenter_id: str) -> None:
        self.presenters = [p for p in self.presenters if p.id != presenter_id]
        # Blocks belonging to removed presenter are also removed
        self.blocks = [b for b in self.blocks if b.presenter_id != presenter_id]
        self.recompute_start_times()
        self.touch()

    # ------------------------------------------------------------------
    # Block helpers
    # ------------------------------------------------------------------

    def get_block(self, block_id: str) -> Optional[Block]:
        for b in self.blocks:
            if b.id == block_id:
                return b
        return None

    def add_block(self, block: Block) -> None:
        if self.get_presenter(block.presenter_id) is None:
            raise ValueError(f"Unknown presenter_id {block.presenter_id}")
        self.blocks.append(block)
        self.recompute_start_times()
        self.touch()

    def remove_block(self, block_id: str) -> None:
        self.blocks = [b for b in self.blocks if b.id != block_id]
        self.recompute_start_times()
        self.touch()

    def move_block(self, block_id: str, new_index: int) -> None:
        """Reorder a block to a new position in the sequential list."""
        block = self.get_block(block_id)
        if block is None:
            raise ValueError(f"Block {block_id} not found")
        self.blocks.remove(block)
        new_index = max(0, min(new_index, len(self.blocks)))
        self.blocks.insert(new_index, block)
        self.recompute_start_times()
        self.touch()

    def recompute_start_times(self) -> None:
        """Recompute all block start_time values from the ordered block list."""
        t = 0.0
        for block in self.blocks:
            block.start_time = t
            t += block.duration

    @property
    def total_duration(self) -> float:
        return sum(b.duration for b in self.blocks)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Return a list of validation error strings. Empty list means valid."""
        errors: list[str] = []
        if not self.name.strip():
            errors.append("Timeline must have a name.")
        if not self.blocks:
            errors.append("Timeline must have at least one block.")
        presenter_ids = {p.id for p in self.presenters}
        for i, block in enumerate(self.blocks):
            prefix = f"Block {i + 1}"
            if block.presenter_id not in presenter_ids:
                errors.append(f"{prefix}: references unknown presenter {block.presenter_id}")
            if block.slide_start < 1:
                errors.append(f"{prefix}: slide_start must be >= 1")
            if block.slide_end < block.slide_start:
                errors.append(f"{prefix}: slide_end must be >= slide_start")
            if block.duration < 1.0:
                errors.append(f"{prefix}: duration must be >= 1 second")
        return errors

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def touch(self) -> None:
        self.updated_at = _utcnow()

    def to_dict(self) -> dict:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "id": self.id,
            "name": self.name,
            "presentation_file_path": self.presentation_file_path,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "presenters": [p.to_dict() for p in self.presenters],
            "blocks": [b.to_dict() for b in self.blocks],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Timeline":
        return cls(
            id=d["id"],
            name=d["name"],
            presentation_file_path=d.get("presentation_file_path", ""),
            created_at=d.get("created_at", _utcnow()),
            updated_at=d.get("updated_at", _utcnow()),
            presenters=[Presenter.from_dict(p) for p in d.get("presenters", [])],
            blocks=[Block.from_dict(b) for b in d.get("blocks", [])],
        )
