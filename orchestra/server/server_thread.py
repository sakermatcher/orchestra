"""
ServerThread — wraps Flask-SocketIO's blocking run() in a daemon thread.

Started from OrchestraApp.__init__() after QApplication is created.
Being a daemon thread, it is terminated automatically when the Qt main thread exits.

IMPORTANT: We use the pre-monkey-patch threading.Thread (via eventlet.patcher.original)
so the server runs in a REAL OS thread, not an eventlet green thread. This is required
because the Qt event loop occupies the main OS thread and never yields to the
eventlet hub — which would otherwise starve the Flask server of CPU time.
"""
from __future__ import annotations
from typing import Optional

# Get the real OS-level Thread class, bypassing eventlet's monkey-patch
try:
    from eventlet.patcher import original as _eventlet_original
    _RealThread = _eventlet_original("threading").Thread
    _RealEvent  = _eventlet_original("threading").Event
except Exception:
    import threading as _threading
    _RealThread = _threading.Thread
    _RealEvent  = _threading.Event


class ServerThread(_RealThread):
    """
    Runs socketio.run() on a dedicated REAL OS thread so the Qt event loop
    can run on the main thread without starving the eventlet hub.
    """

    def __init__(self, app, socketio, host: str, port: int):
        super().__init__(daemon=True, name="OrchestralFlaskThread")
        self._app = app
        self._socketio = socketio
        self._host = host
        self._port = port
        self._started_event = _RealEvent()
        self._error: Optional[Exception] = None

    def run(self) -> None:
        try:
            # Start the relay worker from THIS OS thread so eventlet.spawn()
            # places it in the Flask hub (not the Qt hub).  Must happen before
            # socketio.run() blocks the thread in the eventlet event loop.
            from orchestra.server.flask_app import start_relay_worker
            start_relay_worker(self._socketio)

            self._started_event.set()
            self._socketio.run(
                self._app,
                host=self._host,
                port=self._port,
                use_reloader=False,
                log_output=False,
                allow_unsafe_werkzeug=True,
            )
        except OSError as e:
            self._error = e
            self._started_event.set()  # unblock wait_until_ready() on failure

    def wait_until_ready(self, timeout: float = 5.0) -> bool:
        """Block caller until the server thread has started (or failed). Returns True on success."""
        self._started_event.wait(timeout=timeout)
        return self._error is None

    @property
    def start_error(self) -> Optional[Exception]:
        return self._error

