"""
SettingsDialog — application settings persisted to config.json.
"""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout,
    QSpinBox, QLineEdit, QCheckBox, QDialogButtonBox, QLabel,
)

from orchestra.storage.config_store import load_config, save_config


class SettingsDialog(QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setModal(True)
        self.setMinimumWidth(440)
        self._config = load_config()
        self._build()

    def _build(self):
        layout = QVBoxLayout(self)
        tabs = QTabWidget()

        # --- Server tab ---
        server_tab = QWidget()
        sf = QFormLayout(server_tab)
        sf.setSpacing(8)

        self._port = QSpinBox(); self._port.setRange(1024, 65535)
        self._port.setValue(self._config.get("server_port", 5000))
        sf.addRow("Server port:", self._port)

        self._auto_ip = QCheckBox("Auto-detect local IP")
        self._auto_ip.setChecked(self._config.get("auto_detect_ip", True))
        sf.addRow("", self._auto_ip)

        self._override_ip = QLineEdit()
        self._override_ip.setPlaceholderText("e.g. 192.168.1.100")
        self._override_ip.setText(self._config.get("override_display_ip") or "")
        sf.addRow("Override display IP:", self._override_ip)

        tabs.addTab(server_tab, "Server")

        # --- PowerPoint tab ---
        ppt_tab = QWidget()
        pf = QFormLayout(ppt_tab)
        pf.setSpacing(8)

        self._advance_delay = QSpinBox(); self._advance_delay.setRange(0, 2000)
        self._advance_delay.setSuffix(" ms")
        self._advance_delay.setValue(self._config.get("powerpoint_slide_advance_delay_ms", 150))
        pf.addRow("Slide advance delay:", self._advance_delay)

        self._vib_buffer = QSpinBox(); self._vib_buffer.setRange(0, 500)
        self._vib_buffer.setSuffix(" ms")
        self._vib_buffer.setValue(self._config.get("vibration_fire_early_buffer_ms", 80))
        pf.addRow("Vibration fire buffer:", self._vib_buffer)

        tabs.addTab(ppt_tab, "PowerPoint")

        layout.addWidget(tabs)

        info = QLabel("Changes apply on next session start.")
        info.setStyleSheet("color: #8888a0; font-size: 11px;")
        layout.addWidget(info)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_save(self):
        self._config["server_port"] = self._port.value()
        self._config["auto_detect_ip"] = self._auto_ip.isChecked()
        override = self._override_ip.text().strip() or None
        self._config["override_display_ip"] = override
        self._config["powerpoint_slide_advance_delay_ms"] = self._advance_delay.value()
        self._config["vibration_fire_early_buffer_ms"] = self._vib_buffer.value()
        save_config(self._config)
        self.accept()
