"""Professional DAW Dark Theme for Chord Studio Desktop."""

DARK_THEME_QSS = """
QMainWindow {
    background-color: #0b0f19;
}

QWidget {
    background-color: #0b0f19;
    color: #f1f5f9;
    font-family: -apple-system, "Segoe UI", Roboto, "Malgun Gothic", sans-serif;
    font-size: 13px;
}

QGroupBox {
    background-color: #131b2e;
    border: 1px solid #1e293b;
    border-radius: 10px;
    margin-top: 24px;
    padding-top: 14px;
    font-weight: bold;
    color: #94a3b8;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 10px;
    color: #38bdf8;
    background-color: transparent;
}

QPushButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #1e293b, stop:1 #0f172a);
    color: #f8fafc;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 7px 14px;
    font-weight: 600;
}

QPushButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284c7, stop:1 #2563eb);
    border-color: #38bdf8;
    color: #ffffff;
}

QPushButton:pressed {
    background-color: #0369a1;
}

QPushButton#btnPrimary {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #0284c7, stop:1 #2563eb);
    border: 1px solid #38bdf8;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#btnPrimary:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #38bdf8, stop:1 #3b82f6);
}

QPushButton#btnAccent {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #059669, stop:1 #10b981);
    border: 1px solid #34d399;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#btnAccent:hover {
    background: #10b981;
}

QComboBox {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    padding: 5px 10px;
    color: #f8fafc;
    min-height: 22px;
}

QComboBox:hover {
    border-color: #38bdf8;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    border: 1px solid #475569;
    selection-background-color: #0284c7;
    selection-color: #ffffff;
    color: #f8fafc;
}

QSlider::groove:horizontal {
    height: 6px;
    background: #1e293b;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: #38bdf8;
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background: #ffffff;
    border: 2px solid #0284c7;
    width: 14px;
    margin-top: -4px;
    margin-bottom: -4px;
    border-radius: 7px;
}

QSlider::handle:horizontal:hover {
    background: #38bdf8;
}

QProgressBar {
    background-color: #1e293b;
    border: 1px solid #334155;
    border-radius: 6px;
    text-align: center;
    color: #ffffff;
    font-weight: bold;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0284c7, stop:1 #10b981);
    border-radius: 5px;
}

QLabel {
    background-color: transparent;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:horizontal, QScrollBar:vertical {
    border: none;
    background: #0f172a;
    width: 8px;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal, QScrollBar::handle:vertical {
    background: #334155;
    border-radius: 4px;
}

QScrollBar::handle:hover {
    background: #475569;
}
"""
