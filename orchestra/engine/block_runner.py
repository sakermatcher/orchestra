"""
BlockRunner — manages the lifecycle of the currently active block.

Responsibilities:
  - Track elapsed time using time.monotonic()
  - Run the timer tick green thread
  - Coordinate with VibrationScheduler
  - Detect time-based block expiry
  - Handle overrun state
"""
from __future__ import annotations
import time
from typing import Callable, Optional

try:
    import eventlet
    _USE_EVENTLET = True
except ImportError:
    _USE_EVENTLET = False

from orchestra.models.block import Block, EndCondition
from orchestra.engine.vibration_scheduler import VibrationScheduler
from orchestra.constants import TIMER_BROADCAST_INTERVAL_MS


class BlockRunner:
    """
    Manages one active block's timer loop. Created per block activation.
    Call start() after block:activate is emitted.
    Call stop() when the block ends (for any reason).
    """

    def __init__(
        self,
        block: Block,
        socketio,
        vib_scheduler: VibrationScheduler,
        on_block_expired: Callable[[], None],
        config: dict,
        effective_duration: Optional[float] = None,
    ):
        self._block = block
        self._socketio = socketio
        self._vib_scheduler = vib_scheduler
        self._on_block_expired = on_block_expired
        self._config = config
        # effective_duration may be longer than block.duration when the session
        # has accumulated surplus time from previous blocks finishing early.
        self._effective_duration: float = (
            effective_duration if effective_duration is not None else block.duration
        )

        self._start_monotonic: float = 0.0
        self._paused_at: Optional[float] = None
        self._total_paused: float = 0.0
        self._running = False
        self._overrun = False
        self._tick_thread = None
        self._expiry_thread = None

    def start(self, start_monotonic: float, paused: bool = False) -> None:
        self._start_monotonic = start_monotonic
        self._running = True

        if paused:
            # Start in paused state: no threads spawned, no vibrations scheduled.
            # Call resume() later to actually begin timing.
            self._paused_at = start_monotonic
            return

        self._vib_scheduler.schedule_block(self._block, start_monotonic, self._effective_duration)

        if _USE_EVENTLET:
            self._tick_thread = eventlet.spawn(self._tick_loop)
            if self._block.end_condition in (EndCondition.TIME, EndCondition.EITHER):
                self._expiry_thread = eventlet.spawn(self._expiry_waiter)

    def stop(self) -> None:
        self._running = False
        self._vib_scheduler.cancel_all()
        if self._tick_thread:
            try: self._tick_thread.kill()
            except: pass
        if self._expiry_thread:
            try: self._expiry_thread.kill()
            except: pass

    def pause(self) -> None:
        self._paused_at = time.monotonic()
        if self._tick_thread:
            try: self._tick_thread.kill()
            except: pass
        if self._expiry_thread:
            try: self._expiry_thread.kill()
            except: pass
        self._tick_thread = None
        self._expiry_thread = None

    def resume(self, resume_monotonic: float) -> None:
        if self._paused_at is not None:
            self._total_paused += resume_monotonic - self._paused_at
            self._paused_at = None
        if _USE_EVENTLET and self._running:
            self._tick_thread = eventlet.spawn(self._tick_loop)
            remaining = self.block_remaining_seconds
            if remaining > 0 and self._block.end_condition in (EndCondition.TIME, EndCondition.EITHER):
                self._expiry_thread = eventlet.spawn(self._expiry_waiter)

    @property
    def block_elapsed_seconds(self) -> float:
        if self._paused_at is not None:
            return self._paused_at - self._start_monotonic - self._total_paused
        return time.monotonic() - self._start_monotonic - self._total_paused

    @property
    def effective_duration(self) -> float:
        return self._effective_duration

    @property
    def block_remaining_seconds(self) -> float:
        return self._effective_duration - self.block_elapsed_seconds

    @property
    def is_overrun(self) -> bool:
        return self._overrun

    @property
    def overrun_seconds(self) -> float:
        if not self._overrun:
            return 0.0
        return max(0.0, self.block_elapsed_seconds - self._effective_duration)

    # ------------------------------------------------------------------
    # Internal green threads
    # ------------------------------------------------------------------

    def _tick_loop(self) -> None:
        interval = self._config.get("timer_broadcast_interval_ms",
                                    TIMER_BROADCAST_INTERVAL_MS) / 1000.0
        while self._running:
            elapsed = self.block_elapsed_seconds
            remaining = self._effective_duration - elapsed
            payload = {
                "session_elapsed_seconds": elapsed,   # engine will correct to session total
                "block_elapsed_seconds": elapsed,
                "block_remaining_seconds": max(0.0, remaining),
                "current_block_id": self._block.id,
                "server_epoch": time.time(),
            }
            if self._socketio:
                self._socketio.emit("timer:tick", payload, room="session:all")
            if _USE_EVENTLET:
                eventlet.sleep(interval)
            else:
                break

    def _expiry_waiter(self) -> None:
        """Sleep until effective block duration expires, then trigger callback."""
        remaining = self.block_remaining_seconds
        if remaining > 0:
            if _USE_EVENTLET:
                eventlet.sleep(remaining)
            else:
                time.sleep(remaining)
        if self._running:
            self._on_block_expired()

    def _start_overrun_ticker(self) -> None:
        if _USE_EVENTLET:
            eventlet.spawn(self._overrun_tick_loop)

    def _overrun_tick_loop(self) -> None:
        while self._running:
            if _USE_EVENTLET:
                eventlet.sleep(1.0)
            else:
                break
            if not self._running:
                break
            overrun_payload = {
                "block_id": self._block.id,
                "presenter_id": self._block.presenter_id,
                "presenter_name": "",  # engine will fill this in
                "overrun_seconds": self.overrun_seconds,
                "overrun_behavior": self._block.overrun_behavior.value,
            }
            if self._socketio:
                self._socketio.emit("block:overrun", overrun_payload, room="session:all")
