"""
ImportPptxDialog — file picker to attach a PPTX to a timeline and detect slide count.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QDialogButtonBox, QSpinBox,
)

from orchestra.models.timeline import Timeline
from orchestra.storage.timeline_store import save_timeline
from orchestra.storage.config_store import load_config, save_config


class ImportPptxDialog(QDialog):

    def __init__(self, timeline: Timeline, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import / Set PowerPoint File")
        self.setModal(True)
        self.setMinimumWidth(500)
        self._timeline = timeline
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        layout.addWidget(QLabel("Select the PowerPoint file for this timeline:"))

        path_row = QHBoxLayout()
        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("C:\\path\\to\\presentation.pptx")
        if self._timeline.presentation_file_path:
            self._path_edit.setText(self._timeline.presentation_file_path)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._on_browse)
        path_row.addWidget(self._path_edit)
        path_row.addWidget(btn_browse)
        layout.addLayout(path_row)

        slide_row = QHBoxLayout()
        slide_row.addWidget(QLabel("Total slides (auto-detected):"))
        self._slide_count = QSpinBox()
        self._slide_count.setRange(1, 9999)
        self._slide_count.setValue(self._detect_slide_count() or 1)
        slide_row.addWidget(self._slide_count)
        slide_row.addStretch()
        layout.addLayout(slide_row)

        self._info_label = QLabel("")
        self._info_label.setStyleSheet("color: #8888a0; font-size: 11px;")
        layout.addWidget(self._info_label)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_browse(self):
        from PyQt6.QtWidgets import QFileDialog
        cfg = load_config()
        start_dir = cfg.get("last_pptx_directory", str(Path.home()))
        path, _ = QFileDialog.getOpenFileName(
            self, "Select PowerPoint File", start_dir,
            "PowerPoint Files (*.pptx *.ppt);;All Files (*)"
        )
        if path:
            self._path_edit.setText(path)
            cfg["last_pptx_directory"] = str(Path(path).parent)
            save_config(cfg)
            count = self._detect_slide_count(path)
            if count:
                self._slide_count.setValue(count)
                self._info_label.setText(f"Detected {count} slides.")

    def _detect_slide_count(self, path: str = None) -> int:
        p = path or self._path_edit.text()
        if not p or not Path(p).exists():
            return 0
        try:
            from pptx import Presentation
            prs = Presentation(p)
            return len(prs.slides)
        except Exception:
            return 0

    def _on_accept(self):
        path = self._path_edit.text().strip()
        if path and not Path(path).exists():
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "File Not Found",
                                f"The file does not exist:\n{path}")
            return
        self._timeline.presentation_file_path = path
        self._timeline.touch()
        save_timeline(self._timeline)
        self.accept()
