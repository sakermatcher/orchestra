"""
MainWindow — the top-level application window.

Structure:
  menuBar() ← File, Edit, Session, Help
  statusBar() ← server status, IP:port, presenter count
  centralWidget() ← QSplitter
    [L] SidebarPanel     (220px fixed)
    [C] WorkspaceStack   (QStackedWidget — editor mode or session mode)
    [R] PresenterPanel   (260px fixed)

The WorkspaceStack switches between EditorPanel (index 0) and SessionPanel (index 1)
based on engine state via QtBridge signals.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont
from PyQt6.QtWidgets import (
    QMainWindow, QSplitter, QStackedWidget, QStatusBar,
    QLabel, QWidget, QVBoxLayout, QMessageBox,
    QSystemTrayIcon, QMenu,
)

from orchestra.bridge.qt_bridge import QtBridge
from orchestra.constants import SIDEBAR_WIDTH, PRESENTER_PANEL_WIDTH


class MainWindow(QMainWindow):

    def __init__(self, bridge: QtBridge, engine=None, parent=None):
        super().__init__(parent)
        self._bridge = bridge
        self._engine = engine
        self._force_quit = False

        self.setWindowTitle("Orchestra")
        self.setMinimumSize(1100, 700)
        self.resize(1400, 860)

        self._build_menu()
        self._build_status_bar()
        self._build_central()
        self._connect_bridge()
        self._setup_tray()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def _build_menu(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")
        file_menu.addAction("&New Timeline", "Ctrl+N", self._on_new_timeline)
        file_menu.addAction("&Import PPTX…", self._on_import_pptx)
        file_menu.addSeparator()
        file_menu.addAction("&Settings…", "Ctrl+,", self._on_open_settings)
        file_menu.addSeparator()
        file_menu.addAction("&Quit", "Ctrl+Q", self._on_quit)

        edit_menu = mb.addMenu("&Edit")
        edit_menu.addAction("Add &Block", "Ctrl+B", self._on_add_block)
        edit_menu.addAction("Add &Presenter", "Ctrl+P", self._on_add_presenter)
        edit_menu.addSeparator()
        self._undo_action = edit_menu.addAction("&Undo", "Ctrl+Z", self._on_undo)
        self._redo_action = edit_menu.addAction("&Redo", "Ctrl+Y", self._on_redo)

        session_menu = mb.addMenu("&Session")
        self._start_action = session_menu.addAction("&Start Session", "F5", self._on_start_session)
        self._pause_action = session_menu.addAction("&Pause / Resume", "F6", self._on_pause_resume)
        self._skip_action  = session_menu.addAction("S&kip Block", "F7", self._on_skip_block)
        self._abort_action = session_menu.addAction("&Abort Session", self._on_abort_session)
        self._pause_action.setEnabled(False)
        self._skip_action.setEnabled(False)
        self._abort_action.setEnabled(False)

        help_menu = mb.addMenu("&Help")
        help_menu.addAction("&About Orchestra", self._on_about)

    def _build_status_bar(self) -> None:
        sb = self.statusBar()
        self._status_server = QLabel("Server: stopped")
        self._status_ip     = QLabel("")
        self._status_conn   = QLabel("0 connected")
        sb.addPermanentWidget(self._status_server)
        sb.addPermanentWidget(QLabel("|"))
        sb.addPermanentWidget(self._status_ip)
        sb.addPermanentWidget(QLabel("|"))
        sb.addPermanentWidget(self._status_conn)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # --- Left: Sidebar ---
        from orchestra.ui.panels.sidebar_panel import SidebarPanel
        self._sidebar = SidebarPanel(self._bridge, self._engine, parent=self)
        self._sidebar.setFixedWidth(SIDEBAR_WIDTH)
        self._sidebar.timeline_selected.connect(self._on_timeline_selected)
        splitter.addWidget(self._sidebar)

        # --- Center: Workspace stack ---
        self._workspace = QStackedWidget()

        from orchestra.ui.panels.editor_panel import EditorPanel
        self._editor_panel = EditorPanel(self._bridge, self._engine, parent=self)
        self._workspace.addWidget(self._editor_panel)  # index 0

        from orchestra.ui.panels.session_panel import SessionPanel
        self._session_panel = SessionPanel(self._bridge, self._engine, parent=self)
        self._workspace.addWidget(self._session_panel)  # index 1

        splitter.addWidget(self._workspace)

        # --- Right: Presenter panel ---
        from orchestra.ui.panels.presenter_panel import PresenterPanel
        self._presenter_panel = PresenterPanel(self._bridge, self._engine, parent=self)
        self._presenter_panel.setFixedWidth(PRESENTER_PANEL_WIDTH)
        splitter.addWidget(self._presenter_panel)

        # Prevent sidebar and presenter panel from being resized
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        self.setCentralWidget(splitter)

    def _connect_bridge(self) -> None:
        self._bridge.session_state_changed.connect(self._on_session_state_changed)
        self._bridge.presenter_connected.connect(self._on_presenter_connected)
        self._bridge.presenter_disconnected.connect(self._on_presenter_disconnected)
        self._bridge.connected_list_updated.connect(self._on_connected_list_updated)
        self._bridge.server_error.connect(self._on_server_error)
        self._bridge.powerpoint_error.connect(self._on_powerpoint_error)

    def _setup_tray(self) -> None:
        """Create a system tray icon with show/quit context menu."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = None
            return

        # Generate a simple icon with "O" text
        pixmap = QPixmap(32, 32)
        pixmap.fill(QColor("#5264c8"))
        painter = QPainter(pixmap)
        painter.setPen(QColor("#ffffff"))
        font = QFont()
        font.setBold(True)
        font.setPixelSize(20)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "O")
        painter.end()
        icon = QIcon(pixmap)

        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("Orchestra")

        tray_menu = QMenu()
        tray_menu.addAction("Show Window", self._on_tray_show)
        tray_menu.addSeparator()
        tray_menu.addAction("Quit", self._on_quit)

        self._tray.setContextMenu(tray_menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    # ------------------------------------------------------------------
    # Public API (called by OrchestraApp)
    # ------------------------------------------------------------------

    def set_server_running(self, host: str, port: int) -> None:
        self._status_server.setText("Server: running")
        self._status_ip.setText(f"{host}:{port}")

    def set_server_error(self, message: str) -> None:
        self._status_server.setText(f"Server error: {message}")

    # ------------------------------------------------------------------
    # Bridge slots
    # ------------------------------------------------------------------

    @pyqtSlot(str)
    def _on_session_state_changed(self, state: str) -> None:
        is_active = state in ("warmup", "running", "paused")
        self._workspace.setCurrentIndex(1 if is_active else 0)
        self._start_action.setEnabled(state in ("idle", "timeline_loaded"))
        self._pause_action.setEnabled(state in ("running", "paused"))
        self._skip_action.setEnabled(state == "running")
        self._abort_action.setEnabled(is_active)
        self._sidebar.set_session_active(is_active)

        # After a session ends, return engine to TIMELINE_LOADED so a new
        # session can be started without reloading the timeline.
        if state in ("aborted", "completed") and self._engine:
            self._engine.session_reset()
            return  # session_reset() fires another state_changed("timeline_loaded")

        if state == "warmup" and self._engine:
            snap = self._engine.get_session_snapshot()
            presenters = snap.get("presenters", [])
            blocks_summary = snap.get("blocks_summary", [])
            total_dur = sum(b["duration"] for b in blocks_summary) if blocks_summary else 0.0
            self._session_panel.setup_for_session(presenters, blocks_summary, total_dur)

    @pyqtSlot(str, str)
    def _on_presenter_connected(self, presenter_id: str, name: str) -> None:
        pass  # presenter_panel handles its own updates

    @pyqtSlot(str, str)
    def _on_presenter_disconnected(self, presenter_id: str, name: str) -> None:
        pass

    @pyqtSlot(list)
    def _on_connected_list_updated(self, ids: list) -> None:
        self._status_conn.setText(f"{len(ids)} connected")

    @pyqtSlot(str)
    def _on_server_error(self, message: str) -> None:
        QMessageBox.critical(self, "Server Error", message)

    @pyqtSlot(str)
    def _on_powerpoint_error(self, message: str) -> None:
        QMessageBox.critical(self, "PowerPoint Error", message)

    # ------------------------------------------------------------------
    # Menu action handlers
    # ------------------------------------------------------------------

    @pyqtSlot()
    def _on_timeline_selected(self) -> None:
        self._workspace.setCurrentIndex(0)
        self._start_action.setEnabled(True)

    def _on_new_timeline(self) -> None:
        from orchestra.ui.dialogs.new_timeline_dialog import NewTimelineDialog
        dlg = NewTimelineDialog(parent=self)
        if dlg.exec():
            timeline = dlg.created_timeline
            if timeline and self._editor_panel:
                self._editor_panel.load_timeline(timeline)
                self._sidebar.refresh()

    def _on_import_pptx(self) -> None:
        from orchestra.ui.dialogs.import_pptx_dialog import ImportPptxDialog
        timeline = self._editor_panel.current_timeline if self._editor_panel else None
        if timeline is None:
            QMessageBox.information(self, "Import PPTX",
                                    "Create or select a timeline first.")
            return
        dlg = ImportPptxDialog(timeline=timeline, parent=self)
        if dlg.exec():
            self._editor_panel.load_timeline(timeline)
            self._sidebar.refresh()

    def _on_open_settings(self) -> None:
        from orchestra.ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(parent=self)
        dlg.exec()

    def _on_add_block(self) -> None:
        if self._editor_panel:
            self._editor_panel.request_add_block()

    def _on_add_presenter(self) -> None:
        if self._editor_panel:
            self._editor_panel.request_add_presenter()

    def _on_undo(self) -> None:
        if self._editor_panel:
            self._editor_panel.undo()

    def _on_redo(self) -> None:
        if self._editor_panel:
            self._editor_panel.redo()

    def _on_start_session(self) -> None:
        if self._engine:
            self._engine.request_start_session()

    def _on_pause_resume(self) -> None:
        if self._engine:
            self._engine.toggle_pause()

    def _on_skip_block(self) -> None:
        if self._engine:
            self._engine.skip_current_block()

    def _on_abort_session(self) -> None:
        from orchestra.ui.dialogs.confirm_dialog import ConfirmDialog
        dlg = ConfirmDialog(
            "Abort Session",
            "Are you sure you want to abort the current session?\n\n"
            "All connected presenters will be disconnected.",
            parent=self,
        )
        if dlg.exec() and self._engine:
            self._engine.abort_session()

    def _on_about(self) -> None:
        from orchestra import APP_VERSION
        QMessageBox.about(
            self, "About Orchestra",
            f"<b>Orchestra</b> v{APP_VERSION}<br><br>"
            "Professional presentation coordination system.<br><br>"
            "Real-time multi-presenter control with timeline-driven "
            "haptic alerts and PowerPoint integration.",
        )

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        if self._engine and self._engine.is_session_active():
            from orchestra.ui.dialogs.confirm_dialog import ConfirmDialog
            dlg = ConfirmDialog(
                "Quit Orchestra",
                "A presentation session is currently active.\n"
                "Quitting will abort the session and disconnect all presenters.",
                parent=self,
            )
            if not dlg.exec():
                event.ignore()
                return
            self._engine.abort_session()

        # Minimize to tray unless explicitly quitting
        if not self._force_quit and self._tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage(
                "Orchestra",
                "Orchestra is minimized to the system tray.",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
            return

        event.accept()

    def _on_quit(self) -> None:
        self._force_quit = True
        self.close()

    def _on_tray_show(self) -> None:
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._on_tray_show()
