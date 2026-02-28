"""
BlockEditorPanel — properties form for the currently selected timeline block.
Shown at the bottom of EditorPanel, collapsible.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QSpinBox, QDoubleSpinBox, QComboBox,
    QTextEdit, QTableWidget, QTableWidgetItem, QPushButton,
    QHeaderView,
)

from orchestra.models.block import Block, EndCondition, OverrunBehavior
from orchestra.models.timeline import Timeline
from orchestra.models.vibration import VibrationEvent
from orchestra.ui.theme import Colours


class BlockEditorPanel(QWidget):

    block_changed = pyqtSignal(str)   # block_id

    def __init__(self, parent=None):
        super().__init__(parent)
        self._block: Optional[Block] = None
        self._timeline: Optional[Timeline] = None
        self._loading = False
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        header_row = QHBoxLayout()
        header = QLabel("BLOCK PROPERTIES")
        header.setObjectName("labelSectionHeader")
        header_row.addWidget(header)
        header_row.addStretch()
        layout.addLayout(header_row)

        # Main form + vibrations side by side
        cols = QHBoxLayout()

        # Left: form fields
        form = QFormLayout()
        form.setSpacing(6)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self._presenter_combo = QComboBox()
        self._presenter_combo.currentIndexChanged.connect(self._on_field_changed)
        form.addRow("Presenter:", self._presenter_combo)

        slide_row = QHBoxLayout()
        self._slide_start = QSpinBox(); self._slide_start.setRange(1, 9999)
        self._slide_end   = QSpinBox(); self._slide_end.setRange(1, 9999)
        self._slide_start.valueChanged.connect(self._on_field_changed)
        self._slide_end.valueChanged.connect(self._on_field_changed)
        slide_row.addWidget(self._slide_start)
        slide_row.addWidget(QLabel("→"))
        slide_row.addWidget(self._slide_end)
        form.addRow("Slides:", slide_row)

        self._duration = QDoubleSpinBox()
        self._duration.setRange(1, 7200)
        self._duration.setSuffix(" sec")
        self._duration.valueChanged.connect(self._on_field_changed)
        form.addRow("Duration:", self._duration)

        self._end_cond = QComboBox()
        self._end_cond.addItems(["time", "click", "either"])
        self._end_cond.currentIndexChanged.connect(self._on_field_changed)
        form.addRow("End on:", self._end_cond)

        self._overrun = QComboBox()
        self._overrun.addItems(["auto_advance", "alert_only"])
        self._overrun.currentIndexChanged.connect(self._on_field_changed)
        form.addRow("Overrun:", self._overrun)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Block notes (shown to presenter)…")
        self._notes.setMaximumHeight(60)
        self._notes.textChanged.connect(self._on_field_changed)
        form.addRow("Notes:", self._notes)

        form_widget = QWidget()
        form_widget.setLayout(form)
        cols.addWidget(form_widget, stretch=1)

        # Right: vibrations table
        vib_layout = QVBoxLayout()
        vib_header = QLabel("VIBRATIONS")
        vib_header.setObjectName("labelSectionHeader")
        vib_layout.addWidget(vib_header)

        self._vib_table = QTableWidget(0, 3)
        self._vib_table.setHorizontalHeaderLabels(["Label", "Sec before end", "Type"])
        self._vib_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._vib_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
        self._vib_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        self._vib_table.setColumnWidth(1, 110)
        self._vib_table.setColumnWidth(2, 70)
        self._vib_table.setMinimumWidth(300)
        self._vib_table.itemChanged.connect(self._on_vib_changed)
        vib_layout.addWidget(self._vib_table)

        vib_btn_row = QHBoxLayout()
        btn_add_vib = QPushButton("+ Vibration")
        btn_add_vib.clicked.connect(self._on_add_vibration)
        btn_del_vib = QPushButton("✕")
        btn_del_vib.setFixedWidth(28)
        btn_del_vib.clicked.connect(self._on_delete_vibration)
        vib_btn_row.addWidget(btn_add_vib)
        vib_btn_row.addWidget(btn_del_vib)
        vib_btn_row.addStretch()
        vib_layout.addLayout(vib_btn_row)

        vib_widget = QWidget()
        vib_widget.setLayout(vib_layout)
        cols.addWidget(vib_widget, stretch=1)

        layout.addLayout(cols)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load_block(self, block: Block, timeline: Timeline) -> None:
        self._loading = True
        self._block = block
        self._timeline = timeline

        # Presenter combo
        self._presenter_combo.clear()
        for p in timeline.presenters:
            self._presenter_combo.addItem(p.name, p.id)
        idx = next((i for i, p in enumerate(timeline.presenters)
                    if p.id == block.presenter_id), 0)
        self._presenter_combo.setCurrentIndex(idx)

        self._slide_start.setValue(block.slide_start)
        self._slide_end.setValue(block.slide_end)
        self._duration.setValue(block.duration)
        self._end_cond.setCurrentText(block.end_condition.value)
        self._overrun.setCurrentText(block.overrun_behavior.value)
        self._notes.blockSignals(True)
        self._notes.setPlainText(block.notes)
        self._notes.blockSignals(False)

        # Vibrations
        self._vib_table.blockSignals(True)
        self._vib_table.setRowCount(0)
        for v in block.vibrations:
            self._add_vibration_row(v.label, v.seconds_before_end, v.type)
        self._vib_table.blockSignals(False)

        self._loading = False

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _on_field_changed(self, *args):
        if self._loading or not self._block:
            return
        pid = self._presenter_combo.currentData()
        if pid:
            self._block.presenter_id = pid
        self._block.slide_start = self._slide_start.value()
        self._block.slide_end   = self._slide_end.value()
        self._block.duration    = self._duration.value()
        self._block.end_condition    = EndCondition(self._end_cond.currentText())
        self._block.overrun_behavior = OverrunBehavior(self._overrun.currentText())
        self._block.notes = self._notes.toPlainText()
        if self._timeline:
            self._timeline.recompute_start_times()
        self.block_changed.emit(self._block.id)

    def _on_vib_changed(self, item):
        if self._loading or not self._block:
            return
        self._sync_vibrations_from_table()
        self.block_changed.emit(self._block.id)

    def _on_add_vibration(self):
        if not self._block:
            return
        self._vib_table.blockSignals(True)
        self._add_vibration_row("Warning", 30.0, "short")
        self._vib_table.blockSignals(False)
        self._sync_vibrations_from_table()
        self.block_changed.emit(self._block.id)

    def _on_delete_vibration(self):
        row = self._vib_table.currentRow()
        if row >= 0:
            self._vib_table.removeRow(row)
            self._sync_vibrations_from_table()
            self.block_changed.emit(self._block.id)

    def _add_vibration_row(self, label: str, sec: float, vtype: str):
        row = self._vib_table.rowCount()
        self._vib_table.insertRow(row)
        self._vib_table.setItem(row, 0, QTableWidgetItem(label))
        self._vib_table.setItem(row, 1, QTableWidgetItem(str(sec)))
        type_combo = QComboBox()
        type_combo.addItems(["short", "long"])
        type_combo.setCurrentText(vtype)
        type_combo.currentIndexChanged.connect(self._on_vib_combo_changed)
        self._vib_table.setCellWidget(row, 2, type_combo)

    def _on_vib_combo_changed(self, _):
        if not self._loading:
            self._sync_vibrations_from_table()
            if self._block:
                self.block_changed.emit(self._block.id)

    def _sync_vibrations_from_table(self):
        if not self._block:
            return
        vibs = []
        for row in range(self._vib_table.rowCount()):
            label_item = self._vib_table.item(row, 0)
            sec_item   = self._vib_table.item(row, 1)
            type_widget = self._vib_table.cellWidget(row, 2)
            if label_item and sec_item and type_widget:
                try:
                    sec = float(sec_item.text())
                except ValueError:
                    sec = 30.0
                existing = self._block.vibrations[row] if row < len(self._block.vibrations) else None
                vid = existing.id if existing else None
                import uuid
                vibs.append(VibrationEvent(
                    id=vid or str(uuid.uuid4()),
                    label=label_item.text(),
                    seconds_before_end=sec,
                    type=type_widget.currentText(),
                ))
        self._block.vibrations = vibs


from PyQt6.QtCore import Qt
