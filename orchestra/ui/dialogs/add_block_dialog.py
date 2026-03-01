"""
AddBlockDialog — create a new block in the timeline.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QSpinBox,
    QComboBox, QTextEdit, QDialogButtonBox, QLabel,
)

from orchestra.models.block import Block, EndCondition
from orchestra.models.timeline import Timeline
from orchestra.constants import DEFAULT_BLOCK_DURATION_SECONDS


class AddBlockDialog(QDialog):

    def __init__(self, timeline: Timeline, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Block")
        self.setModal(True)
        self.setMinimumWidth(400)
        self._timeline = timeline
        self.created_block: Optional[Block] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        self._presenter_combo = QComboBox()
        for p in self._timeline.presenters:
            self._presenter_combo.addItem(p.name, p.id)
        form.addRow("Presenter:", self._presenter_combo)

        last_slide = 1
        if self._timeline.blocks:
            last_slide = self._timeline.blocks[-1].slide_end + 1

        self._slide_start = QSpinBox(); self._slide_start.setRange(1, 9999)
        self._slide_start.setValue(last_slide)
        self._slide_end = QSpinBox(); self._slide_end.setRange(1, 9999)
        self._slide_end.setValue(last_slide)

        from PyQt6.QtWidgets import QHBoxLayout, QWidget
        slide_row_w = QWidget()
        slide_row = QHBoxLayout(slide_row_w)
        slide_row.setContentsMargins(0, 0, 0, 0)
        slide_row.addWidget(self._slide_start)
        slide_row.addWidget(QLabel("→"))
        slide_row.addWidget(self._slide_end)
        form.addRow("Slides:", slide_row_w)

        self._duration = QSpinBox()
        self._duration.setRange(1, 7200)
        self._duration.setValue(int(DEFAULT_BLOCK_DURATION_SECONDS))
        self._duration.setSuffix(" sec")
        form.addRow("Duration:", self._duration)

        self._end_cond = QComboBox()
        self._end_cond.addItem("Time", "either")
        self._end_cond.addItem("Click", "click")
        form.addRow("End condition:", self._end_cond)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Notes visible to presenter during this block…")
        self._notes.setMaximumHeight(60)
        form.addRow("Notes:", self._notes)

        layout.addLayout(form)

        self._error_label = QLabel("")
        self._error_label.setStyleSheet("color: #e85454;")
        layout.addWidget(self._error_label)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_accept(self):
        if not self._timeline.presenters:
            self._error_label.setText("Add at least one presenter first.")
            return
        pid = self._presenter_combo.currentData()
        start = self._slide_start.value()
        end   = self._slide_end.value()
        if end < start:
            self._error_label.setText("Slide end must be >= slide start.")
            return
        self.created_block = Block.create(
            presenter_id=pid,
            slide_start=start,
            slide_end=end,
            duration=self._duration.value(),
            end_condition=EndCondition(self._end_cond.currentData()),
            notes=self._notes.toPlainText(),
        )
        self.accept()
