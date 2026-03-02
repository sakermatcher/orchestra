"""
Config store — reads and writes data/config.json.

All paths in the application are resolved relative to the project root,
which is determined once here and reused everywhere.
"""
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from orchestra.constants import (
    DATA_DIR_NAME,
    TIMELINES_DIR_NAME,
    CONFIG_FILENAME,
    DEFAULT_SERVER_PORT,
    DEFAULT_SERVER_HOST,
    POWERPOINT_ADVANCE_DELAY_MS,
    VIBRATION_FIRE_EARLY_BUFFER_MS,
    TIMER_BROADCAST_INTERVAL_MS,
    SESSION_WARMUP_TIMEOUT_SECONDS,
)

# Project root = parent of the orchestra/ package directory.
# When running as a PyInstaller bundle, user data lives next to the .exe
# rather than inside the temporary _MEIPASS extraction directory.
if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys.executable).parent
else:
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

_DEFAULT_CONFIG: Dict[str, Any] = {
    "schema_version": 1,
    "server_port": DEFAULT_SERVER_PORT,
    "server_host": DEFAULT_SERVER_HOST,
    "auto_detect_ip": True,
    "override_display_ip": None,
    "powerpoint_slide_advance_delay_ms": POWERPOINT_ADVANCE_DELAY_MS,
    "vibration_fire_early_buffer_ms": VIBRATION_FIRE_EARLY_BUFFER_MS,
    "timer_broadcast_interval_ms": TIMER_BROADCAST_INTERVAL_MS,
    "session_warmup_timeout_seconds": SESSION_WARMUP_TIMEOUT_SECONDS,
    "theme": "dark",
    "last_pptx_directory": str(Path.home()),
    "recent_timeline_ids": [],
}


def get_data_dir() -> Path:
    d = _PROJECT_ROOT / DATA_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def get_timelines_dir() -> Path:
    d = get_data_dir() / TIMELINES_DIR_NAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _config_path() -> Path:
    return get_data_dir() / CONFIG_FILENAME


def load_config() -> Dict[str, Any]:
    path = _config_path()
    if not path.exists():
        save_config(_DEFAULT_CONFIG.copy())
        return _DEFAULT_CONFIG.copy()
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # Fill missing keys with defaults (forward-compatible config upgrades)
    merged = _DEFAULT_CONFIG.copy()
    merged.update(data)
    return merged


def save_config(config: Dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
