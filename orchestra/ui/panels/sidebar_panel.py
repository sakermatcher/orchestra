"""
SidebarPanel — left panel with timeline list and action buttons.

Phase 1: Shows timeline list. Emits timeline_selected when user clicks a timeline.
Phase 2: Full drag, context menu, multi-select behavior.
"""
from __future__ import annotations
from pathlib import Path

from PyQt6.QtCore import pyqtSignal, Qt, QSize
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QListWidget, QListWidgetItem, QLabel, QInputDialog,
)

from orchestra.storage.timeline_store import list_timelines
from orchestra.ui.theme import Colours

_ICONS_DIR = Path(__file__).parent.parent / "icons"

# Shared style for the small icon-only action buttons in the sidebar.
# Uses ACCENT_BLUE so black icons are legible against a coloured background.
_BTN_STYLE = (
    f"QPushButton {{ background:{Colours.ACCENT_BLUE}; border:none;"
    f"border-radius:4px; color:#fff; }}"
    f"QPushButton:hover {{ background:#6374d8; }}"
    f"QPushButton:pressed {{ background:#3d54b0; }}"
)


def _icon(name: str) -> QIcon:
    p = _ICONS_DIR / name
    return QIcon(str(p)) if p.exists() else QIcon()


def _get_pptx_thumbnail(path: str) -> "QPixmap | None":
    """Extract the embedded first-slide thumbnail from a .pptx (ZIP) file."""
    if not path:
        return None
    import zipfile
    from PyQt6.QtCore import QByteArray
    try:
        with zipfile.ZipFile(path, "r") as z:
            names = z.namelist()
            for candidate in (
                "docProps/thumbnail.jpeg",
                "docProps/thumbnail.jpg",
                "docProps/thumbnail.png",
            ):
                if candidate in names:
                    data = z.read(candidate)
                    pm = QPixmap()
                    pm.loadFromData(QByteArray(data))
                    if not pm.isNull():
                        return pm
    except Exception:
        pass
    return None


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
        self._list.setIconSize(QSize(80, 45))
        self._list.itemDoubleClicked.connect(self._on_double_click)
        self._list.itemClicked.connect(self._on_click)
        layout.addWidget(self._list)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(4)

        self._btn_new = QPushButton()
        self._btn_new.setIcon(_icon("new.png"))
        self._btn_new.setIconSize(QSize(16, 16))
        self._btn_new.setToolTip("New Timeline")
        self._btn_new.setFixedSize(32, 32)
        self._btn_new.setStyleSheet(_BTN_STYLE)
        self._btn_new.clicked.connect(self._on_new)

        self._btn_rename = QPushButton()
        self._btn_rename.setIcon(_icon("rename.png"))
        self._btn_rename.setIconSize(QSize(16, 16))
        self._btn_rename.setToolTip("Rename Timeline")
        self._btn_rename.setFixedSize(32, 32)
        self._btn_rename.setStyleSheet(_BTN_STYLE)
        self._btn_rename.clicked.connect(self._on_rename)

        self._btn_delete = QPushButton()
        self._btn_delete.setIcon(_icon("delete.png"))
        self._btn_delete.setIconSize(QSize(16, 16))
        self._btn_delete.setToolTip("Delete Timeline")
        self._btn_delete.setFixedSize(32, 32)
        self._btn_delete.setStyleSheet(_BTN_STYLE)
        self._btn_delete.clicked.connect(self._on_delete)

        btn_row.addWidget(self._btn_new)
        btn_row.addWidget(self._btn_rename)
        btn_row.addStretch()
        btn_row.addWidget(self._btn_delete)
        layout.addLayout(btn_row)

        import_header = QLabel("IMPORT")
        import_header.setObjectName("labelSectionHeader")
        layout.addWidget(import_header)

        self._btn_import = QPushButton("  Import PPTX…")
        self._btn_import.setIcon(_icon("import.png"))
        self._btn_import.setIconSize(QSize(16, 16))
        self._btn_import.clicked.connect(self._on_import)
        layout.addWidget(self._btn_import)

        layout.addStretch()

    def refresh(self):
        self._list.clear()
        for timeline in list_timelines():
            item = QListWidgetItem(f"{timeline.name}\n{len(timeline.blocks)} blocks")
            item.setData(256, timeline.id)  # Qt.ItemDataRole.UserRole = 256
            pm = _get_pptx_thumbnail(
                getattr(timeline, "presentation_file_path", "") or ""
            )
            if pm:
                item.setIcon(QIcon(pm.scaled(
                    80, 45,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )))
            self._list.addItem(item)

    def set_session_active(self, active: bool) -> None:
        """Disable timeline switching while a session is running."""
        self._list.setEnabled(not active)
        self._btn_new.setEnabled(not active)
        self._btn_rename.setEnabled(not active)
        self._btn_delete.setEnabled(not active)
        self._btn_import.setEnabled(not active)

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

    def _on_rename(self):
        tid = self.get_selected_timeline_id()
        if not tid:
            return
        from orchestra.storage.timeline_store import load_timeline, save_timeline
        timeline = load_timeline(tid)
        if not timeline:
            return
        name, ok = QInputDialog.getText(
            self, "Rename Timeline", "New name:", text=timeline.name
        )
        if ok and name.strip():
            timeline.name = name.strip()
            timeline.touch()
            save_timeline(timeline)
            self.refresh()
            # Keep the editor in sync if this timeline is currently open
            main = self.window()
            if hasattr(main, '_editor_panel'):
                ep = main._editor_panel
                if ep.current_timeline and ep.current_timeline.id == tid:
                    ep.load_timeline(timeline)

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
