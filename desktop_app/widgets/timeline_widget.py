"""Interactive 16th-Beat Quantized Chord Timeline Widget for Chord Studio."""

from PySide6.QtCore import Qt, QRectF, QPointF, Signal
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont
from PySide6.QtWidgets import QWidget


class TimelineWidget(QWidget):
    seek_requested = Signal(float)  # seconds
    segment_selected = Signal(dict)  # segment dict

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 72)
        self.setFixedHeight(80)
        self.setStyleSheet("background-color: #0c1222; border-top: 1px solid #1e293b;")

        self.duration_s = 0.0
        self.current_time_s = 0.0
        self.bpm = 120.0
        self.start_offset = 0.0
        self.segments = []  # list of {start, end, symbol, top3, user_edited, ...}
        self.selected_idx = -1

        self._dragging = False

    def set_data(self, duration_s: float, bpm: float, start_offset: float, segments: list):
        self.duration_s = max(1.0, duration_s)
        self.bpm = max(40.0, min(300.0, bpm)) if bpm > 0 else 120.0
        self.start_offset = start_offset
        self.segments = list(segments)
        self.update()

    def set_current_time(self, current_s: float):
        self.current_time_s = max(0.0, min(self.duration_s, current_s))
        self.update()

    def _time_to_x(self, t: float):
        if self.duration_s <= 0:
            return 0.0
        pad_x = 10.0
        usable_w = self.width() - (pad_x * 2.0)
        return pad_x + (t / self.duration_s) * usable_w

    def _x_to_time(self, x: float):
        pad_x = 10.0
        usable_w = self.width() - (pad_x * 2.0)
        if usable_w <= 0:
            return 0.0
        ratio = max(0.0, min(1.0, (x - pad_x) / usable_w))
        return ratio * self.duration_s

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        w, h = self.width(), self.height()
        pad_x = 10.0
        top_y = 6.0
        timeline_h = h - 16.0

        if self.duration_s <= 0 or not self.segments:
            painter.fillRect(self.rect(), QColor("#0c1222"))
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 11))
            painter.drawText(self.rect(), Qt.AlignCenter, "타임라인 데이터 로딩 대기 중...")
            return

        # 1. Background
        painter.fillRect(QRectF(pad_x, top_y, w - pad_x * 2, timeline_h), QColor("#131b2e"))

        # 2. Draw Chord Segments
        curr_t = self.current_time_s
        for idx, seg in enumerate(self.segments):
            start = seg.get('start', 0.0)
            end = seg.get('end', start + 0.5)
            x1 = self._time_to_x(start)
            x2 = self._time_to_x(end)
            seg_w = max(2.0, x2 - x1)

            is_active = (start <= curr_t <= end)
            is_selected = (idx == self.selected_idx)
            is_edited = seg.get('user_edited', False)

            # Segment box fill
            if is_selected:
                fill = QColor(56, 189, 248, 120)
            elif is_active:
                fill = QColor(2, 132, 199, 90)
            elif is_edited:
                fill = QColor(168, 85, 247, 60)
            else:
                fill = QColor(30, 41, 59, 140 if idx % 2 == 0 else 100)

            rect = QRectF(x1, top_y + 16, seg_w, timeline_h - 16)
            painter.fillRect(rect, fill)

            # Segment border
            painter.setPen(QPen(QColor("#334155"), 0.8))
            painter.drawRect(rect)

            # Chord Symbol Text
            sym = seg.get('symbol', '')
            if sym and seg_w > 18:
                painter.setPen(QColor("#ffffff" if is_active else "#94a3b8"))
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold if is_active else QFont.Normal))
                painter.drawText(rect, Qt.AlignCenter, sym)

        # 3. Draw Measure Rulers & Numbers on Top
        spb = 60.0 / self.bpm  # seconds per beat
        spm = spb * 4.0        # seconds per measure (4/4)
        total_measures = int(self.duration_s / spm) + 1

        for m in range(total_measures):
            m_time = self.start_offset + (m * spm)
            if 0 <= m_time <= self.duration_s:
                mx = self._time_to_x(m_time)
                painter.setPen(QPen(QColor("#475569"), 1.2))
                painter.drawLine(QPointF(mx, top_y), QPointF(mx, top_y + timeline_h))

                # Measure label
                painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
                painter.setPen(QColor("#64748b"))
                painter.drawText(QPointF(mx + 3, top_y + 11), f"m.{m+1}")

        # 4. Red Playhead Needle
        px = self._time_to_x(self.current_time_s)
        # Needle glow
        painter.setPen(QPen(QColor(239, 68, 68, 80), 4.0))
        painter.drawLine(QPointF(px, top_y), QPointF(px, top_y + timeline_h))
        # Needle sharp line
        painter.setPen(QPen(QColor("#ef4444"), 2.0))
        painter.drawLine(QPointF(px, top_y), QPointF(px, top_y + timeline_h))

        # Needle head handle
        painter.setBrush(QBrush(QColor("#ef4444")))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon([
            QPointF(px - 5, top_y),
            QPointF(px + 5, top_y),
            QPointF(px, top_y + 6),
        ])

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = True
            t = self._x_to_time(event.position().x())
            self.set_current_time(t)
            self.seek_requested.emit(t)

            # Check if clicked on a segment
            for idx, seg in enumerate(self.segments):
                if seg.get('start', 0.0) <= t <= seg.get('end', 0.0):
                    self.selected_idx = idx
                    self.segment_selected.emit(seg)
                    break

    def mouseMoveEvent(self, event):
        if self._dragging:
            t = self._x_to_time(event.position().x())
            self.set_current_time(t)
            self.seek_requested.emit(t)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._dragging = False
