"""Main Window for Chord Studio Pro Native Desktop Application."""

import sys
from pathlib import Path
from PySide6.QtCore import Qt, QUrl, QTime
from PySide6.QtGui import QAction, QKeySequence, QFont
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFileDialog, QProgressBar, QCheckBox, QComboBox, QMessageBox, QSplitter
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from desktop_app.theme import DARK_THEME_QSS
from desktop_app.widgets.fretboard_video import FretboardVideoWidget
from desktop_app.widgets.inspector_widget import InspectorWidget
from desktop_app.widgets.timeline_widget import TimelineWidget
from desktop_app.workers.analysis_worker import AnalysisWorker


def format_time(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m:02d}:{s:02d}"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🎸 Chord Studio Pro - 데스크톱 에디션")
        self.resize(1200, 800)
        self.setMinimumSize(960, 640)
        self.setStyleSheet(DARK_THEME_QSS)

        # Media Player & Audio
        self.player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.player.setAudioOutput(self.audio_output)

        # State
        self.current_media_path = None
        self.analysis_data = None
        self.job_data = None
        self.timeline_rows = []  # from branches['0.2']
        self.worker = None

        self._init_ui()
        self._init_shortcuts()
        self._connect_signals()

    def _init_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(12, 10, 12, 10)
        main_layout.setSpacing(10)

        # 1. Top Header Bar
        header = QHBoxLayout()
        header.setSpacing(10)

        self.btn_open = QPushButton("📁 파일 열기 (Ctrl+O)")
        self.btn_open.setObjectName("btnPrimary")
        self.btn_open.clicked.connect(self._on_open_file)
        header.addWidget(self.btn_open)

        self.chk_separate = QCheckBox("기타 트랙 분리 (Demucs AI)")
        self.chk_separate.setStyleSheet("color: #94a3b8; font-weight: bold;")
        self.chk_separate.setChecked(True)
        header.addWidget(self.chk_separate)

        self.btn_calibrate = QPushButton("🎯 지판 4점 지정")
        self.btn_calibrate.setCheckable(True)
        self.btn_calibrate.clicked.connect(self._on_toggle_calibrate)
        header.addWidget(self.btn_calibrate)

        header.addSpacing(15)

        self.lbl_bpm = QLabel("BPM: --")
        self.lbl_bpm.setStyleSheet("color: #38bdf8; font-weight: bold;")
        header.addWidget(self.lbl_bpm)

        header.addWidget(QLabel("카포:"))
        self.cmb_capo = QComboBox()
        self.cmb_capo.addItems([f"카포 {i}" for i in range(8)])
        self.cmb_capo.currentIndexChanged.connect(self._on_capo_changed)
        header.addWidget(self.cmb_capo)

        header.addStretch()

        # Status text & Progress
        self.lbl_status = QLabel("준비됨")
        self.lbl_status.setStyleSheet("color: #64748b; font-size: 12px;")
        header.addWidget(self.lbl_status)

        self.prog_bar = QProgressBar()
        self.prog_bar.setFixedSize(160, 18)
        self.prog_bar.setVisible(False)
        header.addWidget(self.prog_bar)

        main_layout.addLayout(header)

        # 2. Main Central Splitter (Left: Video, Right: Inspector)
        splitter = QSplitter(Qt.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1e293b; width: 2px; }")

        # Left Container (Video)
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(6)

        self.video_widget = FretboardVideoWidget(self)
        self.player.setVideoSink(self.video_widget.video_sink)
        left_layout.addWidget(self.video_widget, stretch=1)

        splitter.addWidget(left_widget)

        # Right Container (Inspector)
        self.inspector = InspectorWidget(self)
        splitter.addWidget(self.inspector)

        # Proportions: 75% video, 25% inspector
        splitter.setStretchFactor(0, 4)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter, stretch=1)

        # 3. Bottom Transport Controls
        transport = QHBoxLayout()
        transport.setSpacing(10)

        self.btn_play = QPushButton("▶ 재생 (Space)")
        self.btn_play.setObjectName("btnAccent")
        self.btn_play.setFixedWidth(130)
        self.btn_play.clicked.connect(self._toggle_playback)
        transport.addWidget(self.btn_play)

        self.lbl_time = QLabel("00:00 / 00:00")
        self.lbl_time.setStyleSheet("color: #e2e8f0; font-family: monospace; font-size: 13px; font-weight: bold;")
        transport.addWidget(self.lbl_time)

        transport.addSpacing(15)

        transport.addWidget(QLabel("배속:"))
        self.cmb_speed = QComboBox()
        self.cmb_speed.addItems(["0.5x", "0.75x", "1.0x", "1.25x"])
        self.cmb_speed.setCurrentText("1.0x")
        self.cmb_speed.currentTextChanged.connect(self._on_speed_changed)
        transport.addWidget(self.cmb_speed)

        transport.addStretch()

        main_layout.addLayout(transport)

        # 4. 16th-Beat Quantized Timeline
        self.timeline = TimelineWidget(self)
        main_layout.addWidget(self.timeline)

    def _init_shortcuts(self):
        # Open file
        act_open = QAction(self)
        act_open.setShortcut(QKeySequence.Open)
        act_open.triggered.connect(self._on_open_file)
        self.addAction(act_open)

        # Space: Play / Pause
        act_play = QAction(self)
        act_play.setShortcut(QKeySequence(Qt.Key_Space))
        act_play.triggered.connect(self._toggle_playback)
        self.addAction(act_play)

        # Left / Right: Seek 2 seconds
        act_seek_back = QAction(self)
        act_seek_back.setShortcut(QKeySequence(Qt.Key_Left))
        act_seek_back.triggered.connect(lambda: self._seek_relative(-2000))
        self.addAction(act_seek_back)

        act_seek_fwd = QAction(self)
        act_seek_fwd.setShortcut(QKeySequence(Qt.Key_Right))
        act_seek_fwd.triggered.connect(lambda: self._seek_relative(2000))
        self.addAction(act_seek_fwd)

    def _connect_signals(self):
        # Media player signals
        self.player.positionChanged.connect(self._on_player_position_changed)
        self.player.durationChanged.connect(self._on_player_duration_changed)
        self.player.playbackStateChanged.connect(self._on_playback_state_changed)

        # Timeline signals
        self.timeline.seek_requested.connect(self._on_timeline_seek)
        self.timeline.segment_selected.connect(self._on_segment_selected)

        # Inspector signals
        self.inspector.chord_override_requested.connect(self._on_chord_override)

    def _on_open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "오디오 또는 비디오 파일 선택",
            "",
            "미디어 파일 (*.mp4 *.mkv *.mov *.avi *.webm *.wav *.mp3 *.flac);;모든 파일 (*.*)",
        )
        if not file_path:
            return

        self.current_media_path = Path(file_path)
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(file_path))

        # Start AI analysis
        self._start_analysis(file_path)

    def _start_analysis(self, file_path: str):
        self.prog_bar.setVisible(True)
        self.prog_bar.setValue(0)
        self.lbl_status.setText("AI 분석 시작 중...")
        self.btn_open.setEnabled(False)

        self.worker = AnalysisWorker(
            media_path=file_path,
            separate_guitar=self.chk_separate.isChecked(),
        )
        self.worker.progress_updated.connect(self._on_analysis_progress)
        self.worker.analysis_finished.connect(self._on_analysis_finished)
        self.worker.analysis_failed.connect(self._on_analysis_failed)
        self.worker.start()

    def _on_analysis_progress(self, percent: int, text: str):
        self.prog_bar.setValue(percent)
        self.lbl_status.setText(text)

    def _on_analysis_finished(self, r_data: dict, j_data: dict):
        self.prog_bar.setVisible(False)
        self.btn_open.setEnabled(True)
        self.lbl_status.setText("분석 완료")

        self.analysis_data = r_data
        self.job_data = j_data

        bpm = float(j_data.get('bpm', 120.0))
        self.lbl_bpm.setText(f"BPM: {bpm:.1f}")

        # Extract timeline segments from branches
        branches = r_data.get('branches', {})
        self.timeline_rows = branches.get('0.2', [])

        segments = self._build_timeline_segments()
        duration_s = float(r_data.get('duration_s', self.player.duration() / 1000.0))
        start_offset = float(j_data.get('start_time_offset', 0.0))

        self.timeline.set_data(
            duration_s=duration_s,
            bpm=bpm,
            start_offset=start_offset,
            segments=segments,
        )

    def _build_timeline_segments(self):
        """Converts frame rows into coalesced chord segments for the timeline."""
        if not self.timeline_rows:
            return []
        segments = []
        curr_sym = None
        curr_start = 0.0
        curr_cands = []

        for row in self.timeline_rows:
            t = float(row.get('time_s', 0.0))
            pres = row.get('presentation', {})
            cands = pres.get('display_candidates', [])
            sym = cands[0].get('symbol', '') if cands else ''

            if sym != curr_sym:
                if curr_sym is not None:
                    segments.append({
                        'start': curr_start,
                        'end': t,
                        'symbol': curr_sym,
                        'candidates': curr_cands,
                    })
                curr_sym = sym
                curr_start = t
                curr_cands = cands

        if curr_sym is not None:
            last_t = float(self.timeline_rows[-1].get('time_s', curr_start + 0.5))
            segments.append({
                'start': curr_start,
                'end': last_t,
                'symbol': curr_sym,
                'candidates': curr_cands,
            })
        return segments

    def _on_analysis_failed(self, error_msg: str):
        self.prog_bar.setVisible(False)
        self.btn_open.setEnabled(True)
        self.lbl_status.setText("분석 실패")
        QMessageBox.critical(self, "분석 오류", f"분석 중 오류가 발생했습니다:\n{error_msg}")

    def _toggle_playback(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
        else:
            self.player.play()

    def _on_playback_state_changed(self, state):
        if state == QMediaPlayer.PlayingState:
            self.btn_play.setText("⏸ 일시정지 (Space)")
        else:
            self.btn_play.setText("▶ 재생 (Space)")

    def _on_player_position_changed(self, position_ms: int):
        pos_s = position_ms / 1000.0
        dur_s = max(1.0, self.player.duration() / 1000.0)

        self.lbl_time.setText(f"{format_time(pos_s)} / {format_time(dur_s)}")
        self.timeline.set_current_time(pos_s)

        # Update active chord from timeline frames
        if self.timeline_rows:
            # Binary search or scan
            idx = int(round(pos_s * 24))  # 24Hz frame rate
            if 0 <= idx < len(self.timeline_rows):
                row = self.timeline_rows[idx]
                pres = row.get('presentation', {})
                cands = pres.get('display_candidates', [])
                sym = cands[0].get('symbol', '') if cands else ''
                self.video_widget.set_current_chord(sym)
                self.inspector.update_active_chord(sym, cands)

    def _on_player_duration_changed(self, duration_ms: int):
        pos_s = self.player.position() / 1000.0
        dur_s = max(1.0, duration_ms / 1000.0)
        self.lbl_time.setText(f"{format_time(pos_s)} / {format_time(dur_s)}")

    def _on_timeline_seek(self, time_s: float):
        self.player.setPosition(int(time_s * 1000))

    def _seek_relative(self, delta_ms: int):
        new_pos = max(0, min(self.player.duration(), self.player.position() + delta_ms))
        self.player.setPosition(new_pos)

    def _on_segment_selected(self, seg: dict):
        sym = seg.get('symbol', '')
        cands = seg.get('candidates', [])
        self.inspector.update_active_chord(sym, cands)

    def _on_chord_override(self, new_symbol: str):
        """User edited chord: updates current active segment and refreshes timeline."""
        curr_s = self.player.position() / 1000.0
        # Update matching frames in timeline_rows
        changed = 0
        for row in self.timeline_rows:
            t = float(row.get('time_s', 0.0))
            if abs(t - curr_s) <= 0.8:  # 1 beat window
                pres = row.setdefault('presentation', {})
                cands = pres.setdefault('display_candidates', [{}])
                cands[0]['symbol'] = new_symbol
                cands[0]['user_edited'] = True
                changed += 1

        if changed > 0:
            segments = self._build_timeline_segments()
            bpm = float(self.job_data.get('bpm', 120.0)) if self.job_data else 120.0
            dur_s = max(1.0, self.player.duration() / 1000.0)
            self.timeline.set_data(dur_s, bpm, 0.0, segments)
            self.video_widget.set_current_chord(new_symbol)
            self.inspector.update_active_chord(new_symbol)

    def _on_toggle_calibrate(self, checked: bool):
        self.video_widget.toggle_calibration_mode(checked)
        if checked:
            self.btn_calibrate.setText("🎯 지정 완료")
            self.btn_calibrate.setObjectName("btnAccent")
        else:
            self.btn_calibrate.setText("🎯 지판 4점 지정")
            self.btn_calibrate.setObjectName("")
        self.btn_calibrate.setStyleSheet("")

    def _on_capo_changed(self, idx: int):
        self.inspector.diagram.set_chord(self.inspector._active_symbol, capo=idx)

    def _on_speed_changed(self, text: str):
        speed_map = {"0.5x": 0.5, "0.75x": 0.75, "1.0x": 1.0, "1.25x": 1.25}
        rate = speed_map.get(text, 1.0)
        self.player.setPlaybackRate(rate)
