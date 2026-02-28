"""
EditorPanel — center workspace for timeline editing.

Contains:
  - Toolbar (add/remove blocks and presenters, start session)
  - TimelineCanvas (custom-painted, drag-and-drop)
  - BlockEditorPanel (bottom, collapsible, bound to selected block)

Phase 2: Full timeline canvas with drag/resize. This file provides the panel
         framework and toolbar wiring.
"""
from __future__ import annotations
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QSplitter, QToolBar, QLabel,
    QSizePolicy, QMessageBox,
)

from orchestra.bridge.qt_bridge import QtBridge
from orchestra.models.timeline import Timeline
from orchestra.storage.timeline_store import save_timeline
from orchestra.ui.theme import Colours


class EditorPanel(QWidget):

    def __init__(self, bridge: QtBridge, engine, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._engine = engine
        self._timeline: Optional[Timeline] = None
        self._undo_stack: list[dict] = []
        self._redo_stack: list[dict] = []
        self._build()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = self._build_toolbar()
        layout.addWidget(toolbar)

        # Canvas + block editor splitter (vertical)
        self._splitter = QSplitter(Qt.Orientation.Vertical)

        from orchestra.ui.widgets.timeline_canvas import TimelineCanvas
        self._canvas = TimelineCanvas(parent=self)
        self._canvas.block_selected.connect(self._on_block_selected)
        self._canvas.timeline_mutated.connect(self._on_timeline_mutated)
        self._splitter.addWidget(self._canvas)

        from orchestra.ui.panels.block_editor_panel import BlockEditorPanel
        self._block_editor = BlockEditorPanel(parent=self)
        self._block_editor.block_changed.connect(self._on_block_edited)
        self._block_editor.setMaximumHeight(280)
        self._splitter.addWidget(self._block_editor)

        self._splitter.setStretchFactor(0, 1)
        self._splitter.setStretchFactor(1, 0)
        layout.addWidget(self._splitter)

        self._show_empty_state()

    def _build_toolbar(self) -> QToolBar:
        tb = QToolBar()
        tb.setMovable(False)

        self._act_add_block = tb.addAction("+ Block", self.request_add_block)
        self._act_del_block = tb.addAction("✕ Block", self._on_delete_block)
        tb.addSeparator()
        self._act_add_presenter = tb.addAction("+ Presenter", self.request_add_presenter)
        self._act_del_presenter = tb.addAction("✕ Presenter", self._on_delete_presenter)
        tb.addSeparator()

        self._act_start = tb.addAction("▶  Start Session", self._on_start_session)
        # Make start action stand out
        start_widget = tb.widgetForAction(self._act_start)
        if start_widget:
            start_widget.setStyleSheet(
                f"background:{Colours.ACCENT_GREEN}; color:#000; font-weight:700;"
                f"border-radius:4px; padding:4px 12px;"
            )

        self._set_toolbar_enabled(False)
        return tb

    def _show_empty_state(self):
        # Canvas shows its own empty state message; block editor hidden
        self._block_editor.setVisible(False)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def current_timeline(self) -> Optional[Timeline]:
        return self._timeline

    def load_timeline(self, timeline: Timeline) -> None:
        self._timeline = timeline
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._canvas.set_timeline(timeline)
        self._set_toolbar_enabled(True)
        # Tell the engine about the newly loaded timeline
        if self._engine:
            self._engine.load_timeline(timeline)
        # Update presenter panel
        main = self.window()
        if hasattr(main, '_presenter_panel'):
            main._presenter_panel.load_timeline_presenters(timeline)

    def request_add_block(self) -> None:
        if not self._timeline:
            QMessageBox.information(self, "No Timeline", "Open or create a timeline first.")
            return
        from orchestra.ui.dialogs.add_block_dialog import AddBlockDialog
        dlg = AddBlockDialog(timeline=self._timeline, parent=self)
        if dlg.exec():
            block = dlg.created_block
            self._push_undo()
            self._timeline.add_block(block)
            save_timeline(self._timeline)
            self._canvas.set_timeline(self._timeline)
            self._sync_engine()

    def request_add_presenter(self) -> None:
        if not self._timeline:
            return
        from orchestra.ui.dialogs.presenter_dialog import PresenterDialog
        used_colors = [p.color for p in self._timeline.presenters]
        dlg = PresenterDialog(used_colors=used_colors, parent=self)
        if dlg.exec():
            presenter = dlg.created_presenter
            self._push_undo()
            self._timeline.add_presenter(presenter)
            save_timeline(self._timeline)
            self._canvas.set_timeline(self._timeline)
            if self._engine:
                self._engine.load_timeline(self._timeline)
            main = self.window()
            if hasattr(main, '_presenter_panel'):
                main._presenter_panel.load_timeline_presenters(self._timeline)

    def undo(self) -> None:
        if not self._undo_stack:
            return
        self._redo_stack.append(self._timeline.to_dict())
        state = self._undo_stack.pop()
        self._timeline = Timeline.from_dict(state)
        save_timeline(self._timeline)
        self._canvas.set_timeline(self._timeline)
        self._sync_engine()

    def redo(self) -> None:
        if not self._redo_stack:
            return
        self._undo_stack.append(self._timeline.to_dict())
        state = self._redo_stack.pop()
        self._timeline = Timeline.from_dict(state)
        save_timeline(self._timeline)
        self._canvas.set_timeline(self._timeline)
        self._sync_engine()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _push_undo(self) -> None:
        if self._timeline:
            self._undo_stack.append(self._timeline.to_dict())
            self._redo_stack.clear()
            # Cap undo history
            if len(self._undo_stack) > 50:
                self._undo_stack.pop(0)

    def _sync_engine(self) -> None:
        """Keep engine aware of the current timeline (only when no session is active)."""
        if self._engine and self._timeline and not self._engine.is_session_active():
            self._engine.load_timeline(self._timeline)

    def _set_toolbar_enabled(self, enabled: bool) -> None:
        self._act_add_block.setEnabled(enabled)
        self._act_del_block.setEnabled(enabled)
        self._act_add_presenter.setEnabled(enabled)
        self._act_del_presenter.setEnabled(enabled)
        self._act_start.setEnabled(enabled)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def _on_block_selected(self, block_id: str) -> None:
        if not self._timeline:
            return
        block = self._timeline.get_block(block_id)
        if block:
            self._block_editor.load_block(block, self._timeline)
            self._block_editor.setVisible(True)

    @pyqtSlot()
    def _on_timeline_mutated(self) -> None:
        if self._timeline:
            self._push_undo()
            save_timeline(self._timeline)

    @pyqtSlot(str)
    def _on_block_edited(self, block_id: str) -> None:
        if self._timeline:
            save_timeline(self._timeline)
            self._canvas.update()

    def _on_delete_block(self) -> None:
        if not self._canvas.selected_block_id or not self._timeline:
            return
        self._push_undo()
        self._timeline.remove_block(self._canvas.selected_block_id)
        save_timeline(self._timeline)
        self._canvas.set_timeline(self._timeline)
        self._block_editor.setVisible(False)
        self._sync_engine()

    def _on_delete_presenter(self) -> None:
        if not self._timeline or not self._timeline.presenters:
            return
        from PyQt6.QtWidgets import QInputDialog
        names = [p.name for p in self._timeline.presenters]
        name, ok = QInputDialog.getItem(self, "Remove Presenter",
                                        "Select presenter to remove:", names, 0, False)
        if ok and name:
            presenter = next((p for p in self._timeline.presenters if p.name == name), None)
            if presenter:
                self._push_undo()
                self._timeline.remove_presenter(presenter.id)
                save_timeline(self._timeline)
                self._canvas.set_timeline(self._timeline)
                self._sync_engine()

    def _on_start_session(self) -> None:
        if not self._timeline:
            return
        errors = self._timeline.validate()
        if errors:
            QMessageBox.warning(self, "Timeline Validation",
                                "Cannot start session:\n\n" + "\n".join(f"• {e}" for e in errors))
            return
        if self._engine:
            self._engine.request_start_session()
        else:
            QMessageBox.information(self, "Engine Not Ready",
                                    "Timeline engine is not initialized yet.")
