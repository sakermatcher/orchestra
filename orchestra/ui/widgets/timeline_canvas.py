"""
TimelineCanvas — custom-painted QWidget implementing the timeline editor.

Features:
  - Horizontal time ruler (MM:SS)
  - One horizontal swimlane per presenter
  - Block rectangles, click-to-select, drag-to-move (change presenter),
    drag-to-resize (change duration)
  - Zoom via Ctrl+scroll
  - Right-click context menu for block actions
"""
from __future__ import annotations
from typing import Optional
import math

from PyQt6.QtCore import Qt, QRect, QPoint, pyqtSignal, QSize
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QFontMetrics,
    QCursor, QWheelEvent, QMouseEvent, QPaintEvent, QContextMenuEvent,
)
from PyQt6.QtWidgets import QWidget, QScrollArea, QMenu, QSizePolicy

from orchestra.models.timeline import Timeline
from orchestra.models.block import Block
from orchestra.ui.theme import Colours
from orchestra.constants import (
    TIMELINE_RULER_HEIGHT,
    TIMELINE_LANE_HEIGHT,
    TIMELINE_LANE_LABEL_WIDTH,
    TIMELINE_DEFAULT_ZOOM_PX_PER_SEC,
    TIMELINE_MIN_ZOOM_PX_PER_SEC,
    TIMELINE_MAX_ZOOM_PX_PER_SEC,
    BLOCK_MIN_DURATION_SECONDS,
)

_RESIZE_HANDLE_WIDTH = 8   # pixels on each side of block edge for resize hit zone
_BLOCK_VERTICAL_PADDING = 8


class TimelineCanvas(QWidget):

    block_selected  = pyqtSignal(str)   # block_id
    timeline_mutated = pyqtSignal()     # any drag/resize completed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._timeline: Optional[Timeline] = None
        self._zoom: float = TIMELINE_DEFAULT_ZOOM_PX_PER_SEC  # px per second
        self._selected_block_id: Optional[str] = None

        # Drag state
        self._drag_mode: str = ""              # "" | "move" | "resize_left" | "resize_right"
        self._drag_block: Optional[Block] = None
        self._drag_start_pos: QPoint = QPoint()
        self._drag_original_duration: float = 0.0
        self._drag_original_presenter_idx: int = 0

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(TIMELINE_RULER_HEIGHT + TIMELINE_LANE_HEIGHT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_timeline(self, timeline: Optional[Timeline]) -> None:
        self._timeline = timeline
        self._selected_block_id = None
        self._update_size()
        self.update()

    @property
    def selected_block_id(self) -> Optional[str]:
        return self._selected_block_id

    # ------------------------------------------------------------------
    # Coordinate helpers
    # ------------------------------------------------------------------

    def _sec_to_x(self, seconds: float) -> int:
        return TIMELINE_LANE_LABEL_WIDTH + int(seconds * self._zoom)

    def _x_to_sec(self, x: int) -> float:
        return max(0.0, (x - TIMELINE_LANE_LABEL_WIDTH) / self._zoom)

    def _presenter_y(self, presenter_idx: int) -> int:
        return TIMELINE_RULER_HEIGHT + presenter_idx * TIMELINE_LANE_HEIGHT

    def _y_to_presenter_idx(self, y: int) -> int:
        if not self._timeline:
            return -1
        idx = (y - TIMELINE_RULER_HEIGHT) // TIMELINE_LANE_HEIGHT
        return max(0, min(idx, len(self._timeline.presenters) - 1))

    def _block_rect(self, block: Block, presenter_idx: int) -> QRect:
        x = self._sec_to_x(block.start_time)
        w = max(4, int(block.duration * self._zoom))
        y = self._presenter_y(presenter_idx) + _BLOCK_VERTICAL_PADDING
        h = TIMELINE_LANE_HEIGHT - 2 * _BLOCK_VERTICAL_PADDING
        return QRect(x, y, w, h)

    def _update_size(self) -> None:
        if not self._timeline:
            return
        n_lanes = max(1, len(self._timeline.presenters))
        total_sec = max(60.0, self._timeline.total_duration + 30)
        w = TIMELINE_LANE_LABEL_WIDTH + int(total_sec * self._zoom) + 40
        h = TIMELINE_RULER_HEIGHT + n_lanes * TIMELINE_LANE_HEIGHT
        self.setMinimumSize(w, h)

    # ------------------------------------------------------------------
    # Paint
    # ------------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Background
        painter.fillRect(0, 0, w, h, QColor(Colours.BG_PANEL))

        if not self._timeline:
            painter.setPen(QColor(Colours.TEXT_SECONDARY))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "No timeline loaded.\nCreate or select a timeline from the sidebar.")
            return

        self._paint_ruler(painter, w)
        self._paint_lanes(painter, w)
        self._paint_blocks(painter)
        painter.end()

    def _paint_ruler(self, painter: QPainter, width: int) -> None:
        # Background
        painter.fillRect(0, 0, width, TIMELINE_RULER_HEIGHT, QColor(Colours.BG_DARKEST))
        painter.fillRect(0, 0, TIMELINE_LANE_LABEL_WIDTH, TIMELINE_RULER_HEIGHT,
                         QColor(Colours.BG_DARKEST))

        # Vertical border
        painter.setPen(QPen(QColor(Colours.BORDER), 1))
        painter.drawLine(0, TIMELINE_RULER_HEIGHT, width, TIMELINE_RULER_HEIGHT)

        if not self._timeline:
            return

        total_sec = max(60.0, self._timeline.total_duration + 30)

        # Determine tick interval (1, 5, 10, 30, 60s depending on zoom)
        min_px_between_ticks = 40
        candidate_intervals = [1, 5, 10, 15, 30, 60, 120, 300, 600]
        tick_interval = 60
        for ci in candidate_intervals:
            if ci * self._zoom >= min_px_between_ticks:
                tick_interval = ci
                break

        font = QFont("Segoe UI", 9)
        painter.setFont(font)
        painter.setPen(QColor(Colours.TEXT_SECONDARY))

        t = 0
        while t <= total_sec + tick_interval:
            x = self._sec_to_x(t)
            if x > width:
                break
            m = t // 60
            s = t % 60
            label = f"{m}:{s:02d}"
            painter.drawLine(x, TIMELINE_RULER_HEIGHT - 6, x, TIMELINE_RULER_HEIGHT)
            painter.drawText(x + 3, TIMELINE_RULER_HEIGHT - 8, label)
            t += tick_interval

    def _paint_lanes(self, painter: QPainter, width: int) -> None:
        if not self._timeline:
            return
        for i, presenter in enumerate(self._timeline.presenters):
            y = self._presenter_y(i)
            # Alternating lane background
            bg = Colours.BG_PANEL if i % 2 == 0 else Colours.BG_DARK
            painter.fillRect(TIMELINE_LANE_LABEL_WIDTH, y, width, TIMELINE_LANE_HEIGHT,
                             QColor(bg))
            # Lane border
            painter.setPen(QPen(QColor(Colours.BORDER), 1))
            painter.drawLine(0, y + TIMELINE_LANE_HEIGHT, width, y + TIMELINE_LANE_HEIGHT)

            # Presenter label
            painter.fillRect(0, y, TIMELINE_LANE_LABEL_WIDTH, TIMELINE_LANE_HEIGHT,
                             QColor(Colours.BG_DARKEST))
            # Colour swatch
            swatch_rect = QRect(6, y + TIMELINE_LANE_HEIGHT // 2 - 7, 14, 14)
            painter.setBrush(QBrush(QColor(presenter.color)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(swatch_rect, 3, 3)
            # Name
            painter.setPen(QColor(Colours.TEXT_PRIMARY))
            font = QFont("Segoe UI", 10)
            painter.setFont(font)
            text_rect = QRect(26, y, TIMELINE_LANE_LABEL_WIDTH - 32, TIMELINE_LANE_HEIGHT)
            painter.drawText(text_rect,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             presenter.name)
            # Right divider
            painter.setPen(QPen(QColor(Colours.BORDER), 1))
            painter.drawLine(TIMELINE_LANE_LABEL_WIDTH - 1, y,
                             TIMELINE_LANE_LABEL_WIDTH - 1, y + TIMELINE_LANE_HEIGHT)

    def _paint_blocks(self, painter: QPainter) -> None:
        if not self._timeline:
            return

        presenter_idx_map = {p.id: i for i, p in enumerate(self._timeline.presenters)}
        font = QFont("Segoe UI", 9)
        painter.setFont(font)

        for block in self._timeline.blocks:
            idx = presenter_idx_map.get(block.presenter_id)
            if idx is None:
                continue
            presenter = self._timeline.presenters[idx]
            rect = self._block_rect(block, idx)

            is_selected = block.id == self._selected_block_id

            # Fill
            base_color = QColor(presenter.color)
            fill_color = base_color.lighter(130) if is_selected else base_color
            fill_color.setAlpha(210)
            painter.setBrush(QBrush(fill_color))

            # Border
            if is_selected:
                pen = QPen(QColor("#ffffff"), 2)
            else:
                pen = QPen(base_color.darker(140), 1)
            painter.setPen(pen)
            painter.drawRoundedRect(rect, 4, 4)

            # Resize handles (subtle)
            if is_selected and rect.width() > 20:
                handle_color = QColor(255, 255, 255, 100)
                painter.fillRect(rect.x(), rect.y(), _RESIZE_HANDLE_WIDTH, rect.height(),
                                 handle_color)
                painter.fillRect(rect.right() - _RESIZE_HANDLE_WIDTH, rect.y(),
                                 _RESIZE_HANDLE_WIDTH, rect.height(), handle_color)

            # Block label (duration + slide range)
            label = f"S{block.slide_start}–{block.slide_end}"
            dur_m = int(block.duration) // 60
            dur_s = int(block.duration) % 60
            label += f"  {dur_m}:{dur_s:02d}"
            if block.vibrations:
                label += f"  ({len(block.vibrations)}v)"

            painter.setPen(QColor(Colours.TEXT_INVERSE))
            text_rect = rect.adjusted(_RESIZE_HANDLE_WIDTH + 2, 2, -_RESIZE_HANDLE_WIDTH - 2, -2)
            painter.drawText(text_rect,
                             Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                             label)

    # ------------------------------------------------------------------
    # Mouse interaction
    # ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            return

        hit = self._hit_test(event.pos())
        if hit is None:
            self._selected_block_id = None
            self.update()
            return

        block, mode = hit
        self._selected_block_id = block.id
        self._drag_block = block
        self._drag_mode = mode
        self._drag_start_pos = event.pos()
        self._drag_original_duration = block.duration

        if self._timeline:
            presenter_idx_map = {p.id: i for i, p in enumerate(self._timeline.presenters)}
            self._drag_original_presenter_idx = presenter_idx_map.get(block.presenter_id, 0)

        self.block_selected.emit(block.id)
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_block and self._drag_mode:
            dx = event.pos().x() - self._drag_start_pos.x()
            d_sec = dx / self._zoom

            if self._drag_mode == "resize_right":
                new_dur = max(BLOCK_MIN_DURATION_SECONDS,
                              self._drag_original_duration + d_sec)
                self._drag_block.duration = new_dur
                if self._timeline:
                    self._timeline.recompute_start_times()
                    self._update_size()
                self.update()

            elif self._drag_mode == "resize_left":
                # Shrink from the left — shift start_time and shrink duration
                clamped = min(d_sec, self._drag_original_duration - BLOCK_MIN_DURATION_SECONDS)
                self._drag_block.duration = max(BLOCK_MIN_DURATION_SECONDS,
                                                self._drag_original_duration - clamped)
                if self._timeline:
                    self._timeline.recompute_start_times()
                self.update()

            elif self._drag_mode == "move":
                # Reorder presenter lane (vertical drag)
                if self._timeline:
                    new_p_idx = self._y_to_presenter_idx(event.pos().y())
                    if new_p_idx != self._drag_original_presenter_idx:
                        new_pid = self._timeline.presenters[new_p_idx].id
                        self._drag_block.presenter_id = new_pid
                        self._drag_original_presenter_idx = new_p_idx
                        self.update()
        else:
            # Cursor update on hover
            hit = self._hit_test(event.pos())
            if hit:
                _, mode = hit
                if mode in ("resize_left", "resize_right"):
                    self.setCursor(QCursor(Qt.CursorShape.SizeHorCursor))
                else:
                    self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._drag_mode and self._drag_block:
            if self._timeline:
                self._timeline.recompute_start_times()
            self.timeline_mutated.emit()
            self._update_size()
            self.update()
        self._drag_block = None
        self._drag_mode = ""
        self.unsetCursor()

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.15 if delta > 0 else 1 / 1.15
            self._zoom = max(TIMELINE_MIN_ZOOM_PX_PER_SEC,
                             min(TIMELINE_MAX_ZOOM_PX_PER_SEC, self._zoom * factor))
            self._update_size()
            self.update()
            event.accept()
        else:
            super().wheelEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        hit = self._hit_test(event.pos())
        if not hit:
            return
        block, _ = hit
        menu = QMenu(self)
        menu.addAction(f"Edit Block…", lambda: self.block_selected.emit(block.id))
        menu.addSeparator()
        delete_act = menu.addAction("Delete Block")
        delete_act.triggered.connect(lambda: self._delete_block(block.id))
        menu.exec(event.globalPos())

    def _delete_block(self, block_id: str) -> None:
        if self._timeline:
            self._timeline.remove_block(block_id)
            self._selected_block_id = None
            self._update_size()
            self.timeline_mutated.emit()
            self.update()

    # ------------------------------------------------------------------
    # Hit testing
    # ------------------------------------------------------------------

    def _hit_test(self, pos: QPoint) -> Optional[tuple[Block, str]]:
        if not self._timeline:
            return None

        presenter_idx_map = {p.id: i for i, p in enumerate(self._timeline.presenters)}

        for block in self._timeline.blocks:
            idx = presenter_idx_map.get(block.presenter_id)
            if idx is None:
                continue
            rect = self._block_rect(block, idx)
            if not rect.contains(pos):
                continue

            # Determine mode from x position
            if pos.x() <= rect.x() + _RESIZE_HANDLE_WIDTH:
                return block, "resize_left"
            if pos.x() >= rect.right() - _RESIZE_HANDLE_WIDTH:
                return block, "resize_right"
            return block, "move"

        return None
