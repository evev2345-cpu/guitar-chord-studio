"""Interactive Video & 4-Point Fretboard Overlay Widget for Chord Studio."""

import math
from PySide6.QtCore import Qt, QPointF, QRectF, Signal
from PySide6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QCursor, QImage
)
from PySide6.QtWidgets import QWidget
from PySide6.QtMultimedia import QVideoSink, QVideoFrame


class FretboardVideoWidget(QWidget):
    calibration_changed = Signal(list)  # emits 4 corners [[x,y],...] normalized (0..1)
    seek_requested = Signal(float)       # emits seek fraction or seconds

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumSize(480, 270)
        self.setStyleSheet("background-color: #050811; border-radius: 8px;")

        self.video_sink = QVideoSink(self)
        self.video_sink.videoFrameChanged.connect(self._on_frame_changed)

        self._current_image = None
        self._video_size = (1920, 1080)
        self.corners_norm = []  # 4 points in normalized coordinates [0..1]
        self.calibration_mode = False
        self.total_frets = 20
        self.perspective_k = 0.0
        self.current_chord = ""
        self.current_bpm = 0.0

        self._dragging_idx = -1
        self._hover_idx = -1

    def _on_frame_changed(self, frame: QVideoFrame):
        if not frame.isValid():
            return
        image = frame.toImage()
        if not image.isNull():
            self._current_image = image
            self._video_size = (image.width(), image.height())
            self.update()

    def set_calibration(self, corners_norm, perspective_k=0.0, total_frets=20):
        self.corners_norm = [list(c) for c in corners_norm]
        self.perspective_k = perspective_k
        self.total_frets = total_frets
        self.update()

    def set_current_chord(self, chord_sym: str):
        if self.current_chord != chord_sym:
            self.current_chord = chord_sym
            self.update()

    def toggle_calibration_mode(self, enabled: bool):
        self.calibration_mode = enabled
        if enabled and len(self.corners_norm) < 4:
            # Set default sensible fretboard box
            self.corners_norm = [
                [0.45, 0.35],  # 1: nut top (6th string)
                [0.22, 0.43],  # 2: body top
                [0.23, 0.49],  # 3: body bottom
                [0.46, 0.41],  # 4: nut bottom (1st string)
            ]
        self.update()

    def _get_video_rect(self):
        """Returns the scaled rect where video image is rendered inside the widget."""
        w, h = self.width(), self.height()
        vw, vh = self._video_size
        if vw <= 0 or vh <= 0:
            return QRectF(0, 0, w, h)
        scale = min(w / vw, h / vh)
        dw, dh = vw * scale, vh * scale
        dx, dy = (w - dw) / 2.0, (h - dh) / 2.0
        return QRectF(dx, dy, dw, dh)

    def _norm_to_screen(self, nx, ny, vrect):
        return QPointF(vrect.x() + nx * vrect.width(), vrect.y() + ny * vrect.height())

    def _screen_to_norm(self, sx, sy, vrect):
        if vrect.width() <= 0 or vrect.height() <= 0:
            return 0.0, 0.0
        nx = max(0.0, min(1.0, (sx - vrect.x()) / vrect.width()))
        ny = max(0.0, min(1.0, (sy - vrect.y()) / vrect.height()))
        return nx, ny

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        vrect = self._get_video_rect()

        # 1. Draw video frame or placeholder
        if self._current_image and not self._current_image.isNull():
            painter.drawImage(vrect, self._current_image)
        else:
            painter.fillRect(self.rect(), QColor("#090d16"))
            painter.setPen(QColor("#475569"))
            painter.setFont(QFont("Segoe UI", 14, QFont.Bold))
            painter.drawText(
                self.rect(),
                Qt.AlignCenter,
                "🎸 영상을 열어주세요 (Ctrl+O 또는 파일 열기 버튼)",
            )

        # 2. Draw Fretboard perspective grid if corners available
        if len(self.corners_norm) == 4:
            pts = [self._norm_to_screen(c[0], c[1], vrect) for c in self.corners_norm]

            # Draw outer polygon
            poly = QPolygonF([pts[0], pts[1], pts[2], pts[3]])
            fill_color = QColor(56, 189, 248, 25 if not self.calibration_mode else 45)
            painter.setBrush(QBrush(fill_color))
            border_pen = QPen(
                QColor("#38bdf8" if not self.calibration_mode else "#f59e0b"),
                2.0 if not self.calibration_mode else 2.5,
            )
            painter.setPen(border_pen)
            painter.drawPolygon(poly)

            # Draw frets (12-TET spacing with perspective k)
            denom = 1.0 - (2.0 ** (-self.total_frets / 12.0))
            k = max(-0.8, min(0.8, self.perspective_k))

            for n in range(1, self.total_frets + 1):
                un = (1.0 - (2.0 ** (-n / 12.0))) / denom
                ratio = (1.0 + k) * un / (1.0 + k * un) if un < 1.0 else 1.0

                top = QPointF(
                    (1.0 - ratio) * pts[0].x() + ratio * pts[1].x(),
                    (1.0 - ratio) * pts[0].y() + ratio * pts[1].y(),
                )
                bot = QPointF(
                    (1.0 - ratio) * pts[3].x() + ratio * pts[2].x(),
                    (1.0 - ratio) * pts[3].y() + ratio * pts[2].y(),
                )

                # 12th fret highlighted
                if n == 12:
                    pen = QPen(QColor("#38ef7d"), 2.5)
                elif n <= 12:
                    pen = QPen(QColor(255, 207, 102, 180), 1.6)
                else:
                    pen = QPen(QColor(255, 207, 102, 100), 1.2)

                painter.setPen(pen)
                painter.drawLine(top, bot)

                # Inlay dots on frets 3, 5, 7, 9, 12, 15, 17, 19
                if n in (3, 5, 7, 9, 15, 17, 19):
                    mid = QPointF((top.x() + bot.x()) / 2.0, (top.y() + bot.y()) / 2.0)
                    painter.setBrush(QBrush(QColor(255, 255, 255, 160)))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(mid, 2.5, 2.5)
                elif n == 12:
                    # Double dot
                    d1 = QPointF(top.x() * 0.65 + bot.x() * 0.35, top.y() * 0.65 + bot.y() * 0.35)
                    d2 = QPointF(top.x() * 0.35 + bot.x() * 0.65, top.y() * 0.35 + bot.y() * 0.65)
                    painter.setBrush(QBrush(QColor("#38ef7d")))
                    painter.setPen(Qt.NoPen)
                    painter.drawEllipse(d1, 2.5, 2.5)
                    painter.drawEllipse(d2, 2.5, 2.5)

            # 3. Draw Corner Draggable Pins (Numbered 1, 2, 3, 4)
            pin_labels = ["1", "2", "3", "4"]
            pin_sub = ["6번줄 너트", "6번줄 끝", "1번줄 끝", "1번줄 너트"]

            for i, pt in enumerate(pts):
                is_hover = (i == self._hover_idx) or (i == self._dragging_idx)
                radius = 11.0 if is_hover else 9.0

                # Outer halo
                halo_color = QColor("#f59e0b" if self.calibration_mode else "#38bdf8")
                halo_color.setAlpha(60 if not is_hover else 120)
                painter.setBrush(QBrush(halo_color))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(pt, radius + 4, radius + 4)

                # Pin circle
                pin_bg = QColor("#f59e0b" if self.calibration_mode else "#0284c7")
                if is_hover:
                    pin_bg = pin_bg.lighter(130)
                painter.setBrush(QBrush(pin_bg))
                painter.setPen(QPen(QColor("#ffffff"), 1.8))
                painter.drawEllipse(pt, radius, radius)

                # Pin number
                painter.setPen(QColor("#ffffff"))
                painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
                painter.drawText(
                    QRectF(pt.x() - radius, pt.y() - radius, radius * 2, radius * 2),
                    Qt.AlignCenter,
                    pin_labels[i],
                )

                # In calibration mode, show helpful subtitle
                if self.calibration_mode:
                    painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                    painter.setPen(QColor("#fef08a"))
                    painter.drawText(
                        QPointF(pt.x() + 14, pt.y() + 4),
                        f"P{i+1}: {pin_sub[i]}",
                    )

        # 4. Live Chord Badge Overlay (Top Left)
        if self.current_chord:
            badge_rect = QRectF(16, 16, 92, 48)
            painter.setBrush(QBrush(QColor(15, 23, 42, 220)))
            painter.setPen(QPen(QColor("#38bdf8"), 1.8))
            painter.drawRoundedRect(badge_rect, 10, 10)

            painter.setPen(QColor("#38bdf8"))
            painter.setFont(QFont("Segoe UI", 18, QFont.Bold))
            painter.drawText(badge_rect, Qt.AlignCenter, self.current_chord)

        # 5. Calibration Mode Top Notification Banner
        if self.calibration_mode:
            banner_rect = QRectF((self.width() - 360) / 2.0, 14, 360, 32)
            painter.setBrush(QBrush(QColor(245, 158, 11, 230)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(banner_rect, 6, 6)

            painter.setPen(QColor("#000000"))
            painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
            painter.drawText(
                banner_rect,
                Qt.AlignCenter,
                "📌 지판 4개 핀(1~4번)을 마우스로 드래그하여 맞추세요",
            )

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            vrect = self._get_video_rect()
            pts = [self._norm_to_screen(c[0], c[1], vrect) for c in self.corners_norm]

            # Check if clicked on an existing pin
            for i, pt in enumerate(pts):
                dist = math.hypot(event.position().x() - pt.x(), event.position().y() - pt.y())
                if dist <= 18:
                    self._dragging_idx = i
                    self.setCursor(QCursor(Qt.ClosedHandCursor))
                    self.update()
                    return

            # If in calibration mode and less than 4 points
            if self.calibration_mode and len(self.corners_norm) < 4:
                nx, ny = self._screen_to_norm(
                    event.position().x(), event.position().y(), vrect
                )
                self.corners_norm.append([nx, ny])
                self.calibration_changed.emit(self.corners_norm)
                self.update()

    def mouseMoveEvent(self, event):
        vrect = self._get_video_rect()
        if self._dragging_idx >= 0 and self._dragging_idx < len(self.corners_norm):
            nx, ny = self._screen_to_norm(
                event.position().x(), event.position().y(), vrect
            )
            self.corners_norm[self._dragging_idx] = [round(nx, 4), round(ny, 4)]
            self.calibration_changed.emit(self.corners_norm)
            self.update()
            return

        # Check hover
        hover = -1
        pts = [self._norm_to_screen(c[0], c[1], vrect) for c in self.corners_norm]
        for i, pt in enumerate(pts):
            dist = math.hypot(event.position().x() - pt.x(), event.position().y() - pt.y())
            if dist <= 18:
                hover = i
                break

        if hover != self._hover_idx:
            self._hover_idx = hover
            self.setCursor(QCursor(Qt.PointingHandCursor if hover >= 0 else Qt.ArrowCursor))
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._dragging_idx >= 0:
            self._dragging_idx = -1
            self.setCursor(QCursor(Qt.PointingHandCursor if self._hover_idx >= 0 else Qt.ArrowCursor))
            self.calibration_changed.emit(self.corners_norm)
            self.update()
