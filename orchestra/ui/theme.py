"""
Orchestra dark theme.

All colours and stylesheet definitions live here.
No hardcoded colours anywhere else in the codebase — reference these constants.
"""
from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

class Colours:
    # Backgrounds
    BG_DARKEST   = "#0d0d0f"
    BG_DARK      = "#141417"
    BG_PANEL     = "#1a1a1f"
    BG_SURFACE   = "#222228"
    BG_HOVER     = "#2a2a32"
    BG_SELECTED  = "#2e2e40"

    # Borders
    BORDER       = "#2d2d38"
    BORDER_FOCUS = "#5264c8"

    # Text
    TEXT_PRIMARY   = "#e8e8f0"
    TEXT_SECONDARY = "#8888a0"
    TEXT_DISABLED  = "#505060"
    TEXT_INVERSE   = "#0d0d0f"

    # Accents
    ACCENT_BLUE    = "#5264c8"
    ACCENT_GREEN   = "#3dc98e"
    ACCENT_YELLOW  = "#e8c547"
    ACCENT_RED     = "#e85454"
    ACCENT_ORANGE  = "#e88a28"

    # Session state colours
    STATE_IDLE       = "#505060"
    STATE_WARMUP     = "#e8c547"
    STATE_RUNNING    = "#3dc98e"
    STATE_PAUSED     = "#e88a28"
    STATE_COMPLETED  = "#5264c8"
    STATE_ABORTED    = "#e85454"
    STATE_ERROR      = "#e85454"

    # Default presenter colours (used when creating presenters without a chosen colour)
    PRESENTER_DEFAULTS = [
        "#E74C3C", "#3498DB", "#2ECC71", "#F39C12",
        "#9B59B6", "#1ABC9C", "#E67E22", "#E91E63",
    ]


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
QMainWindow, QDialog, QWidget {{
    background-color: {Colours.BG_DARK};
    color: {Colours.TEXT_PRIMARY};
    font-family: "Segoe UI", sans-serif;
    font-size: 13px;
}}

QSplitter::handle {{
    background-color: {Colours.BORDER};
    width: 1px;
    height: 1px;
}}

/* --- Sidebar and panels --- */
QFrame#sidebar, QFrame#presenterPanel {{
    background-color: {Colours.BG_DARKEST};
    border-right: 1px solid {Colours.BORDER};
}}

/* --- List widgets --- */
QListWidget {{
    background-color: {Colours.BG_SURFACE};
    border: 1px solid {Colours.BORDER};
    border-radius: 4px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 3px;
}}
QListWidget::item:selected {{
    background-color: {Colours.BG_SELECTED};
    color: {Colours.TEXT_PRIMARY};
}}
QListWidget::item:hover {{
    background-color: {Colours.BG_HOVER};
}}

/* --- Buttons --- */
QPushButton {{
    background-color: {Colours.BG_SURFACE};
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.BORDER};
    border-radius: 4px;
    padding: 5px 14px;
    min-height: 26px;
}}
QPushButton:hover {{
    background-color: {Colours.BG_HOVER};
    border-color: {Colours.ACCENT_BLUE};
}}
QPushButton:pressed {{
    background-color: {Colours.BG_SELECTED};
}}
QPushButton:disabled {{
    color: {Colours.TEXT_DISABLED};
    border-color: {Colours.BORDER};
}}
QPushButton#btnPrimary {{
    background-color: {Colours.ACCENT_BLUE};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btnPrimary:hover {{
    background-color: #6374d8;
}}
QPushButton#btnDanger {{
    background-color: {Colours.ACCENT_RED};
    color: #ffffff;
    border: none;
    font-weight: 600;
}}
QPushButton#btnDanger:hover {{
    background-color: #f06060;
}}
QPushButton#btnSuccess {{
    background-color: {Colours.ACCENT_GREEN};
    color: {Colours.TEXT_INVERSE};
    border: none;
    font-weight: 700;
    font-size: 14px;
    min-height: 36px;
    border-radius: 6px;
}}

/* --- Labels --- */
QLabel {{
    color: {Colours.TEXT_PRIMARY};
}}
QLabel#labelSectionHeader {{
    color: {Colours.TEXT_SECONDARY};
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-transform: uppercase;
    padding: 4px 0 2px 0;
}}

/* --- Input fields --- */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QTimeEdit, QComboBox {{
    background-color: {Colours.BG_SURFACE};
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.BORDER};
    border-radius: 4px;
    padding: 4px 8px;
    selection-background-color: {Colours.ACCENT_BLUE};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border-color: {Colours.BORDER_FOCUS};
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

/* --- Table widget --- */
QTableWidget {{
    background-color: {Colours.BG_SURFACE};
    border: 1px solid {Colours.BORDER};
    gridline-color: {Colours.BORDER};
    border-radius: 4px;
}}
QTableWidget::item:selected {{
    background-color: {Colours.BG_SELECTED};
}}
QHeaderView::section {{
    background-color: {Colours.BG_PANEL};
    color: {Colours.TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {Colours.BORDER};
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* --- Toolbar --- */
QToolBar {{
    background-color: {Colours.BG_DARKEST};
    border-bottom: 1px solid {Colours.BORDER};
    spacing: 4px;
    padding: 4px 6px;
}}
QToolBar QToolButton {{
    background-color: transparent;
    border: 1px solid transparent;
    border-radius: 4px;
    padding: 4px 10px;
    color: {Colours.TEXT_PRIMARY};
}}
QToolBar QToolButton:hover {{
    background-color: {Colours.BG_HOVER};
    border-color: {Colours.BORDER};
}}

/* --- Status bar --- */
QStatusBar {{
    background-color: {Colours.BG_DARKEST};
    color: {Colours.TEXT_SECONDARY};
    border-top: 1px solid {Colours.BORDER};
    font-size: 11px;
}}

/* --- Scroll bars --- */
QScrollBar:vertical {{
    background: {Colours.BG_DARKEST};
    width: 8px;
    border: none;
}}
QScrollBar::handle:vertical {{
    background: {Colours.BG_HOVER};
    border-radius: 4px;
    min-height: 20px;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {Colours.BG_DARKEST};
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background: {Colours.BG_HOVER};
    border-radius: 4px;
    min-width: 20px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* --- Menu --- */
QMenuBar {{
    background-color: {Colours.BG_DARKEST};
    color: {Colours.TEXT_PRIMARY};
    border-bottom: 1px solid {Colours.BORDER};
}}
QMenuBar::item:selected {{
    background-color: {Colours.BG_HOVER};
}}
QMenu {{
    background-color: {Colours.BG_PANEL};
    border: 1px solid {Colours.BORDER};
}}
QMenu::item {{
    padding: 5px 24px 5px 16px;
}}
QMenu::item:selected {{
    background-color: {Colours.BG_HOVER};
}}
QMenu::separator {{
    height: 1px;
    background-color: {Colours.BORDER};
    margin: 2px 0;
}}

/* --- Splitter --- */
QSplitter::handle:horizontal {{
    background-color: {Colours.BORDER};
    width: 1px;
}}

/* --- Progress bar --- */
QProgressBar {{
    background-color: {Colours.BG_SURFACE};
    border: 1px solid {Colours.BORDER};
    border-radius: 4px;
    text-align: center;
    color: {Colours.TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background-color: {Colours.ACCENT_BLUE};
    border-radius: 3px;
}}

/* --- Tooltip --- */
QToolTip {{
    background-color: {Colours.BG_PANEL};
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.BORDER};
    padding: 4px 8px;
    border-radius: 3px;
}}
"""


def apply_theme(app: QApplication) -> None:
    """Apply the Orchestra dark theme to the QApplication."""
    app.setStyleSheet(STYLESHEET)

    palette = QPalette()
    _c = QColor

    palette.setColor(QPalette.ColorRole.Window,          _c(Colours.BG_DARK))
    palette.setColor(QPalette.ColorRole.WindowText,      _c(Colours.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Base,            _c(Colours.BG_SURFACE))
    palette.setColor(QPalette.ColorRole.AlternateBase,   _c(Colours.BG_PANEL))
    palette.setColor(QPalette.ColorRole.Text,            _c(Colours.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Button,          _c(Colours.BG_SURFACE))
    palette.setColor(QPalette.ColorRole.ButtonText,      _c(Colours.TEXT_PRIMARY))
    palette.setColor(QPalette.ColorRole.Highlight,       _c(Colours.ACCENT_BLUE))
    palette.setColor(QPalette.ColorRole.HighlightedText, _c("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, _c(Colours.TEXT_DISABLED))

    app.setPalette(palette)
