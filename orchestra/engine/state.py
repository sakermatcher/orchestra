"""Engine state enumeration."""
from enum import Enum


class EngineState(str, Enum):
    IDLE             = "idle"
    TIMELINE_LOADED  = "timeline_loaded"
    WARMUP           = "warmup"
    RUNNING          = "running"
    PAUSED           = "paused"
    BLOCK_TRANSITION = "block_transition"
    COMPLETED        = "completed"
    ABORTED          = "aborted"
    ERROR            = "error"
