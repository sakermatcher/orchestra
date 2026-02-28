"""
VibrationScheduler — schedules per-vibration green threads for a block.

One green thread per vibration event. Killed when the block ends early.
Uses time.monotonic() for drift-free scheduling.
"""
from __future__ import annotations
import time
from typing import Optional

try:
    import eventlet
    import eventlet.greenthread
    _USE_EVENTLET = True
except ImportError:
    _USE_EVENTLET = False

from orchestra.models.block import Block
from orchestra.constants import VIBRATION_FIRE_EARLY_BUFFER_MS


class VibrationScheduler:

    def __init__(self, socketio, config: dict):
        self._socketio = socketio
        self._config = config
        self._green_threads: list = []

    def schedule_block(self, block: Block, block_start_monotonic: float) -> None:
        """Schedule all vibration events for a block. Call on block activation."""
        self.cancel_all()
        buffer_sec = self._config.get("vibration_fire_early_buffer_ms",
                                      VIBRATION_FIRE_EARLY_BUFFER_MS) / 1000.0
        for v in block.vibrations:
            fire_at_elapsed = block.duration - v.seconds_before_end - buffer_sec
            if fire_at_elapsed < 0:
                continue  # Only schedule future events
            target_monotonic = block_start_monotonic + fire_at_elapsed
            if _USE_EVENTLET:
                gt = eventlet.spawn(
                    self._fire_vibration_at,
                    target_monotonic, v, block.id, block.presenter_id
                )
                self._green_threads.append(gt)

    def cancel_all(self) -> None:
        """Kill all pending vibration green threads. Called when block ends."""
        for gt in self._green_threads:
            try:
                gt.kill()
            except Exception:
                pass
        self._green_threads.clear()

    def _fire_vibration_at(
        self,
        target_monotonic: float,
        vibration,
        block_id: str,
        presenter_id: str,
    ) -> None:
        now = time.monotonic()
        sleep_for = target_monotonic - now
        if sleep_for > 0:
            if _USE_EVENTLET:
                eventlet.sleep(sleep_for)
            else:
                time.sleep(sleep_for)
        # Emit to the presenter's private room only
        room = f"presenter:{presenter_id}"
        payload = {
            "vibration_id": vibration.id,
            "label": vibration.label,
            "type": vibration.type,
            "pattern_ms": vibration.pattern_ms,
            "block_id": block_id,
            "seconds_remaining": vibration.seconds_before_end,
        }
        if self._socketio:
            self._socketio.emit("presenter:vibrate", payload, room=room)
