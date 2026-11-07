"""Inspector Panel: Current Chord, 5-Fret Diagram & Candidate Editor."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QGroupBox, QFrame
)
from desktop_app.widgets.chord_diagram import ChordDiagramWidget
from desktop_app.chord_db import ROOT_NAMES, QUALITIES, parse_symbol


class InspectorWidget(QWidget):
    chord_override_requested = Signal(str)  # emits new symbol like 'B' or 'G#m7/D#'

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet("background-color: #0e1424; border-left: 1px solid #1e293b;")

        self._active_symbol = ""
        self._current_candidates = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # 1. Active Chord Display Card
        chord_card = QFrame()
        chord_card.setStyleSheet("background-color: #131b2e; border: 1px solid #1e293b; border-radius: 10px; padding: 12px;")
        card_layout = QVBoxLayout(chord_card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(4)

        title_lbl = QLabel("현재 분석 코드")
        title_lbl.setStyleSheet("color: #94a3b8; font-size: 11px; font-weight: bold;")
        card_layout.addWidget(title_lbl)

        self.lbl_chord = QLabel("-")
        self.lbl_chord.setFont(QFont("Segoe UI", 32, QFont.Bold))
        self.lbl_chord.setStyleSheet("color: #38bdf8; background: transparent;")
        self.lbl_chord.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_chord)

        self.lbl_sub = QLabel("원곡 화성 분석 대기 중")
        self.lbl_sub.setStyleSheet("color: #64748b; font-size: 11px;")
        self.lbl_sub.setAlignment(Qt.AlignCenter)
        card_layout.addWidget(self.lbl_sub)

        layout.addWidget(chord_card)

        # 2. 5-Fret Guitar Diagram
        diag_group = QGroupBox("5프렛 기타 운지 다이어그램")
        diag_layout = QVBoxLayout(diag_group)
        diag_layout.setContentsMargins(4, 12, 4, 4)
        self.diagram = ChordDiagramWidget()
        diag_layout.addWidget(self.diagram)
        layout.addWidget(diag_group)

        # 3. Top Candidates (Quick Swap)
        self.cand_group = QGroupBox("함께 확인된 후보 (클릭 시 즉시 적용)")
        self.cand_layout = QVBoxLayout(self.cand_group)
        self.cand_layout.setContentsMargins(8, 14, 8, 8)
        self.cand_layout.setSpacing(6)

        self.btn_cands = []
        for i in range(3):
            btn = QPushButton(f"후보 {i+1}")
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1e293b;
                    color: #e2e8f0;
                    border: 1px solid #334155;
                    border-radius: 6px;
                    padding: 6px 10px;
                    text-align: left;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #0284c7;
                    border-color: #38bdf8;
                    color: #ffffff;
                }
            """)
            btn.clicked.connect(lambda checked, idx=i: self._on_cand_clicked(idx))
            self.btn_cands.append(btn)
            self.cand_layout.addWidget(btn)

        layout.addWidget(self.cand_group)

        # 4. Manual Chord Editor
        edit_group = QGroupBox("구간 코드 직접 수정")
        edit_layout = QVBoxLayout(edit_group)
        edit_layout.setContentsMargins(8, 14, 8, 8)
        edit_layout.setSpacing(8)

        row1 = QHBoxLayout()
        self.cmb_root = QComboBox()
        self.cmb_root.addItems(ROOT_NAMES)

        self.cmb_qual = QComboBox()
        self.cmb_qual.addItems(["major", "minor", "7", "m7", "maj7", "sus4", "dim", "aug", "6", "9"])

        row1.addWidget(self.cmb_root)
        row1.addWidget(self.cmb_qual)
        edit_layout.addLayout(row1)

        row2 = QHBoxLayout()
        self.cmb_bass = QComboBox()
        self.cmb_bass.addItem("베이스 없음")
        for r in ROOT_NAMES:
            self.cmb_bass.addItem(f"/{r}")
        row2.addWidget(QLabel("베이스:"))
        row2.addWidget(self.cmb_bass)
        edit_layout.addLayout(row2)

        self.btn_apply = QPushButton("이 코드로 변경")
        self.btn_apply.setObjectName("btnPrimary")
        self.btn_apply.clicked.connect(self._on_apply_custom_chord)
        edit_layout.addWidget(self.btn_apply)

        layout.addWidget(edit_group)
        layout.addStretch()

    def update_active_chord(self, symbol: str, candidates: list = None, sub_text: str = ""):
        if symbol != self._active_symbol:
            self._active_symbol = symbol
            self.lbl_chord.setText(symbol or "-")
            self.diagram.set_chord(symbol)

        if sub_text:
            self.lbl_sub.setText(sub_text)

        self._current_candidates = list(candidates or [])
        for i, btn in enumerate(self.btn_cands):
            if i < len(self._current_candidates):
                c = self._current_candidates[i]
                c_sym = c.get('symbol', '')
                score = c.get('score', 0.0)
                btn.setText(f"{c_sym}  ({int(score * 100)}%)")
                btn.setVisible(True)
            else:
                btn.setVisible(False)

        # Sync dropdowns
        if symbol:
            root, qual, bass = parse_symbol(symbol)
            if root in ROOT_NAMES:
                self.cmb_root.setCurrentText(root)
            if qual in ["major", "minor", "7", "m7", "maj7", "sus4", "dim", "aug", "6", "9"]:
                self.cmb_qual.setCurrentText(qual)
            if bass and f"/{bass}" in [self.cmb_bass.itemText(i) for i in range(self.cmb_bass.count())]:
                self.cmb_bass.setCurrentText(f"/{bass}")
            else:
                self.cmb_bass.setCurrentIndex(0)

    def _on_cand_clicked(self, idx: int):
        if idx < len(self._current_candidates):
            sym = self._current_candidates[idx].get('symbol', '')
            if sym:
                self.chord_override_requested.emit(sym)

    def _on_apply_custom_chord(self):
        root = self.cmb_root.currentText()
        qual = self.cmb_qual.currentText()
        bass = self.cmb_bass.currentText()

        symbol = root if qual == "major" else f"{root}{qual}"
        if bass != "베이스 없음" and bass.startswith("/"):
            symbol = f"{symbol}{bass}"

        self.chord_override_requested.emit(symbol)
