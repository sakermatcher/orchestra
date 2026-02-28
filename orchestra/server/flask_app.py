"""
Flask application factory.

create_app() returns the (Flask app, SocketIO) pair.
The SocketIO instance is created here and reused by socket_events.py.

Cross-thread relay
------------------
The Qt main thread is a real OS thread that never yields to an eventlet hub.
Calling eventlet.spawn() or socketio.emit() from the Qt thread therefore adds
work to the Qt thread's own hub, which never runs.

The remedy is a real (un-patched) OS-level queue that the Qt thread writes to.
A lightweight eventlet green thread running in the Flask OS thread polls this
queue every ~10 ms and executes the callables from within the correct hub
context.  get_relay_queue() exposes the queue so TimelineEngine can use it.
"""
from __future__ import annotations
from flask import Flask
from flask_socketio import SocketIO

from orchestra import APP_VERSION

_socketio: SocketIO | None = None

# ---------------------------------------------------------------------------
# Cross-thread relay queue (real OS-level, NOT eventlet-patched)
# ---------------------------------------------------------------------------

try:
    from eventlet.patcher import original as _ep_original
    _relay_queue = _ep_original("queue").Queue()
except Exception:
    import queue as _fallback_q
    _relay_queue = _fallback_q.Queue()


def get_relay_queue():
    """Return the cross-thread relay queue.

    The engine (Qt thread) puts callables here.  The relay worker green thread
    (Flask/eventlet hub) dequeues and calls them within the correct context.
    """
    return _relay_queue


def get_socketio() -> SocketIO:
    """Return the shared SocketIO instance. Must call create_app() first."""
    if _socketio is None:
        raise RuntimeError("create_app() has not been called yet")
    return _socketio


def create_app(engine_ref=None, bridge_ref=None) -> tuple[Flask, SocketIO]:
    """
    Application factory.

    engine_ref:  TimelineEngine instance (injected, may be None in Phase 1)
    bridge_ref:  QtBridge instance (injected, may be None in Phase 1)

    Returns (Flask app, SocketIO instance).
    """
    global _socketio

    import os
    static_folder = os.path.join(os.path.dirname(__file__), "..", "static")
    static_folder = os.path.abspath(static_folder)

    app = Flask(
        __name__,
        static_folder=static_folder,
        static_url_path="/static",
    )
    app.config["SECRET_KEY"] = "orchestra-local-secret"
    app.config["ENGINE"] = engine_ref
    app.config["BRIDGE"] = bridge_ref

    # Register HTTP routes blueprint
    from orchestra.server.routes import mobile_bp
    app.register_blueprint(mobile_bp)

    # Create SocketIO with eventlet async mode
    sio = SocketIO(
        app,
        async_mode="eventlet",
        cors_allowed_origins="*",
        logger=False,
        engineio_logger=False,
    )
    _socketio = sio

    # Register socket event handlers
    from orchestra.server.socket_events import register_handlers
    register_handlers(sio)

    # Give session_manager a reference to socketio for room management
    from orchestra.server.session_manager import session_manager
    session_manager.set_socketio(sio)

    # NOTE: the relay worker is NOT started here.
    # It must be started from within the Flask OS thread (ServerThread.run)
    # so that eventlet.spawn places the green thread in the Flask hub.
    # Calling sio.start_background_task() here would run it from the Qt
    # main thread's hub, which QApplication.exec() never yields to.

    return app, sio


def start_relay_worker(sio) -> None:
    """
    Start the relay worker green thread.

    MUST be called from within the Flask OS thread (e.g. ServerThread.run)
    BEFORE socketio.run() blocks.  eventlet.spawn() uses the calling thread's
    hub, so calling this from the Qt thread would add the worker to the Qt
    hub — which never runs.
    """
    q = _relay_queue

    def _relay_worker():
        while True:
            # Drain ALL available items before sleeping to minimise latency
            # when multiple events are queued at once.
            try:
                while True:
                    fn = q.get_nowait()
                    try:
                        fn()
                    except Exception as exc:
                        print(f"[relay] error: {exc}")
            except Exception:
                pass  # queue empty — normal
            sio.sleep(0.01)  # yield 10 ms, then poll again

    sio.start_background_task(_relay_worker)
