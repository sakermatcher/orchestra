"""
QtBridge — thread-safe event bus between Flask/SocketIO green threads and the Qt main thread.

USAGE
-----
1. Flask handler calls `bridge.post(event_type, payload)` from any thread.
2. A QTimer on the Qt main thread calls `bridge._poll()` every 50ms.
3. _poll() drains the queue and emits pyqtSignals.
4. Qt widgets connect to these signals and update the UI.

NEVER call PyQt6 methods directly from Flask handlers — always go through this bridge.
"""
from __future__ import annotations
import queue
from typing import Any

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from orchestra.constants import QT_BRIDGE_POLL_INTERVAL_MS


class QtBridge(QObject):
    """
    Signals correspond to server-side events that the UI needs to react to.
    Add new signals here as new event types are introduced in Phase 3+.
    """

    # Session lifecycle
    session_state_changed = pyqtSignal(str)          # new state string
    session_snapshot_ready = pyqtSignal(dict)        # full session snapshot

    # Presenter connections
    presenter_connected = pyqtSignal(str, str)       # presenter_id, name
    presenter_disconnected = pyqtSignal(str, str)    # presenter_id, name
    connected_list_updated = pyqtSignal(list)        # list of connected presenter_ids

    # Block events
    block_activated = pyqtSignal(dict)               # block_activate payload
    block_completed = pyqtSignal(dict)               # block_complete payload
    block_overrun = pyqtSignal(dict)                 # block_overrun payload

    # Timer
    timer_tick = pyqtSignal(dict)                    # timer:tick payload

    # Errors
    server_error = pyqtSignal(str)                   # human-readable error message
    powerpoint_error = pyqtSignal(str)               # COM error message

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._timer = QTimer(self)
        self._timer.setInterval(QT_BRIDGE_POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._poll)
        self._timer.start()

    def post(self, event_type: str, payload: Any = None) -> None:
        """Thread-safe. Called from any thread to queue an event for Qt processing."""
        self._queue.put_nowait((event_type, payload))

    def _poll(self) -> None:
        """Called on Qt main thread by QTimer. Drains queue and emits signals."""
        try:
            while True:
                event_type, payload = self._queue.get_nowait()
                self._dispatch(event_type, payload)
        except queue.Empty:
            pass

    def _dispatch(self, event_type: str, payload: Any) -> None:
        dispatch_map = {
            "session:state_changed":    lambda p: self.session_state_changed.emit(p),
            "session:snapshot":         lambda p: self.session_snapshot_ready.emit(p),
            "presenter:connected":      lambda p: self.presenter_connected.emit(p["id"], p["name"]),
            "presenter:disconnected":   lambda p: self.presenter_disconnected.emit(p["id"], p["name"]),
            "presenter:list_updated":   lambda p: self.connected_list_updated.emit(p),
            "block:activated":          lambda p: self.block_activated.emit(p),
            "block:completed":          lambda p: self.block_completed.emit(p),
            "block:overrun":            lambda p: self.block_overrun.emit(p),
            "timer:tick":               lambda p: self.timer_tick.emit(p),
            "error:server":             lambda p: self.server_error.emit(p),
            "error:powerpoint":         lambda p: self.powerpoint_error.emit(p),
        }
        handler = dispatch_map.get(event_type)
        if handler is not None:
            try:
                handler(payload)
            except Exception as e:
                print(f"[QtBridge] Error dispatching {event_type!r}: {e}")
        else:
            print(f"[QtBridge] Unknown event type: {event_type!r}")
