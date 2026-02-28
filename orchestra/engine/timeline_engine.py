"""
TimelineEngine — the authoritative presentation session state machine.

All state transitions happen here. WebSocket emissions happen here.
COM commands are enqueued here.
Qt bridge posts happen here.

Thread safety:
  - Operator methods (request_start_session, toggle_pause, etc.) are called
    from the Qt main thread via signal-slot.
  - Presenter methods (handle_presenter_advance_request) are called from
    Flask/eventlet green threads.
  - An eventlet.semaphore.Semaphore protects the transition state.
"""
from __future__ import annotations
import json
import time
from pathlib import Path
from typing import Optional

try:
    import eventlet.semaphore
    _Lock = eventlet.semaphore.Semaphore
    _USE_EVENTLET = True
except ImportError:
    import threading
    _Lock = threading.Semaphore
    _USE_EVENTLET = False

from orchestra.engine.state import EngineState
from orchestra.engine.session import ActiveSession, BlockState
from orchestra.engine.block_runner import BlockRunner
from orchestra.engine.vibration_scheduler import VibrationScheduler
from orchestra.models.timeline import Timeline
from orchestra.models.block import EndCondition
from orchestra.storage.config_store import load_config, get_data_dir
from orchestra.constants import SESSION_RECOVERY_FILENAME


class TimelineEngine:
    """
    Central coordinator for all session logic.

    Instantiated once in OrchestraApp. Injected into Flask app and Qt bridge.
    """

    def __init__(self, bridge=None, com_worker=None):
        self._bridge = bridge          # QtBridge
        self._com_worker = com_worker  # (command_queue, result_queue) tuple
        self._socketio = None          # Injected after server starts
        self._config = load_config()

        self._state: EngineState = EngineState.IDLE
        self._timeline: Optional[Timeline] = None
        self._session: Optional[ActiveSession] = None
        self._block_runner: Optional[BlockRunner] = None
        self._vib_scheduler: Optional[VibrationScheduler] = None
        self._lock = _Lock(1)

        # Budget tracking: running balance of time saved (positive) or lost
        # (negative) across all completed blocks.  Positive budget is added to
        # the next block's effective timer duration.
        self._session_budget: float = 0.0
        # Effective duration used for the currently active block (may exceed
        # block.duration when surplus budget has accumulated).
        self._current_effective_duration: float = 0.0

    # ------------------------------------------------------------------
    # Dependency injection
    # ------------------------------------------------------------------

    def set_socketio(self, socketio) -> None:
        self._socketio = socketio
        if self._vib_scheduler:
            self._vib_scheduler._socketio = socketio

    def set_bridge(self, bridge) -> None:
        self._bridge = bridge

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def state(self) -> EngineState:
        return self._state

    @property
    def current_timeline(self) -> Optional[Timeline]:
        return self._timeline

    @property
    def current_session(self) -> Optional[ActiveSession]:
        return self._session

    def is_session_active(self) -> bool:
        return self._state in (
            EngineState.WARMUP, EngineState.RUNNING,
            EngineState.PAUSED, EngineState.BLOCK_TRANSITION,
        )

    # ------------------------------------------------------------------
    # Operator commands (called from Qt main thread)
    # ------------------------------------------------------------------

    def load_timeline(self, timeline: Timeline) -> None:
        """Load a timeline for editing/session use."""
        self._timeline = timeline
        if self._state == EngineState.IDLE:
            self._transition(EngineState.TIMELINE_LOADED)
        elif self._state == EngineState.TIMELINE_LOADED:
            pass  # already loaded, just replaced

    def request_start_session(self) -> None:
        """Operator clicks 'Start Session' in the editor."""
        if self._timeline is None:
            return
        errors = self._timeline.validate()
        if errors:
            if self._bridge:
                self._bridge.post("error:server", "Timeline has validation errors:\n" +
                                  "\n".join(errors))
            return
        if self._state not in (EngineState.IDLE, EngineState.TIMELINE_LOADED):
            return

        # Clear any stale presenter connections from the previous session
        try:
            from orchestra.server.session_manager import session_manager as _sm
            _sm.reset()
        except Exception:
            pass

        self._session = ActiveSession.create(self._timeline)
        self._vib_scheduler = VibrationScheduler(self._socketio, self._config)
        self._session_budget = 0.0
        self._current_effective_duration = 0.0
        self._transition(EngineState.WARMUP)

        # Emit session:warmup to all connected clients
        self._emit("session:warmup", {
            "session_id": self._session.id,
            "timeline_name": self._timeline.name,
            "total_duration_seconds": self._timeline.total_duration,
            "block_count": len(self._timeline.blocks),
            "presenters": [p.to_dict() for p in self._timeline.presenters],
        }, room="session:all")

        # Persist session snapshot for crash recovery
        self._persist_recovery()

    def operator_go(self) -> None:
        """Operator clicks 'GO' to begin the actual presentation."""
        if self._state != EngineState.WARMUP:
            return
        # Open PowerPoint
        self._com_open_presentation()
        # Signal session start to all clients
        self._emit("session:started", {
            "session_id": self._session.id,
            "start_epoch": time.time(),
        }, room="session:all")

        delay = self._config.get("presentation_start_delay_seconds", 3)
        if delay > 0 and _USE_EVENTLET:
            import eventlet as _ev
            try:
                from orchestra.server.flask_app import get_relay_queue
                def _do_with_delay():
                    _ev.spawn(lambda: [_ev.sleep(delay), self._activate_block(0)])
                get_relay_queue().put(_do_with_delay)
            except Exception:
                # Flask server not running (tests / early boot) — activate immediately
                self._activate_block(0)
        else:
            self._activate_block(0)

    def toggle_pause(self) -> None:
        if self._state == EngineState.RUNNING:
            self._pause()
        elif self._state == EngineState.PAUSED:
            self._resume()

    def skip_current_block(self) -> None:
        if self._state != EngineState.RUNNING:
            return
        if self._session:
            bs = self._session.current_block_state
            if bs:
                bs.state = "skipped"
        self._complete_current_block("operator_skip")

    def abort_session(self) -> None:
        if not self.is_session_active():
            return
        self._stop_block_runner()
        elapsed = self._session.session_elapsed_seconds if self._session else 0
        self._emit("session:aborted", {
            "reason": "operator_abort",
            "message": "Operator ended the session.",
            "aborted_at_elapsed_seconds": elapsed,
        }, room="session:all")
        self._session = None
        self._transition(EngineState.ABORTED)
        self._cleanup_recovery()

    def session_reset(self) -> None:
        """Return to TIMELINE_LOADED state after completion or abort."""
        if self._state in (EngineState.COMPLETED, EngineState.ABORTED, EngineState.ERROR):
            self._transition(EngineState.TIMELINE_LOADED if self._timeline else EngineState.IDLE)

    # ------------------------------------------------------------------
    # Presenter commands (called from Flask/eventlet green threads)
    # ------------------------------------------------------------------

    def handle_presenter_advance_request(self, data: dict) -> bool:
        """
        A presenter requests to end their block.
        Returns True if the advance was accepted.
        """
        if self._state != EngineState.RUNNING:
            return False
        if not self._session:
            return False

        block = self._session.current_block
        if block is None:
            return False

        presenter_id = data.get("presenter_id")
        block_id = data.get("block_id")

        if block.id != block_id:
            return False
        if block.presenter_id != presenter_id:
            return False
        if block.end_condition == EndCondition.TIME:
            return False   # click not allowed for time-only blocks

        self._complete_current_block("presenter_advance")
        return True

    def handle_presenter_goto_slide(self, data: dict) -> bool:
        """
        A presenter requests to navigate to a specific slide within their block.
        Returns True if accepted.
        """
        if self._state != EngineState.RUNNING:
            return False
        if not self._session:
            return False

        block = self._session.current_block
        if block is None:
            return False

        presenter_id = data.get("presenter_id")
        if block.presenter_id != presenter_id:
            return False

        slide_number = data.get("slide_number")
        if slide_number is None:
            return False

        # Clamp to block's slide range
        slide_number = max(block.slide_start, min(block.slide_end, int(slide_number)))
        self._com_goto_slide(slide_number)
        # Confirm navigation back to the requesting presenter
        self._emit("slide:goto", {
            "slide_number": slide_number,
            "block_id": block.id,
            "reason": "presenter_navigation",
        }, room=f"presenter:{presenter_id}")
        return True

    def handle_presenter_prev_block(self, data: dict) -> bool:
        """
        A presenter requests to go back to the previous block.
        The previous block is started with accumulated surplus as its remaining time.
        Returns True if accepted.
        """
        if self._state != EngineState.RUNNING:
            return False
        if not self._session:
            return False

        current_idx = self._session.current_block_index
        if current_idx == 0:
            return False  # already at the first block

        block = self._session.current_block
        if block is None:
            return False

        presenter_id = data.get("presenter_id")
        if block.presenter_id != presenter_id:
            return False

        # End the current block without updating budget (no time was "spent"
        # on it from budget perspective — presenter is going back)
        self._transition(EngineState.BLOCK_TRANSITION)
        self._stop_block_runner()
        self._emit("block:completed", {
            "block_id": block.id,
            "completion_reason": "presenter_prev_block",
        }, room="session:all")

        # Give the previous block the accumulated budget as its effective duration
        # (minimum 30 seconds so the presenter has some time to work with).
        override_eff = max(30.0, self._session_budget) if self._session_budget > 0 else 30.0
        self._activate_block(current_idx - 1, override_effective_duration=override_eff)
        return True

    # ------------------------------------------------------------------
    # Session snapshot (for /api/session and WebSocket state_sync)
    # ------------------------------------------------------------------

    def get_session_snapshot(self) -> dict:
        if not self._session:
            return {"state": self._state.value, "timeline": None}

        block = self._session.current_block
        block_elapsed = 0.0
        block_remaining = 0.0
        if self._block_runner and self._state in (EngineState.RUNNING, EngineState.PAUSED):
            block_elapsed = self._block_runner.block_elapsed_seconds
            block_remaining = self._block_runner.block_remaining_seconds

        return {
            "state": self._state.value,
            "session_id": self._session.id,
            "timeline_id": self._session.timeline.id,
            "session_elapsed_seconds": self._session.session_elapsed_seconds,
            "session_start_epoch": (
                self._session.block_states[0].actual_start_epoch
                if self._session.block_states
                   and self._session.block_states[0].actual_start_epoch
                else 0.0
            ),
            "current_block_index": self._session.current_block_index,
            "block_elapsed_seconds": block_elapsed,
            "block_remaining_seconds": max(0.0, block_remaining),
            "current_block": block.to_dict() if block else None,
            "session_budget_seconds": self._session_budget,
            "effective_duration_seconds": self._current_effective_duration,
            "blocks_summary": [
                {
                    "block_id": b.id,
                    "presenter_id": b.presenter_id,
                    "presenter_name": self._get_presenter_name(b.presenter_id),
                    "presenter_color": self._get_presenter_color(b.presenter_id),
                    "duration": b.duration,
                }
                for b in self._session.timeline.blocks
            ],
            "presenters": [p.to_dict() for p in self._session.timeline.presenters],
            "activate_epoch": (
                self._session.current_block_state.actual_start_epoch
                if self._session.current_block_state else 0.0
            ),
        }

    # ------------------------------------------------------------------
    # Internal transitions
    # ------------------------------------------------------------------

    def _transition(self, new_state: EngineState) -> None:
        old = self._state
        self._state = new_state
        if self._bridge:
            self._bridge.post("session:state_changed", new_state.value)
        print(f"[Engine] {old.value} → {new_state.value}")

    def _activate_block(self, block_index: int,
                        override_effective_duration: Optional[float] = None) -> None:
        if not self._session:
            return
        blocks = self._session.timeline.blocks
        if block_index >= len(blocks):
            self._complete_session()
            return

        self._session.current_block_index = block_index
        block = blocks[block_index]
        bs = self._session.block_states[block_index]
        bs.state = "active"
        bs.actual_start_epoch = time.time()

        # Compute effective duration: nominal + any accumulated surplus.
        if override_effective_duration is not None:
            effective = override_effective_duration
        else:
            effective = block.duration + max(0.0, self._session_budget)
        self._current_effective_duration = effective

        presenter = self._get_presenter(block.presenter_id)
        self._transition(EngineState.RUNNING)

        payload = {
            "block_id": block.id,
            "presenter_id": block.presenter_id,
            "presenter_name": presenter.name if presenter else "?",
            "presenter_color": presenter.color if presenter else "#888",
            "block_index": block_index,
            "total_blocks": len(blocks),
            "slide_start": block.slide_start,
            "slide_end": block.slide_end,
            "duration_seconds": block.duration,
            "effective_duration_seconds": effective,
            "session_budget_seconds": self._session_budget,
            "end_condition": block.end_condition.value,
            "overrun_behavior": block.overrun_behavior.value,
            "activate_epoch": bs.actual_start_epoch,
            "notes": block.notes,
        }
        self._emit("block:activate", payload, room="session:all")
        self._emit("slide:goto", {
            "slide_number": block.slide_start,
            "block_id": block.id,
            "reason": "block_start",
        }, room=f"presenter:{block.presenter_id}")

        if self._bridge:
            self._bridge.post("block:activated", payload)

        # Navigate PowerPoint
        self._com_goto_slide(block.slide_start)

        # Start block runner — must happen inside the Flask/eventlet hub so
        # that eventlet.spawn() adds green threads to the correct hub.
        self._stop_block_runner()
        now_mono = time.monotonic()
        self._session.block_start_monotonic = now_mono
        self._block_runner = BlockRunner(
            block=block,
            socketio=self._socketio,
            vib_scheduler=self._vib_scheduler,
            on_block_expired=self._on_block_time_expired,
            config=self._config,
            effective_duration=effective,
        )
        _runner = self._block_runner
        _mono = now_mono
        self._relay(lambda: _runner.start(_mono))

    def _on_block_time_expired(self) -> None:
        """Called from block runner green thread when time expires."""
        if self._state == EngineState.RUNNING:
            self._complete_current_block("time_expired")

    def _complete_current_block(self, reason: str) -> None:
        if not self._session:
            return
        self._transition(EngineState.BLOCK_TRANSITION)
        self._stop_block_runner()

        block = self._session.current_block
        bs = self._session.current_block_state
        if block and bs:
            bs.state = "completed"
            bs.actual_end_epoch = time.time()
            actual_duration = bs.actual_end_epoch - bs.actual_start_epoch
            overrun = max(0.0, actual_duration - self._current_effective_duration)
            bs.overrun_seconds = overrun

            # Update running budget: positive = time saved, negative = time lost
            self._session_budget += (self._current_effective_duration - actual_duration)

            self._emit("block:completed", {
                "block_id": block.id,
                "completion_reason": reason,
                "actual_duration_seconds": actual_duration,
                "overrun_seconds": overrun,
                "session_budget_seconds": self._session_budget,
            }, room="session:all")

            if self._bridge:
                self._bridge.post("block:completed", {
                    "block_id": block.id,
                    "completion_reason": reason,
                })

        next_idx = self._session.current_block_index + 1
        if next_idx < len(self._session.timeline.blocks):
            self._activate_block(next_idx)
        else:
            self._complete_session()

    def _complete_session(self) -> None:
        total_elapsed = 0.0
        if self._session:
            bs_list = [bs for bs in self._session.block_states if bs.actual_end_epoch]
            if bs_list:
                last = max(bs_list, key=lambda x: x.actual_end_epoch)
                if self._session.block_states and self._session.block_states[0].actual_start_epoch:
                    total_elapsed = last.actual_end_epoch - self._session.block_states[0].actual_start_epoch

        self._emit("session:completed", {
            "total_actual_duration_seconds": total_elapsed,
            "completed_epoch": time.time(),
        }, room="session:all")
        self._transition(EngineState.COMPLETED)
        self._cleanup_recovery()

    def _pause(self) -> None:
        if self._block_runner:
            self._block_runner.pause()
        self._transition(EngineState.PAUSED)
        self._emit("session:paused", {
            "paused_at_elapsed_seconds": self._session.session_elapsed_seconds if self._session else 0,
            "paused_epoch": time.time(),
        }, room="session:all")

    def _resume(self) -> None:
        resume_mono = time.monotonic()
        if self._block_runner:
            self._block_runner.resume(resume_mono)
        self._transition(EngineState.RUNNING)
        self._emit("session:resumed", {
            "resumed_at_elapsed_seconds": self._session.session_elapsed_seconds if self._session else 0,
            "resumed_epoch": time.time(),
        }, room="session:all")

    def _stop_block_runner(self) -> None:
        if self._block_runner:
            self._block_runner.stop()
            self._block_runner = None

    # ------------------------------------------------------------------
    # COM commands
    # ------------------------------------------------------------------

    def _com_open_presentation(self) -> None:
        if not self._com_worker or not self._timeline:
            return
        if not self._timeline.presentation_file_path:
            print("[Engine] No PPTX file linked to this timeline — "
                  "PowerPoint will not be opened automatically.")
            return
        path = self._timeline.presentation_file_path
        cmd_queue, _ = self._com_worker
        from orchestra.powerpoint.com_controller import PowerPointController
        try:
            cmd_queue.put(lambda: PowerPointController.static_open(path))
            print(f"[Engine] COM: opening presentation '{path}'")
        except Exception as e:
            print(f"[Engine] COM queue error: {e}")
            if self._bridge:
                self._bridge.post("error:powerpoint", f"Failed to open PowerPoint: {e}")

    def _com_goto_slide(self, slide_number: int) -> None:
        if not self._com_worker:
            return
        import time as _time
        delay = self._config.get("powerpoint_slide_advance_delay_ms", 150) / 1000.0
        cmd_queue, _ = self._com_worker
        try:
            def _cmd():
                _time.sleep(delay)
                from orchestra.powerpoint.com_controller import PowerPointController
                PowerPointController.static_goto_slide(slide_number)
            cmd_queue.put(_cmd)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _emit(self, event: str, data: dict, room: str | None = None) -> None:
        if not self._socketio:
            return
        _sio = self._socketio
        _room = room
        def _do():
            if _room:
                _sio.emit(event, data, room=_room)
            else:
                _sio.emit(event, data)
        self._relay(_do)

    def _relay(self, fn) -> None:
        """Execute fn inside the Flask/eventlet hub via the relay queue.

        Safe to call from any OS thread (Qt main thread, Flask green thread,
        COM thread).  The relay worker in flask_app.py drains the queue every
        ~10 ms from within the correct eventlet context.
        """
        try:
            from orchestra.server.flask_app import get_relay_queue
            get_relay_queue().put(fn)
        except Exception:
            # Flask server not yet running (tests / early boot) — call directly
            try:
                fn()
            except Exception:
                pass

    def _get_presenter(self, presenter_id: str):
        if not self._session:
            return None
        return self._session.timeline.get_presenter(presenter_id)

    def _get_presenter_name(self, presenter_id: str) -> str:
        p = self._get_presenter(presenter_id)
        return p.name if p else "?"

    def _get_presenter_color(self, presenter_id: str) -> str:
        p = self._get_presenter(presenter_id)
        return p.color if p else "#888"

    # ------------------------------------------------------------------
    # Crash recovery persistence
    # ------------------------------------------------------------------

    def _persist_recovery(self) -> None:
        if not self._session:
            return
        path = get_data_dir() / SESSION_RECOVERY_FILENAME
        try:
            with path.open("w", encoding="utf-8") as f:
                json.dump(self._session.to_dict(), f, indent=2)
        except Exception:
            pass

    def _cleanup_recovery(self) -> None:
        path = get_data_dir() / SESSION_RECOVERY_FILENAME
        if path.exists():
            try:
                path.unlink()
            except Exception:
                pass
