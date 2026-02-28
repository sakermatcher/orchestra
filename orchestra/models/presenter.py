"""Presenter data model."""
from __future__ import annotations
from dataclasses import dataclass
import uuid


@dataclass
class Presenter:
    id: str
    name: str
    color: str  # hex color, e.g. '#E74C3C'

    @classmethod
    def create(cls, name: str, color: str) -> "Presenter":
        return cls(id=str(uuid.uuid4()), name=name, color=color)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "color": self.color}

    @classmethod
    def from_dict(cls, d: dict) -> "Presenter":
        return cls(id=d["id"], name=d["name"], color=d["color"])
