"""5-Fret Interactive Guitar Chord Diagram Widget for Chord Studio."""

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget
from desktop_app.chord_db import get_chord_voicing, parse_symbol, ROOT_NAMES


class ChordDiagramWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(280, 110)
        self.setFixedHeight(120)
        self.setStyleSheet("background-color: #131b2e; border: 1px solid #1e293b; border-radius: 8px;")

        self.chord_symbol = ""
        self.root_name = ""
        self.quality = "major"
        self.bass = None
        self.frets = [-1, -1, -1, -1, -1, -1]  # 6th to 1st string: -1=X, 0=O, >0=fret
        self.base_fret = 1

    def set_chord(self, symbol: str, capo: int = 0):
        if not symbol:
            self.chord_symbol = ""
            self.frets = [-1, -1, -1, -1, -1, -1]
            self.update()
            return

        self.chord_symbol = symbol
        root, qual, bass = parse_symbol(symbol)
        self.root_name = root
        self.quality = qual
        self.bass = bass

        if root and root in ROOT_NAMES:
            root_pc = ROOT_NAMES.index(root)
            # Apply capo offset if desired
            eff_root = (root_pc - capo + 12) % 12
            voicing = get_chord_voicing(eff_root, qual)
            self.frets = voicing.get('frets', [-1, -1, -1, -1, -1, -1])
            self.base_fret = voicing.get('baseFret', 1)
        else:
            self.frets = [-1, -1, -1, -1, -1, -1]
            self.base_fret = 1

        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()

        if not self.chord_symbol or all(f == -1 for f in self.frets):
            painter.setPen(QColor("#64748b"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "코드 운지 정보 대기 중")
            return

        # Layout parameters (Horizontal 5-fret diagram)
        # Left: Nut / Base fret. Strings: 6th (top) to 1st (bottom) or 1st (top) to 6th (bottom)
        # Standard horizontal tab convention: Top line = 1st string (High E), Bottom line = 6th string (Low E)
        start_x = 52.0
        start_y = 26.0
        diag_w = w - start_x - 36.0
        diag_h = h - start_y - 20.0
        num_frets = 5
        fret_w = diag_w / num_frets
        string_h = diag_h / 5.0

        # Adjust base fret if chord spans higher frets
        valid_frets = [f for f in self.frets if f > 0]
        has_open = any(f == 0 for f in self.frets)
        min_f = min(valid_frets) if valid_frets else 1
        max_f = max(valid_frets) if valid_frets else 1

        base = 1
        if not has_open and min_f >= 3 and max_f > 4:
            base = min_f
        elif not has_open and min_f > 3:
            base = min_f

        # 1. Base Fret / Nut Indicator
        if base == 1:
            # Thick Nut line
            painter.setPen(QPen(QColor("#38bdf8"), 4.0, Qt.SolidLine, Qt.RoundCap))
            painter.drawLine(QPointF(start_x, start_y), QPointF(start_x, start_y + diag_h))
            # Header text
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor("#38bdf8"))
            painter.drawText(QRectF(start_x, 6, fret_w, 16), Qt.AlignCenter, "OPEN (1F)")
        else:
            # Thin fret line + Fret badge
            painter.setPen(QPen(QColor("#64748b"), 2.0))
            painter.drawLine(QPointF(start_x, start_y), QPointF(start_x, start_y + diag_h))
            painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
            painter.setPen(QColor("#f59e0b"))
            painter.drawText(QRectF(start_x - 2, 6, fret_w, 16), Qt.AlignCenter, f"{base}F")

        # 2. Fret Vertical Lines
        for f in range(1, num_frets + 1):
            fx = start_x + f * fret_w
            painter.setPen(QPen(QColor("#334155"), 1.2))
            painter.drawLine(QPointF(fx, start_y), QPointF(fx, start_y + diag_h))
            # Fret numbers at bottom
            painter.setFont(QFont("Segoe UI", 8))
            painter.setPen(QColor("#64748b"))
            painter.drawText(
                QRectF(fx - fret_w, start_y + diag_h + 3, fret_w, 14),
                Qt.AlignCenter,
                str(base + f - 1),
            )

        # 3. Horizontal String Lines (Strings 1 to 6, from top to bottom)
        string_names = ["1E", "2B", "3G", "4D", "5A", "6E"]
        for s in range(6):
            sy = start_y + s * string_h
            # Thicker lines for lower strings (string 6 is thickest)
            thickness = 1.0 + (s * 0.35)
            painter.setPen(QPen(QColor("#475569"), thickness))
            painter.drawLine(QPointF(start_x, sy), QPointF(start_x + diag_w, sy))

            # String name on far left
            painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(6, sy - 7, 20, 14), Qt.AlignRight | Qt.AlignVCenter, string_names[s])

        # 4. Finger Dots & Open/Muted indicators
        # Voicing array is [6th, 5th, 4th, 3rd, 2nd, 1st]
        # Our drawing order s=0 is 1st string, s=5 is 6th string
        for s in range(6):
            fret_val = self.frets[5 - s]  # map 6th..1st to top..bottom
            sy = start_y + s * string_h

            if fret_val == -1:
                # Muted 'X'
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#ef4444"))
                painter.drawText(QRectF(start_x - 18, sy - 8, 14, 16), Qt.AlignCenter, "×")
            elif fret_val == 0:
                # Open 'O'
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.setPen(QColor("#34d399"))
                painter.drawText(QRectF(start_x - 18, sy - 8, 14, 16), Qt.AlignCenter, "○")
            elif fret_val >= base and fret_val < base + num_frets:
                # Finger Dot on fret
                rel_fret = fret_val - base
                dot_x = start_x + (rel_fret * fret_w) + (fret_w / 2.0)

                # Outer glow
                painter.setBrush(QBrush(QColor(56, 189, 248, 80)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(dot_x, sy), 8.5, 8.5)

                # Dot
                painter.setBrush(QBrush(QColor("#38bdf8")))
                painter.setPen(QPen(QColor("#ffffff"), 1.2))
                painter.drawEllipse(QPointF(dot_x, sy), 6.5, 6.5)
