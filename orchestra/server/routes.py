"""
HTTP routes blueprint — serves mobile HTML and minimal REST API.

All real-time data goes over WebSocket. HTTP routes serve:
  - Mobile HTML pages
  - Minimal read-only JSON API for initial page load
"""
from __future__ import annotations
from flask import Blueprint, redirect, url_for, jsonify, current_app, render_template_string
from pathlib import Path

from orchestra import APP_VERSION

mobile_bp = Blueprint("mobile", __name__)


@mobile_bp.get("/")
def index():
    return redirect(url_for("mobile.join_page"))


@mobile_bp.get("/join")
def join_page():
    html_path = Path(__file__).resolve().parent.parent / "static" / "mobile" / "join.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Join page not yet built</h1>", 200


@mobile_bp.get("/presenter/<presenter_id>")
def presenter_page(presenter_id: str):
    html_path = Path(__file__).resolve().parent.parent / "static" / "mobile" / "presenter.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>Presenter page not yet built</h1>", 200


@mobile_bp.get("/api/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION})


@mobile_bp.get("/api/session")
def api_session():
    engine = current_app.config.get("ENGINE")
    if engine is None:
        return jsonify({"state": "idle", "timeline": None})
    return jsonify(engine.get_session_snapshot())


@mobile_bp.get("/api/presenters")
def api_presenters():
    engine = current_app.config.get("ENGINE")
    if engine is None or engine.current_timeline is None:
        return jsonify([])
    presenters = [p.to_dict() for p in engine.current_timeline.presenters]
    return jsonify(presenters)


@mobile_bp.get("/api/timeline")
def api_timeline():
    engine = current_app.config.get("ENGINE")
    if engine is None or engine.current_timeline is None:
        return jsonify(None)
    t = engine.current_timeline
    return jsonify({
        "id": t.id,
        "name": t.name,
        "total_duration_seconds": t.total_duration,
        "block_count": len(t.blocks),
        "presenter_count": len(t.presenters),
    })
