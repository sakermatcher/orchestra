"""
PresenterPanel — right sidebar showing QR code, presenter list, and connection log.

Phase 1: Static structure with placeholders.
Phase 3: QR code generated from live server IP, connection log filled via bridge.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPlainTextEdit,
)
from PyQt6.QtGui import QFont
from datetime import datetime

from orchestra.bridge.qt_bridge import QtBridge
from orchestra.constants import QR_DISPLAY_SIZE
from orchestra.ui.theme import Colours


class PresenterPanel(QWidget):

    def __init__(self, bridge: QtBridge, engine, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._engine = engine
        self._build()
        self._connect_bridge()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Presenter list section
        presenters_label = QLabel("PRESENTERS")
        presenters_label.setObjectName("labelSectionHeader")
        layout.addWidget(presenters_label)

        self._presenter_list = QListWidget()
        self._presenter_list.setMaximumHeight(160)
        layout.addWidget(self._presenter_list)

        # QR / Join link section
        qr_label = QLabel("JOIN LINK")
        qr_label.setObjectName("labelSectionHeader")
        layout.addWidget(qr_label)

        self._qr_display = QLabel("Start a session to\ngenerate QR code")
        self._qr_display.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_display.setMinimumHeight(QR_DISPLAY_SIZE)
        self._qr_display.setStyleSheet(
            f"background:{Colours.BG_SURFACE}; border:1px solid {Colours.BORDER};"
            f"border-radius:4px; color:{Colours.TEXT_SECONDARY};"
        )
        layout.addWidget(self._qr_display)

        self._url_label = QLabel("")
        self._url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._url_label.setStyleSheet(f"color:{Colours.TEXT_SECONDARY}; font-size:11px;")
        self._url_label.setWordWrap(True)
        layout.addWidget(self._url_label)

        # Connection log section
        log_label = QLabel("CONNECTION LOG")
        log_label.setObjectName("labelSectionHeader")
        layout.addWidget(log_label)

        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumBlockCount(200)
        font = QFont("Consolas", 10)
        self._log.setFont(font)
        self._log.setStyleSheet(
            f"background:{Colours.BG_SURFACE}; border:1px solid {Colours.BORDER};"
            f"border-radius:4px;"
        )
        layout.addWidget(self._log)

    def _connect_bridge(self):
        self._bridge.presenter_connected.connect(self._on_connected)
        self._bridge.presenter_disconnected.connect(self._on_disconnected)

    def load_timeline_presenters(self, timeline) -> None:
        """Populate the presenter list from a timeline object."""
        self._presenter_list.clear()
        for p in timeline.presenters:
            item = QListWidgetItem(f"  {p.name}")
            item.setData(256, p.id)
            # Colour swatch via stylesheet on item
            self._presenter_list.addItem(item)

    def set_qr(self, qr_pixmap, url: str) -> None:
        """Display the QR code pixmap and URL string."""
        self._qr_display.setPixmap(
            qr_pixmap.scaled(QR_DISPLAY_SIZE, QR_DISPLAY_SIZE,
                             Qt.AspectRatioMode.KeepAspectRatio,
                             Qt.TransformationMode.SmoothTransformation)
        )
        self._url_label.setText(url)

    def _log_event(self, message: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        self._log.appendPlainText(f"[{ts}] {message}")

    @pyqtSlot(str, str)
    def _on_connected(self, presenter_id: str, name: str):
        self._log_event(f"{name} connected")

    @pyqtSlot(str, str)
    def _on_disconnected(self, presenter_id: str, name: str):
        self._log_event(f"{name} disconnected")
