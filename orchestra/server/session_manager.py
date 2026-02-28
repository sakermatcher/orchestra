"""
Session manager — tracks connected presenter sockets.

All shared state uses eventlet.semaphore.Semaphore (NOT threading.Lock)
because this code runs inside the eventlet green thread pool.

Phase 1: Stub with correct public interface.
Phase 3: Full implementation with room management and validation.
"""
from __future__ import annotations
from typing import Optional

try:
    import eventlet.semaphore
    _Semaphore = eventlet.semaphore.Semaphore
except ImportError:
    import threading
    _Semaphore = threading.Semaphore


class SessionManager:
    """
    Maintains the mapping between socket IDs and presenter IDs.

    One SessionManager instance is created per application lifetime (not per session).
    It is reset when a new session starts.
    """

    def __init__(self):
        self._socket_to_presenter: dict[str, str] = {}
        self._presenter_to_socket: dict[str, str] = {}
        self._lock = _Semaphore(1)
        self._socketio = None  # Injected after socketio is created

    def set_socketio(self, socketio) -> None:
        self._socketio = socketio

    def reset(self) -> None:
        """Clear all connections. Called when a session ends or is aborted."""
        with self._lock:
            self._socket_to_presenter.clear()
            self._presenter_to_socket.clear()

    def register(self, sid: str, presenter_id: str, timeline) -> tuple[bool, str]:
        """
        Register a socket as a presenter.
        Returns (success, error_code). error_code is empty string on success.
        """
        with self._lock:
            if presenter_id in self._presenter_to_socket:
                return False, "presenter_already_connected"
            # Validate presenter_id exists in current timeline
            if timeline is not None:
                if timeline.get_presenter(presenter_id) is None:
                    return False, "unknown_presenter_id"
            self._socket_to_presenter[sid] = presenter_id
            self._presenter_to_socket[presenter_id] = sid

        if self._socketio is not None:
            self._socketio.server.enter_room(sid, f"presenter:{presenter_id}")
            self._socketio.server.enter_room(sid, "session:all")

        return True, ""

    def unregister(self, sid: str) -> Optional[str]:
        """
        Remove a socket. Returns the presenter_id that was unregistered, or None.
        """
        with self._lock:
            presenter_id = self._socket_to_presenter.pop(sid, None)
            if presenter_id is not None:
                self._presenter_to_socket.pop(presenter_id, None)
        return presenter_id

    def get_presenter_id(self, sid: str) -> Optional[str]:
        return self._socket_to_presenter.get(sid)

    def get_socket_id(self, presenter_id: str) -> Optional[str]:
        return self._presenter_to_socket.get(presenter_id)

    def is_connected(self, presenter_id: str) -> bool:
        return presenter_id in self._presenter_to_socket

    def get_connected_presenter_ids(self) -> list[str]:
        with self._lock:
            return list(self._presenter_to_socket.keys())

    def force_disconnect(self, presenter_id: str) -> None:
        """Operator-initiated disconnect. Clears mapping so presenter can rejoin."""
        sid = self.get_socket_id(presenter_id)
        if sid:
            self.unregister(sid)
            if self._socketio is not None:
                self._socketio.server.disconnect(sid)


# Singleton instance created at import time; set_socketio() is called after create_app().
session_manager = SessionManager()
