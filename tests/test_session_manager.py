"""Tests for SessionManager."""
from unittest.mock import MagicMock
import pytest

from orchestra.server.session_manager import SessionManager
from orchestra.models.presenter import Presenter
from orchestra.models.timeline import Timeline
from orchestra.models.block import Block


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_timeline_with_presenters():
    tl = Timeline.create("T")
    p1 = Presenter.create("Alice", "#E74C3C")
    p2 = Presenter.create("Bob", "#3498DB")
    tl.add_presenter(p1)
    tl.add_presenter(p2)
    b = Block.create(p1.id, 1, 5, 60.0)
    tl.add_block(b)
    return tl, p1, p2


def _mock_socketio():
    sio = MagicMock()
    sio.server = MagicMock()
    return sio


# ---------------------------------------------------------------------------
# Always use fresh SessionManager instances (not the module singleton)
# ---------------------------------------------------------------------------

class TestSessionManager:

    def setup_method(self):
        self.mgr = SessionManager()
        self.sio = _mock_socketio()
        self.mgr.set_socketio(self.sio)

    def test_initial_state(self):
        assert self.mgr.get_connected_presenter_ids() == []

    def test_register_success(self):
        tl, p1, _ = _make_timeline_with_presenters()
        ok, err = self.mgr.register("sid1", p1.id, tl)
        assert ok is True
        assert err == ""

    def test_register_sets_connected(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        assert self.mgr.is_connected(p1.id)

    def test_register_joins_rooms(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        self.sio.server.enter_room.assert_any_call("sid1", f"presenter:{p1.id}")
        self.sio.server.enter_room.assert_any_call("sid1", "session:all")

    def test_register_duplicate_rejected(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        ok, err = self.mgr.register("sid2", p1.id, tl)
        assert ok is False
        assert err == "presenter_already_connected"

    def test_register_unknown_presenter_rejected(self):
        tl, _, _ = _make_timeline_with_presenters()
        ok, err = self.mgr.register("sid1", "nonexistent-id", tl)
        assert ok is False
        assert err == "unknown_presenter_id"

    def test_register_no_timeline_allows_any(self):
        """When no timeline is loaded, registration is allowed (pre-session join)."""
        ok, err = self.mgr.register("sid1", "any-id", None)
        assert ok is True

    def test_unregister(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        pid = self.mgr.unregister("sid1")
        assert pid == p1.id
        assert not self.mgr.is_connected(p1.id)
        assert self.mgr.get_presenter_id("sid1") is None

    def test_unregister_unknown_returns_none(self):
        pid = self.mgr.unregister("no-such-sid")
        assert pid is None

    def test_get_presenter_id(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        assert self.mgr.get_presenter_id("sid1") == p1.id

    def test_get_socket_id(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        assert self.mgr.get_socket_id(p1.id) == "sid1"

    def test_get_connected_list(self):
        tl, p1, p2 = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        self.mgr.register("sid2", p2.id, tl)
        ids = self.mgr.get_connected_presenter_ids()
        assert set(ids) == {p1.id, p2.id}

    def test_reset(self):
        tl, p1, p2 = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        self.mgr.register("sid2", p2.id, tl)
        self.mgr.reset()
        assert self.mgr.get_connected_presenter_ids() == []

    def test_force_disconnect(self):
        tl, p1, _ = _make_timeline_with_presenters()
        self.mgr.register("sid1", p1.id, tl)
        self.mgr.force_disconnect(p1.id)
        assert not self.mgr.is_connected(p1.id)
        self.sio.server.disconnect.assert_called_once_with("sid1")

    def test_force_disconnect_unknown_is_noop(self):
        self.mgr.force_disconnect("nonexistent")
        self.sio.server.disconnect.assert_not_called()
