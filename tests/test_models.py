"""Tests for orchestra data models."""
import pytest
from orchestra.models.presenter import Presenter
from orchestra.models.vibration import VibrationEvent
from orchestra.models.block import Block, EndCondition, OverrunBehavior
from orchestra.models.timeline import Timeline


# ---------------------------------------------------------------------------
# Presenter
# ---------------------------------------------------------------------------

class TestPresenter:

    def test_create(self):
        p = Presenter.create("Alice", "#E74C3C")
        assert p.name == "Alice"
        assert p.color == "#E74C3C"
        assert p.id  # non-empty UUID

    def test_roundtrip(self):
        p = Presenter.create("Bob", "#3498DB")
        assert Presenter.from_dict(p.to_dict()) == p


# ---------------------------------------------------------------------------
# VibrationEvent
# ---------------------------------------------------------------------------

class TestVibrationEvent:

    def test_short_pattern(self):
        v = VibrationEvent.create("2 min warning", 120.0, "short")
        assert v.type == "short"
        assert v.seconds_before_end == 120.0

    def test_roundtrip(self):
        v = VibrationEvent.create("Last 30s", 30.0, "long")
        assert VibrationEvent.from_dict(v.to_dict()) == v


# ---------------------------------------------------------------------------
# Block
# ---------------------------------------------------------------------------

class TestBlock:

    def _make_block(self, presenter_id="pid1"):
        return Block.create(
            presenter_id=presenter_id,
            slide_start=1,
            slide_end=5,
            duration=300.0,
        )

    def test_defaults(self):
        b = self._make_block()
        assert b.end_condition == EndCondition.EITHER
        assert b.overrun_behavior == OverrunBehavior.AUTO_ADVANCE
        assert b.vibrations == []
        assert b.notes == ""
        assert b.start_time == 0.0

    def test_roundtrip(self):
        b = self._make_block()
        v = VibrationEvent.create("warning", 60.0, "short")
        b.vibrations.append(v)
        b2 = Block.from_dict(b.to_dict())
        assert b2.id == b.id
        assert b2.slide_start == 1
        assert b2.slide_end == 5
        assert b2.duration == 300.0
        assert len(b2.vibrations) == 1
        assert b2.vibrations[0].label == "warning"


# ---------------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------------

class TestTimeline:

    def _make_timeline(self):
        tl = Timeline.create("Test Timeline")
        p1 = Presenter.create("Alice", "#E74C3C")
        p2 = Presenter.create("Bob", "#3498DB")
        tl.add_presenter(p1)
        tl.add_presenter(p2)

        b1 = Block.create(p1.id, 1, 5, 300.0)
        b2 = Block.create(p2.id, 6, 10, 240.0)
        b3 = Block.create(p1.id, 11, 15, 180.0)
        tl.add_block(b1)
        tl.add_block(b2)
        tl.add_block(b3)
        return tl, p1, p2

    def test_start_times_recomputed_on_add(self):
        tl, p1, p2 = self._make_timeline()
        assert tl.blocks[0].start_time == 0.0
        assert tl.blocks[1].start_time == 300.0
        assert tl.blocks[2].start_time == 540.0

    def test_total_duration(self):
        tl, _, _ = self._make_timeline()
        assert tl.total_duration == 720.0

    def test_remove_block_recomputes(self):
        tl, p1, p2 = self._make_timeline()
        block_id = tl.blocks[0].id
        tl.remove_block(block_id)
        assert len(tl.blocks) == 2
        assert tl.blocks[0].start_time == 0.0
        assert tl.blocks[1].start_time == 240.0

    def test_remove_presenter_removes_blocks(self):
        tl, p1, p2 = self._make_timeline()
        tl.remove_presenter(p1.id)
        assert len(tl.presenters) == 1
        assert all(b.presenter_id == p2.id for b in tl.blocks)

    def test_roundtrip(self):
        tl, _, _ = self._make_timeline()
        v = VibrationEvent.create("warning", 60.0, "short")
        tl.blocks[0].vibrations.append(v)
        tl2 = Timeline.from_dict(tl.to_dict())
        assert tl2.id == tl.id
        assert tl2.name == tl.name
        assert len(tl2.presenters) == 2
        assert len(tl2.blocks) == 3
        assert len(tl2.blocks[0].vibrations) == 1

    def test_validation_empty_blocks(self):
        tl = Timeline.create("Empty")
        p = Presenter.create("X", "#fff")
        tl.add_presenter(p)
        errors = tl.validate()
        assert any("at least one block" in e for e in errors)

    def test_validation_no_name(self):
        tl = Timeline.create("")
        errors = tl.validate()
        assert any("name" in e.lower() for e in errors)

    def test_validation_passes(self):
        tl, _, _ = self._make_timeline()
        assert tl.validate() == []

    def test_validation_slide_end_before_start(self):
        tl = Timeline.create("T")
        p = Presenter.create("X", "#aaa")
        tl.add_presenter(p)
        b = Block.create(p.id, 5, 3, 60.0)   # slide_end < slide_start
        tl.blocks.append(b)
        errors = tl.validate()
        assert any("slide_end" in e for e in errors)

    def test_duplicate_presenter_raises(self):
        tl = Timeline.create("T")
        p = Presenter.create("X", "#aaa")
        tl.add_presenter(p)
        with pytest.raises(ValueError):
            tl.add_presenter(p)

    def test_add_block_unknown_presenter_raises(self):
        tl = Timeline.create("T")
        b = Block.create("nonexistent-id", 1, 5, 60.0)
        with pytest.raises(ValueError):
            tl.add_block(b)

    def test_move_block(self):
        tl, p1, p2 = self._make_timeline()
        first_id = tl.blocks[0].id
        tl.move_block(first_id, 2)
        assert tl.blocks[2].id == first_id
        # Start times recomputed
        assert tl.blocks[0].start_time == 0.0
