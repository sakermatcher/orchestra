"""
SidebarPanel — left panel with timeline list and action buttons.

Phase 1: Shows timeline list. Emits timeline_selected when user clicks a timeline.
Phase 2: Full drag, context menu, multi-select behavior.
"""
from __future__ import annotations
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel,
)

from orchestra.storage.timeline_store import list_timelines


class SidebarPanel(QWidget):

    timeline_selected = pyqtSignal()

    def __init__(self, bridge, engine, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._engine = engine
        self._current_timeline = None
        self._build()
        self.refresh()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        header = QLabel("TIMELINES")
        header.setObjectName("labelSectionHeader")
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.itemClicked.connect(self._on_click)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        self._btn_new = QPushButton("+")
        self._btn_new.setToolTip("New Timeline")
        self._btn_new.setFixedWidth(32)
        self._btn_new.clicked.connect(self._on_new)

        self._btn_delete = QPushButton("✕")
        self._btn_delete.setToolTip("Delete Timeline")
        self._btn_delete.setFixedWidth(32)
        self._btn_delete.clicked.connect(self._on_delete)

        btn_row.addWidget(self._btn_new)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_delete)
        layout.addLayout(btn_row)

        import_header = QLabel("IMPORT")
        import_header.setObjectName("labelSectionHeader")
        layout.addWidget(import_header)

        self._btn_import = QPushButton("Import PPTX…")
        self._btn_import.clicked.connect(self._on_import)
        layout.addWidget(self._btn_import)

        layout.addStretch()

    def refresh(self):
        self._list.clear()
        for timeline in list_timelines():
            item = QListWidgetItem(f"{timeline.name}\n{len(timeline.blocks)} blocks")
            item.setData(256, timeline.id)  # Qt.ItemDataRole.UserRole = 256
            self._list.addItem(item)

    def get_selected_timeline_id(self) -> str | None:
        item = self._list.currentItem()
        if item:
            return item.data(256)
        return None

    def _on_click(self, item: QListWidgetItem):
        from orchestra.storage.timeline_store import load_timeline
        tid = item.data(256)
        try:
            main = self.window()
            if hasattr(main, '_editor_panel'):
                timeline = load_timeline(tid)
                main._editor_panel.load_timeline(timeline)
                self.timeline_selected.emit()
        except Exception as e:
            print(f"[SidebarPanel] Error loading timeline: {e}")

    def _on_double_click(self, item: QListWidgetItem):
        self._on_click(item)

    def _on_new(self):
        from orchestra.ui.dialogs.new_timeline_dialog import NewTimelineDialog
        dlg = NewTimelineDialog(parent=self)
        if dlg.exec():
            timeline = dlg.created_timeline
            if timeline:
                from orchestra.storage.timeline_store import save_timeline
                save_timeline(timeline)
                self.refresh()
                main = self.window()
                if hasattr(main, '_editor_panel'):
                    main._editor_panel.load_timeline(timeline)
                    self.timeline_selected.emit()

    def _on_delete(self):
        tid = self.get_selected_timeline_id()
        if not tid:
            return
        from orchestra.ui.dialogs.confirm_dialog import ConfirmDialog
        from orchestra.storage.timeline_store import delete_timeline
        dlg = ConfirmDialog("Delete Timeline",
                            "Delete this timeline? This cannot be undone.",
                            parent=self)
        if dlg.exec():
            delete_timeline(tid)
            self.refresh()

    def _on_import(self):
        main = self.window()
        if hasattr(main, '_on_import_pptx'):
            main._on_import_pptx()
