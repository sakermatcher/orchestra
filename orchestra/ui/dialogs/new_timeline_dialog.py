"""
NewTimelineDialog — prompts for a timeline name and creates the object.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel,
)

from orchestra.models.timeline import Timeline
from orchestra.storage.timeline_store import save_timeline


class NewTimelineDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("New Timeline")
        self.setModal(True)
        self.setMinimumWidth(380)
        self.created_timeline: Optional[Timeline] = None
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("e.g. Q3 Investor Day")
        form.addRow("Timeline name:", self._name_edit)
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

        self._name_edit.setFocus()

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            self._error_label.setText("Name is required.")
            return
        self.created_timeline = Timeline.create(name=name)
        save_timeline(self.created_timeline)
        self.accept()
