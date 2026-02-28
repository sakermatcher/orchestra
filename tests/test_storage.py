"""Tests for orchestra storage layer."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestra.models.presenter import Presenter
from orchestra.models.block import Block
from orchestra.models.timeline import Timeline
from orchestra.storage.timeline_store import TimelineNotFoundError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_timeline(name="Test") -> Timeline:
    tl = Timeline.create(name)
    p = Presenter.create("Alice", "#E74C3C")
    tl.add_presenter(p)
    b = Block.create(p.id, 1, 5, 300.0)
    tl.add_block(b)
    return tl


# ---------------------------------------------------------------------------
# timeline_store tests
# ---------------------------------------------------------------------------

class TestTimelineStore:

    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.timelines_dir = Path(self.tmpdir.name) / "timelines"
        self.timelines_dir.mkdir()

    def teardown_method(self):
        self.tmpdir.cleanup()

    def _patch(self):
        """Patch get_timelines_dir in timeline_store to use our temp dir."""
        return patch("orchestra.storage.timeline_store.get_timelines_dir",
                     return_value=self.timelines_dir)

    def test_save_creates_file(self):
        from orchestra.storage.timeline_store import save_timeline
        tl = _make_timeline()
        with self._patch():
            save_timeline(tl)
        assert (self.timelines_dir / f"{tl.id}.json").exists()

    def test_save_and_load_roundtrip(self):
        from orchestra.storage.timeline_store import save_timeline, load_timeline
        tl = _make_timeline()
        with self._patch():
            save_timeline(tl)
            loaded = load_timeline(tl.id)
        assert loaded.id == tl.id
        assert loaded.name == tl.name
        assert len(loaded.presenters) == 1
        assert len(loaded.blocks) == 1

    def test_load_nonexistent_raises(self):
        from orchestra.storage.timeline_store import load_timeline
        with self._patch():
            with pytest.raises(TimelineNotFoundError):
                load_timeline("does-not-exist")

    def test_list_returns_timeline_objects(self):
        from orchestra.storage.timeline_store import save_timeline, list_timelines
        tl1 = _make_timeline("Alpha")
        tl2 = _make_timeline("Beta")
        with self._patch():
            save_timeline(tl1)
            save_timeline(tl2)
            items = list_timelines()
        assert len(items) == 2
        assert all(isinstance(t, Timeline) for t in items)
        ids = {t.id for t in items}
        assert tl1.id in ids
        assert tl2.id in ids

    def test_list_sorted_by_updated_at_desc(self):
        import time
        from orchestra.storage.timeline_store import save_timeline, list_timelines
        tl1 = _make_timeline("First")
        time.sleep(0.02)   # Ensure distinct timestamps
        tl2 = _make_timeline("Second")
        with self._patch():
            save_timeline(tl1)
            save_timeline(tl2)
            items = list_timelines()
        # Most recently updated (tl2) should be first
        assert items[0].name == "Second"

    def test_delete_timeline(self):
        from orchestra.storage.timeline_store import save_timeline, delete_timeline
        tl = _make_timeline()
        with self._patch():
            save_timeline(tl)
            assert (self.timelines_dir / f"{tl.id}.json").exists()
            delete_timeline(tl.id)
            assert not (self.timelines_dir / f"{tl.id}.json").exists()

    def test_delete_nonexistent_is_silent(self):
        from orchestra.storage.timeline_store import delete_timeline
        with self._patch():
            delete_timeline("nonexistent")   # Should not raise

    def test_save_recomputes_start_times(self):
        from orchestra.storage.timeline_store import save_timeline, load_timeline
        tl = _make_timeline()
        # Corrupt start time manually
        tl.blocks[0].start_time = 999.0
        with self._patch():
            save_timeline(tl)
            loaded = load_timeline(tl.id)
        assert loaded.blocks[0].start_time == 0.0


# ---------------------------------------------------------------------------
# config_store tests
# ---------------------------------------------------------------------------

class TestConfigStore:

    def setup_method(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.tmpdir.name)

    def teardown_method(self):
        self.tmpdir.cleanup()

    def _patch(self):
        """Patch get_data_dir in config_store to use our temp dir."""
        return patch("orchestra.storage.config_store.get_data_dir",
                     return_value=self.data_dir)

    def test_load_defaults_when_config_missing(self):
        from orchestra.storage.config_store import load_config, _DEFAULT_CONFIG
        with self._patch():
            cfg = load_config()
        for key in _DEFAULT_CONFIG:
            assert key in cfg

    def test_save_and_reload(self):
        from orchestra.storage.config_store import load_config, save_config
        with self._patch():
            cfg = load_config()
            cfg["server_port"] = 9999
            save_config(cfg)
            cfg2 = load_config()
        assert cfg2["server_port"] == 9999

    def test_partial_file_merged_with_defaults(self):
        from orchestra.storage.config_store import load_config, _DEFAULT_CONFIG
        cfg_file = self.data_dir / "config.json"
        cfg_file.write_text(json.dumps({"server_port": 8080}), encoding="utf-8")
        with self._patch():
            cfg = load_config()
        assert cfg["server_port"] == 8080
        # All default keys still present
        for key in _DEFAULT_CONFIG:
            assert key in cfg

    def test_default_config_has_expected_keys(self):
        from orchestra.storage.config_store import _DEFAULT_CONFIG
        assert "server_port" in _DEFAULT_CONFIG
        assert "server_host" in _DEFAULT_CONFIG
        assert "auto_detect_ip" in _DEFAULT_CONFIG
        assert "timer_broadcast_interval_ms" in _DEFAULT_CONFIG
