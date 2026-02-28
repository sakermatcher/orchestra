"""
SessionPanel — live session monitor. Shown on WorkspaceStack index 1.
"""
from __future__ import annotations
import math
from PyQt6.QtCore import Qt, QTimer, pyqtSlot, QRect, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QSizePolicy, QScrollArea, QGridLayout,
)

from orchestra.bridge.qt_bridge import QtBridge
from orchestra.ui.theme import Colours


# ---------------------------------------------------------------------------
# BlockProgressTrack — proportional block timeline with active/overrun state
# ---------------------------------------------------------------------------

class BlockProgressTrack(QWidget):
    """
    Horizontal progress track showing all blocks proportionally.

    - Each block is a colored rectangle (presenter color).
    - The active block has an animated pulsing border.
    - Overrun is shown as a red extension beyond the block's right edge.
    - A time needle (thin white line) marks current elapsed position.
    """

    HEIGHT = 56

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(self.HEIGHT)
        self.setMaximumHeight(self.HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self._blocks: list[dict] = []          # [{block_id, presenter_color, duration}]
        self._total_duration: float = 0.0
        self._active_block_id: str | None = None
        self._session_elapsed: float = 0.0
        self._block_elapsed: float = 0.0
        self._overrun_seconds: float = 0.0

        # Pulse animation
        self._pulse_phase: float = 0.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.setInterval(50)
        self._pulse_timer.timeout.connect(self._tick_pulse)

    def set_blocks(self, blocks_summary: list[dict], total_duration: float):
        self._blocks = blocks_summary
        self._total_duration = total_duration
        self._active_block_id = None
        self._session_elapsed = 0.0
        self._overrun_seconds = 0.0
        self.update()

    def set_active_block(self, block_id: str):
        self._active_block_id = block_id
        self._pulse_phase = 0.0
        self._pulse_timer.start()
        self.update()

    def set_elapsed(self, session_elapsed: float, block_elapsed: float, overrun: float = 0.0):
        self._session_elapsed = session_elapsed
        self._block_elapsed = block_elapsed
        self._overrun_seconds = overrun
        self.update()

    def clear(self):
        self._blocks = []
        self._total_duration = 0.0
        self._active_block_id = None
        self._session_elapsed = 0.0
        self._overrun_seconds = 0.0
        self._pulse_timer.stop()
        self.update()

    def _tick_pulse(self):
        self._pulse_phase = (self._pulse_phase + 0.1) % (2 * math.pi)
        self.update()

    def paintEvent(self, event):  # noqa: N802
        if not self._blocks or self._total_duration <= 0:
            painter = QPainter(self)
            painter.fillRect(self.rect(), QColor(Colours.BG_SURFACE))
            painter.setPen(QColor(Colours.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Session blocks will appear here.")
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()
        px_per_sec = w / self._total_duration

        # Background
        painter.fillRect(self.rect(), QColor(Colours.BG_SURFACE))

        # Draw block rectangles
        x_cursor = 0.0
        active_rect: QRectF | None = None

        for blk in self._blocks:
            bw = blk["duration"] * px_per_sec
            rect = QRectF(x_cursor, 4, bw - 1, h - 8)
            color = QColor(blk.get("presenter_color", "#888"))
            color.setAlpha(180)

            if blk["block_id"] == self._active_block_id:
                color.setAlpha(240)
                active_rect = rect

            painter.fillRect(rect, color)
            x_cursor += bw

        # Draw overrun extension on active block
        if active_rect and self._overrun_seconds > 0:
            overrun_w = self._overrun_seconds * px_per_sec
            overrun_rect = QRectF(
                active_rect.right(), active_rect.top(),
                overrun_w, active_rect.height()
            )
            overrun_color = QColor(Colours.ACCENT_RED)
            overrun_color.setAlpha(200)
            painter.fillRect(overrun_rect, overrun_color)

        # Pulsing border on active block
        if active_rect:
            pulse_alpha = int(128 + 127 * math.sin(self._pulse_phase))
            pen_color = QColor("#ffffff")
            pen_color.setAlpha(pulse_alpha)
            painter.setPen(QPen(pen_color, 2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(active_rect.adjusted(1, 1, -1, -1))

        # Time needle
        if self._session_elapsed > 0 and self._total_duration > 0:
            needle_x = min(self._session_elapsed * px_per_sec, w - 1)
            needle_pen = QPen(QColor("#ffffff"), 1)
            painter.setPen(needle_pen)
            painter.drawLine(int(needle_x), 0, int(needle_x), h)

        # Block separator lines
        sep_pen = QPen(QColor(Colours.BG_DARK), 1)
        painter.setPen(sep_pen)
        x_sep = 0.0
        for blk in self._blocks:
            x_sep += blk["duration"] * px_per_sec
            painter.drawLine(int(x_sep), 0, int(x_sep), h)


# ---------------------------------------------------------------------------
# PresenterCard — single card in the connected-presenter grid
# ---------------------------------------------------------------------------

class PresenterCard(QFrame):

    def __init__(self, name: str, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(56)
        self._color = color
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setFixedWidth(18)
        self._dot.setStyleSheet(f"color:{Colours.TEXT_SECONDARY}; font-size:14px;")

        self._name_label = QLabel(name)
        self._name_label.setStyleSheet(f"color:{Colours.TEXT_PRIMARY}; font-weight:600;")

        self._status_label = QLabel("waiting")
        self._status_label.setStyleSheet(f"color:{Colours.TEXT_SECONDARY}; font-size:11px;")

        layout.addWidget(self._dot)
        layout.addWidget(self._name_label)
        layout.addStretch()
        layout.addWidget(self._status_label)

        self.setStyleSheet(
            f"background:{Colours.BG_SURFACE}; border:1px solid {Colours.BORDER};"
            "border-radius:4px;"
        )
        self.set_disconnected()

    def set_connected(self):
        self._dot.setStyleSheet(f"color:{self._color}; font-size:14px;")
        self._status_label.setText("connected")
        self._status_label.setStyleSheet(f"color:{Colours.ACCENT_GREEN}; font-size:11px;")

    def set_disconnected(self):
        self._dot.setStyleSheet(f"color:{Colours.TEXT_SECONDARY}; font-size:14px;")
        self._status_label.setText("disconnected")
        self._status_label.setStyleSheet(f"color:{Colours.TEXT_SECONDARY}; font-size:11px;")

    def set_presenting(self):
        self._dot.setStyleSheet(f"color:{self._color}; font-size:14px;")
        self._status_label.setText("▶ presenting")
        self._status_label.setStyleSheet(f"color:{self._color}; font-size:11px; font-weight:700;")


# ---------------------------------------------------------------------------
# SessionPanel
# ---------------------------------------------------------------------------

class SessionPanel(QWidget):

    def __init__(self, bridge: QtBridge, engine, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._engine = engine
        self._presenter_cards: dict[str, PresenterCard] = {}  # presenter_id → card
        self._build()
        self._connect_bridge()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # State badge + timer row
        top_row = QHBoxLayout()
        self._state_badge = QLabel("WARMUP")
        self._state_badge.setStyleSheet(
            f"background:{Colours.STATE_WARMUP}; color:#000; font-weight:700;"
            f"border-radius:4px; padding:3px 10px;"
        )
        self._elapsed_label = QLabel("00:00 / --:--")
        self._elapsed_label.setStyleSheet("font-size:22px; font-weight:600;")
        self._block_label = QLabel("Waiting for session…")
        self._block_label.setStyleSheet(f"color:{Colours.TEXT_SECONDARY};")

        top_row.addWidget(self._state_badge)
        top_row.addSpacing(12)
        top_row.addWidget(self._elapsed_label)
        top_row.addStretch()
        top_row.addWidget(self._block_label)
        layout.addLayout(top_row)

        # Block progress track
        self._progress_track = BlockProgressTrack()
        layout.addWidget(self._progress_track)

        # Connected presenter grid
        grid_label = QLabel("Presenters")
        grid_label.setStyleSheet(
            f"color:{Colours.TEXT_SECONDARY}; font-size:11px; font-weight:600; text-transform:uppercase;"
        )
        layout.addWidget(grid_label)

        self._presenter_grid = QGridLayout()
        self._presenter_grid.setSpacing(6)
        self._presenter_grid_widget = QWidget()
        self._presenter_grid_widget.setLayout(self._presenter_grid)
        layout.addWidget(self._presenter_grid_widget)

        layout.addStretch()

        # Control bar
        ctrl_row = QHBoxLayout()
        self._btn_go = QPushButton("GO  —  Start Presentation")
        self._btn_go.setObjectName("btnSuccess")
        self._btn_go.clicked.connect(self._on_go)

        self._btn_pause = QPushButton("Pause")
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_pause.setVisible(False)

        self._btn_skip = QPushButton("Skip Block")
        self._btn_skip.clicked.connect(self._on_skip)
        self._btn_skip.setVisible(False)

        self._btn_abort = QPushButton("Abort Session")
        self._btn_abort.setObjectName("btnDanger")
        self._btn_abort.clicked.connect(self._on_abort)

        ctrl_row.addWidget(self._btn_go)
        ctrl_row.addWidget(self._btn_pause)
        ctrl_row.addWidget(self._btn_skip)
        ctrl_row.addStretch()
        ctrl_row.addWidget(self._btn_abort)
        layout.addLayout(ctrl_row)

    def _connect_bridge(self):
        self._bridge.session_state_changed.connect(self._on_state_changed)
        self._bridge.timer_tick.connect(self._on_timer_tick)
        self._bridge.block_activated.connect(self._on_block_activated)
        self._bridge.block_completed.connect(self._on_block_completed)
        self._bridge.presenter_connected.connect(self._on_presenter_connected)
        self._bridge.presenter_disconnected.connect(self._on_presenter_disconnected)

    # ------------------------------------------------------------------
    # Bridge slots
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def _on_state_changed(self, state: str):
        state_map = {
            "warmup":    (Colours.STATE_WARMUP,    "WARMUP"),
            "running":   (Colours.STATE_RUNNING,   "RUNNING"),
            "paused":    (Colours.STATE_PAUSED,    "PAUSED"),
            "completed": (Colours.STATE_COMPLETED, "COMPLETE"),
            "aborted":   (Colours.STATE_ABORTED,   "ABORTED"),
        }
        color, label = state_map.get(state, (Colours.STATE_IDLE, state.upper()))
        self._state_badge.setText(label)
        self._state_badge.setStyleSheet(
            f"background:{color}; color:#000; font-weight:700;"
            f"border-radius:4px; padding:3px 10px;"
        )
        self._btn_go.setVisible(state == "warmup")
        self._btn_pause.setVisible(state in ("running", "paused"))
        self._btn_skip.setVisible(state == "running")
        self._btn_pause.setText("Resume" if state == "paused" else "Pause")

        if state in ("completed", "aborted", "idle"):
            self._progress_track.clear()

    @pyqtSlot(dict)
    def _on_timer_tick(self, payload: dict):
        session_elapsed = payload.get("session_elapsed_seconds", 0.0)
        block_elapsed = payload.get("block_elapsed_seconds", 0.0)
        overrun = max(0.0, block_elapsed - payload.get("block_duration_seconds", 0.0))

        em = int(session_elapsed) // 60
        es = int(session_elapsed) % 60
        self._elapsed_label.setText(f"{em:02d}:{es:02d}")
        self._progress_track.set_elapsed(session_elapsed, block_elapsed, overrun)

    @pyqtSlot(dict)
    def _on_block_activated(self, payload: dict):
        idx = payload.get("block_index", 0) + 1
        total = payload.get("total_blocks", 0)
        name = payload.get("presenter_name", "?")
        self._block_label.setText(f"Block {idx}/{total}  —  {name}")

        block_id = payload.get("block_id")
        presenter_id = payload.get("presenter_id")

        self._progress_track.set_active_block(block_id)

        # Update presenter card to "presenting"
        for pid, card in self._presenter_cards.items():
            if pid == presenter_id:
                card.set_presenting()
            else:
                # Re-check if connected
                pass

        # If we have blocks summary in the engine, rebuild progress track
        if self._engine:
            snap = self._engine.get_session_snapshot()
            if snap.get("blocks_summary"):
                total_dur = sum(b["duration"] for b in snap["blocks_summary"])
                self._progress_track.set_blocks(snap["blocks_summary"], total_dur)
                self._progress_track.set_active_block(block_id)

    @pyqtSlot(dict)
    def _on_block_completed(self, payload: dict):
        pass  # progress track needle will catch up via timer_tick

    @pyqtSlot(str, str)
    def _on_presenter_connected(self, presenter_id: str, name: str):
        if presenter_id in self._presenter_cards:
            self._presenter_cards[presenter_id].set_connected()

    @pyqtSlot(str, str)
    def _on_presenter_disconnected(self, presenter_id: str, name: str):
        if presenter_id in self._presenter_cards:
            self._presenter_cards[presenter_id].set_disconnected()

    # ------------------------------------------------------------------
    # Public API — called by MainWindow when session starts
    # ------------------------------------------------------------------

    def setup_for_session(self, presenters: list[dict], blocks_summary: list[dict],
                          total_duration: float):
        """Called when session:warmup triggers. Builds presenter cards and progress track."""
        # Clear existing cards
        while self._presenter_grid.count():
            item = self._presenter_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._presenter_cards.clear()

        # Build new cards (up to 2 columns)
        for i, p in enumerate(presenters):
            card = PresenterCard(p["name"], p["color"])
            self._presenter_cards[p["id"]] = card
            row, col = divmod(i, 2)
            self._presenter_grid.addWidget(card, row, col)

        # Initialize progress track
        if blocks_summary and total_duration > 0:
            self._progress_track.set_blocks(blocks_summary, total_duration)

    # ------------------------------------------------------------------
    # Button handlers
    # ------------------------------------------------------------------

    def _on_go(self):
        if self._engine:
            self._engine.operator_go()

    def _on_pause(self):
        if self._engine:
            self._engine.toggle_pause()

    def _on_skip(self):
        if self._engine:
            self._engine.skip_current_block()

    def _on_abort(self):
        from orchestra.ui.dialogs.confirm_dialog import ConfirmDialog
        dlg = ConfirmDialog("Abort Session",
                            "Abort the current session?",
                            parent=self)
        if dlg.exec() and self._engine:
            self._engine.abort_session()
