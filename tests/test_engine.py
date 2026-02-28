"""Tests for TimelineEngine state machine."""
from unittest.mock import MagicMock, patch, call
import pytest

from orchestra.engine.state import EngineState
from orchestra.engine.timeline_engine import TimelineEngine
from orchestra.models.presenter import Presenter
from orchestra.models.block import Block, EndCondition
from orchestra.models.timeline import Timeline


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_valid_timeline() -> Timeline:
    tl = Timeline.create("Session Test")
    p = Presenter.create("Alice", "#E74C3C")
    tl.add_presenter(p)
    b = Block.create(p.id, 1, 5, 300.0)
    tl.add_block(b)
    return tl


def _make_engine():
    bridge = MagicMock()
    socketio = MagicMock()
    engine = TimelineEngine(bridge=bridge)
    # Override _relay so callables execute immediately in tests instead of
    # being queued for a Flask/eventlet hub that doesn't exist here.
    engine._relay = lambda fn: fn()
    # Disable the start delay so operator_go() activates synchronously.
    engine._config["presentation_start_delay_seconds"] = 0
    engine.set_socketio(socketio)
    return engine, bridge, socketio


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------

class TestInitialState:

    def test_starts_idle(self):
        engine, _, _ = _make_engine()
        assert engine.state == EngineState.IDLE

    def test_no_timeline(self):
        engine, _, _ = _make_engine()
        assert engine.current_timeline is None

    def test_no_session(self):
        engine, _, _ = _make_engine()
        assert engine.current_session is None

    def test_is_session_not_active(self):
        engine, _, _ = _make_engine()
        assert not engine.is_session_active()


# ---------------------------------------------------------------------------
# Timeline loading
# ---------------------------------------------------------------------------

class TestTimelineLoading:

    def test_load_transitions_to_loaded(self):
        engine, _, _ = _make_engine()
        tl = _make_valid_timeline()
        engine.load_timeline(tl)
        assert engine.state == EngineState.TIMELINE_LOADED

    def test_load_stores_timeline(self):
        engine, _, _ = _make_engine()
        tl = _make_valid_timeline()
        engine.load_timeline(tl)
        assert engine.current_timeline is tl

    def test_load_twice_stays_loaded(self):
        engine, _, _ = _make_engine()
        tl1 = _make_valid_timeline()
        tl2 = _make_valid_timeline()
        engine.load_timeline(tl1)
        engine.load_timeline(tl2)
        assert engine.state == EngineState.TIMELINE_LOADED
        assert engine.current_timeline is tl2


# ---------------------------------------------------------------------------
# Session start
# ---------------------------------------------------------------------------

class TestSessionStart:

    def test_start_without_timeline_does_nothing(self):
        engine, _, _ = _make_engine()
        engine.request_start_session()
        assert engine.state == EngineState.IDLE

    def test_start_transitions_to_warmup(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        assert engine.state == EngineState.WARMUP

    def test_start_creates_session(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        assert engine.current_session is not None

    def test_start_emits_warmup(self):
        engine, _, sio = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        sio.emit.assert_called()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "session:warmup" in event_names

    def test_is_session_active_during_warmup(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        assert engine.is_session_active()


# ---------------------------------------------------------------------------
# operator_go (WARMUP → RUNNING)
# ---------------------------------------------------------------------------

class TestOperatorGo:

    def _warmup(self):
        engine, bridge, sio = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        return engine, bridge, sio

    @patch("orchestra.engine.timeline_engine.BlockRunner")
    @patch("orchestra.engine.timeline_engine.VibrationScheduler")
    def test_go_transitions_to_running(self, mock_vs, mock_br):
        mock_br.return_value = MagicMock()
        mock_vs.return_value = MagicMock()
        engine, _, _ = self._warmup()
        engine.operator_go()
        assert engine.state == EngineState.RUNNING

    @patch("orchestra.engine.timeline_engine.BlockRunner")
    @patch("orchestra.engine.timeline_engine.VibrationScheduler")
    def test_go_emits_started(self, mock_vs, mock_br):
        mock_br.return_value = MagicMock()
        mock_vs.return_value = MagicMock()
        engine, _, sio = self._warmup()
        engine.operator_go()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "session:started" in event_names

    @patch("orchestra.engine.timeline_engine.BlockRunner")
    @patch("orchestra.engine.timeline_engine.VibrationScheduler")
    def test_go_emits_block_activate(self, mock_vs, mock_br):
        mock_br.return_value = MagicMock()
        mock_vs.return_value = MagicMock()
        engine, _, sio = self._warmup()
        engine.operator_go()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "block:activate" in event_names

    def test_go_ignored_if_not_warmup(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.operator_go()  # still in TIMELINE_LOADED, not WARMUP
        assert engine.state == EngineState.TIMELINE_LOADED


# ---------------------------------------------------------------------------
# Pause / Resume
# ---------------------------------------------------------------------------

class TestPauseResume:

    def _running(self):
        engine, bridge, sio = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        with patch("orchestra.engine.timeline_engine.BlockRunner") as mock_br, \
             patch("orchestra.engine.timeline_engine.VibrationScheduler") as mock_vs:
            mock_br.return_value = MagicMock()
            mock_vs.return_value = MagicMock()
            engine.operator_go()
        return engine, bridge, sio

    def test_pause_from_running(self):
        engine, _, _ = self._running()
        engine.toggle_pause()
        assert engine.state == EngineState.PAUSED

    def test_resume_from_paused(self):
        engine, _, _ = self._running()
        engine.toggle_pause()
        engine.toggle_pause()
        assert engine.state == EngineState.RUNNING

    def test_pause_emits_event(self):
        engine, _, sio = self._running()
        sio.reset_mock()
        engine.toggle_pause()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "session:paused" in event_names

    def test_resume_emits_event(self):
        engine, _, sio = self._running()
        engine.toggle_pause()
        sio.reset_mock()
        engine.toggle_pause()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "session:resumed" in event_names


# ---------------------------------------------------------------------------
# Abort
# ---------------------------------------------------------------------------

class TestAbort:

    def test_abort_from_warmup(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        engine.abort_session()
        assert engine.state == EngineState.ABORTED
        assert engine.current_session is None

    def test_abort_emits_event(self):
        engine, _, sio = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        sio.reset_mock()
        engine.abort_session()
        event_names = [c.args[0] for c in sio.emit.call_args_list]
        assert "session:aborted" in event_names

    def test_abort_when_idle_does_nothing(self):
        engine, _, _ = _make_engine()
        engine.abort_session()
        assert engine.state == EngineState.IDLE


# ---------------------------------------------------------------------------
# Session reset
# ---------------------------------------------------------------------------

class TestSessionReset:

    def test_reset_after_abort(self):
        engine, _, _ = _make_engine()
        engine.load_timeline(_make_valid_timeline())
        engine.request_start_session()
        engine.abort_session()
        engine.session_reset()
        assert engine.state == EngineState.TIMELINE_LOADED

    def test_reset_from_idle_does_nothing(self):
        engine, _, _ = _make_engine()
        engine.session_reset()
        assert engine.state == EngineState.IDLE


# ---------------------------------------------------------------------------
# Presenter advance
# ---------------------------------------------------------------------------

class TestPresenterAdvance:

    def _running_click_block(self):
        engine, bridge, sio = _make_engine()
        tl = Timeline.create("Click Test")
        p = Presenter.create("Alice", "#E74C3C")
        tl.add_presenter(p)
        b = Block.create(p.id, 1, 5, 300.0,
                         end_condition=EndCondition.CLICK)
        tl.add_block(b)
        engine.load_timeline(tl)
        engine.request_start_session()
        with patch("orchestra.engine.timeline_engine.BlockRunner") as mock_br, \
             patch("orchestra.engine.timeline_engine.VibrationScheduler") as mock_vs:
            mock_br.return_value = MagicMock()
            mock_vs.return_value = MagicMock()
            engine.operator_go()
        return engine, p

    def test_valid_advance_accepted(self):
        engine, p = self._running_click_block()
        block = engine.current_session.current_block
        result = engine.handle_presenter_advance_request({
            "presenter_id": p.id,
            "block_id": block.id,
        })
        assert result is True

    def test_wrong_presenter_rejected(self):
        engine, p = self._running_click_block()
        block = engine.current_session.current_block
        result = engine.handle_presenter_advance_request({
            "presenter_id": "wrong-id",
            "block_id": block.id,
        })
        assert result is False

    def test_wrong_block_id_rejected(self):
        engine, p = self._running_click_block()
        result = engine.handle_presenter_advance_request({
            "presenter_id": p.id,
            "block_id": "wrong-block-id",
        })
        assert result is False

    def test_time_only_block_rejected(self):
        engine, bridge, sio = _make_engine()
        tl = Timeline.create("Time Only")
        p = Presenter.create("Bob", "#3498DB")
        tl.add_presenter(p)
        b = Block.create(p.id, 1, 5, 300.0,
                         end_condition=EndCondition.TIME)
        tl.add_block(b)
        engine.load_timeline(tl)
        engine.request_start_session()
        with patch("orchestra.engine.timeline_engine.BlockRunner") as mock_br, \
             patch("orchestra.engine.timeline_engine.VibrationScheduler") as mock_vs:
            mock_br.return_value = MagicMock()
            mock_vs.return_value = MagicMock()
            engine.operator_go()
        block = engine.current_session.current_block
        result = engine.handle_presenter_advance_request({
            "presenter_id": p.id,
            "block_id": block.id,
        })
        assert result is False
