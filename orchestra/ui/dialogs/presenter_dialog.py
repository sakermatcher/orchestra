"""
PresenterDialog — add or edit a presenter (name + color).
"""
from __future__ import annotations
from typing import Optional, List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QPushButton, QDialogButtonBox, QColorDialog, QLabel, QHBoxLayout,
)

from orchestra.models.presenter import Presenter
from orchestra.ui.theme import Colours


class PresenterDialog(QDialog):

    def __init__(self, presenter: Optional[Presenter] = None,
                 used_colors: Optional[List[str]] = None,
                 parent=None):
        super().__init__(parent)
        self.setWindowTitle("Edit Presenter" if presenter else "Add Presenter")
        self.setModal(True)
        self.setMinimumWidth(360)
        self._existing = presenter
        self._used_colors = used_colors or []
        self.created_presenter: Optional[Presenter] = None
        self._selected_color = self._pick_default_color()
        self._build()
        if presenter:
            self._name_edit.setText(presenter.name)
            self._set_color(presenter.color)

    def _pick_default_color(self) -> str:
        for c in Colours.PRESENTER_DEFAULTS:
            if c not in self._used_colors:
                return c
        return Colours.PRESENTER_DEFAULTS[0]

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("Presenter name")
        form.addRow("Name:", self._name_edit)
        layout.addLayout(form)

        color_row = QHBoxLayout()
        color_label = QLabel("Color:")
        self._color_preview = QLabel("  ")
        self._color_preview.setFixedSize(32, 24)
        self._set_color(self._selected_color)
        btn_pick = QPushButton("Choose…")
        btn_pick.clicked.connect(self._on_pick_color)
        color_row.addWidget(color_label)
        color_row.addWidget(self._color_preview)
        color_row.addWidget(btn_pick)
        color_row.addStretch()
        layout.addLayout(color_row)

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

    def _set_color(self, color: str) -> None:
        self._selected_color = color
        self._color_preview.setStyleSheet(
            f"background-color: {color}; border: 1px solid #444; border-radius: 3px;"
        )

    def _on_pick_color(self):
        qc = QColorDialog.getColor(QColor(self._selected_color), self, "Pick Presenter Color")
        if qc.isValid():
            self._set_color(qc.name())

    def _on_accept(self):
        name = self._name_edit.text().strip()
        if not name:
            self._error_label.setText("Name is required.")
            return
        if self._existing:
            self._existing.name = name
            self._existing.color = self._selected_color
            self.created_presenter = self._existing
        else:
            self.created_presenter = Presenter.create(name=name, color=self._selected_color)
        self.accept()
