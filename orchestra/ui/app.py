"""
OrchestraApp — QApplication subclass.

Wires together:
  - QtBridge (cross-thread event bus)
  - TimelineEngine (full implementation)
  - Flask/SocketIO server thread
  - MainWindow

Startup sequence:
  1. Create QApplication (this class)
  2. Create QtBridge
  3. Create TimelineEngine (no socketio yet)
  4. Create Flask app + SocketIO (inject engine + bridge)
  5. Start ServerThread
  6. Inject socketio reference into engine
  7. Create and show MainWindow
"""
from __future__ import annotations
import sys
import socket as _socket
from PyQt6.QtWidgets import QApplication, QMessageBox

from orchestra.bridge.qt_bridge import QtBridge
from orchestra.engine.timeline_engine import TimelineEngine
from orchestra.storage.config_store import load_config
from orchestra.constants import APP_NAME


class OrchestraApp(QApplication):

    def __init__(self, argv: list[str], com_worker=None):
        super().__init__(argv)
        self.setApplicationName(APP_NAME)
        self.setApplicationVersion("1.0.0")

        # Apply dark theme
        from orchestra.ui.theme import apply_theme
        apply_theme(self)

        self._config = load_config()
        self._bridge = QtBridge()

        # Create engine with bridge and COM worker
        self._engine = TimelineEngine(bridge=self._bridge, com_worker=com_worker)

        # Start Flask/SocketIO server (engine + bridge injected so Flask handlers can use them)
        self._server_thread = self._start_server()

        # Inject socketio into engine now that server is running
        if self._server_thread and self._server_thread.start_error is None:
            from orchestra.server.flask_app import get_socketio
            self._engine.set_socketio(get_socketio())

        # Create main window
        from orchestra.ui.main_window import MainWindow
        self._window = MainWindow(bridge=self._bridge, engine=self._engine)

        if self._server_thread and self._server_thread.start_error is None:
            display_ip = self._get_display_ip()
            port = self._config["server_port"]
            self._window.set_server_running(display_ip, port)

            # Generate QR code for the join URL
            self._setup_qr(display_ip, port)
        elif self._server_thread and self._server_thread.start_error:
            self._window.set_server_error(str(self._server_thread.start_error))
            QMessageBox.critical(
                None, "Server Error",
                f"Failed to start the local server on port {self._config['server_port']}.\n\n"
                f"Error: {self._server_thread.start_error}\n\n"
                "Try changing the port in Settings > Server.",
            )

        self._window.show()

    # ------------------------------------------------------------------

    def _start_server(self):
        from orchestra.server.flask_app import create_app
        from orchestra.server.server_thread import ServerThread

        try:
            app, sio = create_app(engine_ref=self._engine, bridge_ref=self._bridge)
            host = self._config.get("server_host", "0.0.0.0")
            port = int(self._config.get("server_port", 5000))
            thread = ServerThread(app, sio, host, port)
            thread.start()
            thread.wait_until_ready(timeout=5.0)
            return thread
        except Exception as e:
            print(f"[OrchestraApp] Failed to start server: {e}")
            return None

    def _get_display_ip(self) -> str:
        cfg = self._config
        if not cfg.get("auto_detect_ip") and cfg.get("override_display_ip"):
            return cfg["override_display_ip"]
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def _setup_qr(self, ip: str, port: int) -> None:
        """Generate QR code and inject into presenter panel."""
        try:
            import qrcode
            from qrcode.image.pil import PilImage
            from PIL import Image
            from PyQt6.QtGui import QPixmap, QImage
            import io

            url = f"http://{ip}:{port}/join"
            qr = qrcode.QRCode(version=1, box_size=6, border=2)
            qr.add_data(url)
            qr.make(fit=True)
            img: Image.Image = qr.make_image(fill_color="black", back_color="white").get_image()

            # Convert PIL image to QPixmap
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            buffer.seek(0)
            qimage = QImage.fromData(buffer.read())
            pixmap = QPixmap.fromImage(qimage)

            if hasattr(self._window, '_presenter_panel'):
                self._window._presenter_panel.set_qr(pixmap, url)
        except Exception as e:
            print(f"[OrchestraApp] QR generation failed: {e}")

    def run(self) -> int:
        return self.exec()
