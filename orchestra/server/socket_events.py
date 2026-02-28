"""
SocketIO event handlers — Phase 3 full implementation.

All handlers validate input, delegate to session_manager or engine,
and post relevant notifications to the Qt bridge.
"""
from __future__ import annotations
from flask import request, current_app
from flask_socketio import emit


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------

def _get_engine():
    return current_app.config.get("ENGINE")

def _get_bridge():
    return current_app.config.get("BRIDGE")

def _get_session_manager():
    from orchestra.server.session_manager import session_manager
    return session_manager


# These handlers are registered when flask_app.create_app() imports this module.
# The module-level @socketio.on decorators can't work here because socketio is
# created in the factory. We use register_handlers() called from flask_app.py.

def register_handlers(socketio):
    """Register all SocketIO event handlers. Called from create_app()."""

    @socketio.on("connect")
    def on_connect():
        sid = request.sid
        print(f"[SocketIO] connect: {sid}")

    @socketio.on("disconnect")
    def on_disconnect():
        sid = request.sid
        sm = _get_session_manager()
        presenter_id = sm.unregister(sid)
        if presenter_id:
            engine = _get_engine()
            presenter_name = "?"
            if engine and engine.current_session:
                p = engine.current_session.timeline.get_presenter(presenter_id)
                if p:
                    presenter_name = p.name
            socketio.emit("presenter:left", {
                "presenter_id": presenter_id,
                "name": presenter_name,
            }, room="session:all")
            bridge = _get_bridge()
            if bridge:
                bridge.post("presenter:disconnected", {"id": presenter_id, "name": presenter_name})
            # Update connected list
            _broadcast_connected_list(socketio, engine, sm)
        print(f"[SocketIO] disconnect: {sid} (presenter: {presenter_id})")

    @socketio.on("presenter:join")
    def on_presenter_join(data):
        sid = request.sid
        presenter_id = data.get("presenter_id")
        display_name = data.get("display_name", "")

        engine = _get_engine()
        sm = _get_session_manager()

        if engine is None or not engine.is_session_active():
            socketio.emit("presenter:join_error", {
                "code": "no_active_session",
                "message": "No presentation session is currently active.",
            }, room=sid)
            return

        timeline = engine.current_session.timeline if engine.current_session else None
        success, error_code = sm.register(sid, presenter_id, timeline)

        if not success:
            messages = {
                "presenter_already_connected": "This presenter is already connected from another device.",
                "unknown_presenter_id": "Presenter ID not found in this timeline.",
                "session_full": "Session has reached maximum capacity.",
            }
            socketio.emit("presenter:join_error", {
                "code": error_code,
                "message": messages.get(error_code, "Join failed."),
            }, room=sid)
            return

        # Get presenter info
        presenter = timeline.get_presenter(presenter_id) if timeline else None
        if presenter is None:
            sm.unregister(sid)
            socketio.emit("presenter:join_error", {
                "code": "unknown_presenter_id",
                "message": "Presenter not found in timeline.",
            }, room=sid)
            return

        # Send success + session snapshot
        snapshot = engine.get_session_snapshot()
        socketio.emit("presenter:join_ok", {
            "presenter_id": presenter_id,
            "name": presenter.name,
            "color": presenter.color,
            "session_snapshot": snapshot,
        }, room=sid)

        # Notify bridge
        bridge = _get_bridge()
        if bridge:
            bridge.post("presenter:connected", {"id": presenter_id, "name": presenter.name})

        # Broadcast updated list
        _broadcast_connected_list(socketio, engine, sm)
        print(f"[SocketIO] presenter:join — {presenter.name} ({presenter_id})")

    @socketio.on("presenter:request_advance")
    def on_presenter_advance(data):
        engine = _get_engine()
        if engine is None:
            return
        accepted = engine.handle_presenter_advance_request(data)
        if not accepted:
            sid = request.sid
            socketio.emit("presenter:advance_rejected", {
                "reason": "not_your_turn_or_not_eligible"
            }, room=sid)

    @socketio.on("presenter:heartbeat")
    def on_heartbeat(data):
        # No-op: Socket.IO's own ping/pong handles keep-alive.
        pass


def _broadcast_connected_list(socketio, engine, sm) -> None:
    """Broadcast updated connected presenter count to all."""
    connected_ids = sm.get_connected_presenter_ids()
    timeline = None
    if engine and engine.current_session:
        timeline = engine.current_session.timeline
    expected = len(timeline.presenters) if timeline else 0
    connected = []
    for pid in connected_ids:
        p = timeline.get_presenter(pid) if timeline else None
        if p:
            connected.append({"presenter_id": pid, "name": p.name, "color": p.color})
    socketio.emit("presenter:connected_list", {
        "connected": connected,
        "total_expected": expected,
    }, room="session:all")
    bridge = engine._bridge if engine else None
    if bridge:
        bridge.post("presenter:list_updated", connected_ids)
