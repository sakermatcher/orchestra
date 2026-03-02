"""
Orchestra — Application-wide constants.
All magic numbers and limits live here. Never hardcode these elsewhere.
"""

APP_NAME = "Orchestra"
APP_VERSION = "1.0.0"

# Server defaults
DEFAULT_SERVER_PORT = 5000
DEFAULT_SERVER_HOST = "0.0.0.0"
SERVER_BIND_RETRY_ATTEMPTS = 3

# Timing
TIMER_BROADCAST_INTERVAL_MS = 1000  # How often timer:tick is emitted (ms)
QT_BRIDGE_POLL_INTERVAL_MS = 50     # How often Qt main thread polls the bridge queue (ms)
VIBRATION_FIRE_EARLY_BUFFER_MS = 80 # Fire vibration this many ms early to compensate latency
POWERPOINT_ADVANCE_DELAY_MS = 150   # Delay after block:activate before sending goto_slide to COM

# Session
SESSION_WARMUP_TIMEOUT_SECONDS = 600  # Max time to wait in WARMUP before auto-abort
MAX_PRESENTERS = 50                    # Hard cap on concurrent presenters
COM_RETRY_ATTEMPTS = 3                 # Retries for COM calls before raising COMFatalError
COM_RETRY_DELAY_MS = 100              # Delay between COM retries

# Vibration patterns (ms)
VIBRATION_SHORT_PATTERN_MS = [800]
VIBRATION_LONG_PATTERN_MS = [1500]

# Data paths (relative to project root, resolved at runtime by config_store)
DATA_DIR_NAME = "data"
TIMELINES_DIR_NAME = "timelines"
CONFIG_FILENAME = "config.json"
SESSION_RECOVERY_FILENAME = "session_recovery.json"

# UI dimensions
SIDEBAR_WIDTH = 220
PRESENTER_PANEL_WIDTH = 260
TIMELINE_RULER_HEIGHT = 28
TIMELINE_LANE_HEIGHT = 60
TIMELINE_LANE_LABEL_WIDTH = 130
TIMELINE_MIN_ZOOM_PX_PER_SEC = 0.5
TIMELINE_MAX_ZOOM_PX_PER_SEC = 20.0
TIMELINE_DEFAULT_ZOOM_PX_PER_SEC = 2.0
BLOCK_MIN_DURATION_SECONDS = 5.0
QR_DISPLAY_SIZE = 200

# Block defaults
DEFAULT_BLOCK_DURATION_SECONDS = 60.0  # 5 minutes
DEFAULT_END_CONDITION = "either"
DEFAULT_OVERRUN_BEHAVIOR = "auto_advance"
