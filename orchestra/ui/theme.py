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
    border-top: 1px solid #3a3a48;
    border-radius: 6px;
    outline: none;
}}
QListWidget::item {{
    padding: 8px 10px;
    border-radius: 4px;
}}
QListWidget::item:selected {{
    background-color: {Colours.BG_SELECTED};
    color: {Colours.TEXT_PRIMARY};
    border-left: 2px solid {Colours.ACCENT_BLUE};
}}
QListWidget::item:hover {{
    background-color: {Colours.BG_HOVER};
}}

/* --- Buttons --- */
QPushButton {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2e2e3a, stop:1 {Colours.BG_SURFACE});
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid #3e3e50;
    border-radius: 5px;
    padding: 5px 14px;
    min-height: 26px;
}}
QPushButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #383852, stop:1 {Colours.BG_HOVER});
    border-color: {Colours.ACCENT_BLUE};
    border-top: 1px solid #6878e0;
}}
QPushButton:pressed {{
    background: {Colours.BG_SELECTED};
    border-color: {Colours.ACCENT_BLUE};
}}
QPushButton:disabled {{
    color: {Colours.TEXT_DISABLED};
    border-color: {Colours.BORDER};
    background: {Colours.BG_SURFACE};
}}
QPushButton#btnPrimary {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #6374d8, stop:1 {Colours.ACCENT_BLUE});
    color: #ffffff;
    border: 1px solid #4050b0;
    border-top: 1px solid #7888e8;
    font-weight: 600;
}}
QPushButton#btnPrimary:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7282e0, stop:1 #6374d8);
    border-top: 1px solid #9090f0;
}}
QPushButton#btnDanger {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f06060, stop:1 {Colours.ACCENT_RED});
    color: #ffffff;
    border: 1px solid #c03030;
    border-top: 1px solid #f88080;
    font-weight: 600;
}}
QPushButton#btnDanger:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #f87070, stop:1 #f06060);
}}
QPushButton#btnSuccess {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #50dfa0, stop:1 {Colours.ACCENT_GREEN});
    color: {Colours.TEXT_INVERSE};
    border: 1px solid #28a070;
    border-top: 1px solid #70f0b8;
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
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a22, stop:1 {Colours.BG_SURFACE});
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid #1a1a28;
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {Colours.ACCENT_BLUE};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QComboBox:focus {{
    border: 1px solid {Colours.BORDER_FOCUS};
    border-top: 1px solid #7888e8;
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1e1e2e, stop:1 #262632);
}}
QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

/* --- Table widget --- */
QTableWidget {{
    background-color: {Colours.BG_SURFACE};
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid #3a3a48;
    gridline-color: {Colours.BORDER};
    border-radius: 6px;
}}
QTableWidget::item:selected {{
    background-color: {Colours.BG_SELECTED};
    border-left: 2px solid {Colours.ACCENT_BLUE};
}}
QHeaderView::section {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #252530, stop:1 {Colours.BG_PANEL});
    color: {Colours.TEXT_SECONDARY};
    border: none;
    border-bottom: 1px solid {Colours.BORDER};
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* --- Toolbar --- */
QToolBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #18181e, stop:1 {Colours.BG_DARKEST});
    border-bottom: 1px solid {Colours.BORDER};
    border-top: 1px solid #252530;
    spacing: 4px;
    padding: 4px 6px;
}}
QToolBar QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: 5px;
    padding: 4px 10px;
    color: {Colours.TEXT_PRIMARY};
}}
QToolBar QToolButton:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #32324a, stop:1 {Colours.BG_HOVER});
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid #3e3e58;
}}
QToolBar QToolButton:pressed {{
    background: {Colours.BG_SELECTED};
}}

/* --- Status bar --- */
QStatusBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {Colours.BG_DARKEST}, stop:1 #0a0a0c);
    color: {Colours.TEXT_SECONDARY};
    border-top: 1px solid {Colours.BORDER};
    font-size: 11px;
}}

/* --- Scroll bars --- */
QScrollBar:vertical {{
    background: {Colours.BG_DARKEST};
    width: 10px;
    border: none;
    border-left: 1px solid {Colours.BORDER};
}}
QScrollBar::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3a3a50, stop:1 #46467a);
    border-radius: 4px;
    min-height: 24px;
    margin: 1px 1px;
}}
QScrollBar::handle:vertical:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #5060b0, stop:1 {Colours.ACCENT_BLUE});
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{
    background: {Colours.BG_DARKEST};
    height: 10px;
    border: none;
    border-top: 1px solid {Colours.BORDER};
}}
QScrollBar::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #46467a, stop:1 #3a3a50);
    border-radius: 4px;
    min-width: 24px;
    margin: 1px 1px;
}}
QScrollBar::handle:horizontal:hover {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {Colours.ACCENT_BLUE}, stop:1 #5060b0);
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* --- Menu --- */
QMenuBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #18181e, stop:1 {Colours.BG_DARKEST});
    color: {Colours.TEXT_PRIMARY};
    border-bottom: 1px solid {Colours.BORDER};
}}
QMenuBar::item:selected {{
    background-color: {Colours.BG_HOVER};
    border-radius: 4px;
}}
QMenu {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #222230, stop:1 {Colours.BG_PANEL});
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid #3a3a50;
    border-radius: 6px;
}}
QMenu::item {{
    padding: 5px 24px 5px 16px;
    border-radius: 3px;
}}
QMenu::item:selected {{
    background-color: {Colours.BG_HOVER};
    color: #ffffff;
}}
QMenu::separator {{
    height: 1px;
    background-color: {Colours.BORDER};
    margin: 2px 0;
}}

/* --- Splitter --- */
QSplitter::handle:horizontal {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {Colours.BORDER}, stop:0.5 #3e3e58, stop:1 {Colours.BORDER});
    width: 3px;
}}
QSplitter::handle:vertical {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 {Colours.BORDER}, stop:0.5 #3e3e58, stop:1 {Colours.BORDER});
    height: 3px;
}}

/* --- Progress bar --- */
QProgressBar {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #1a1a22, stop:1 {Colours.BG_SURFACE});
    border: 1px solid {Colours.BORDER};
    border-radius: 5px;
    text-align: center;
    color: {Colours.TEXT_PRIMARY};
}}
QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #7888e8, stop:1 {Colours.ACCENT_BLUE});
    border-radius: 4px;
}}

/* --- Tooltip --- */
QToolTip {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #2a2a3c, stop:1 {Colours.BG_PANEL});
    color: {Colours.TEXT_PRIMARY};
    border: 1px solid {Colours.ACCENT_BLUE};
    border-top: 1px solid #7888e8;
    padding: 4px 8px;
    border-radius: 4px;
}}

/* --- Group box (dialogs) --- */
QGroupBox {{
    background: transparent;
    border: 1px solid {Colours.BORDER};
    border-top: 2px solid {Colours.ACCENT_BLUE};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 6px;
    font-weight: 600;
    color: {Colours.TEXT_SECONDARY};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {Colours.ACCENT_BLUE};
}}

/* --- Tab widget --- */
QTabWidget::pane {{
    border: 1px solid {Colours.BORDER};
    border-top: 1px solid {Colours.ACCENT_BLUE};
    border-radius: 0 0 6px 6px;
    background: {Colours.BG_PANEL};
}}
QTabBar::tab {{
    background: {Colours.BG_SURFACE};
    color: {Colours.TEXT_SECONDARY};
    border: 1px solid {Colours.BORDER};
    border-bottom: none;
    padding: 5px 14px;
    border-radius: 4px 4px 0 0;
}}
QTabBar::tab:selected {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 #3a3a58, stop:1 {Colours.BG_PANEL});
    color: #ffffff;
    border-top: 2px solid {Colours.ACCENT_BLUE};
}}
QTabBar::tab:hover:!selected {{
    background: {Colours.BG_HOVER};
    color: {Colours.TEXT_PRIMARY};
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
