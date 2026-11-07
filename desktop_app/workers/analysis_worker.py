"""Background Analysis QThread for Demucs, Basic Pitch, and Harmony Engine."""

import sys
import json
import shutil
import subprocess
import hashlib
from pathlib import Path
from PySide6.QtCore import QThread, Signal

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
ENGINE_DIR = ROOT_DIR / 'engine'
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))

PYTHON_EXE = sys.executable


def get_audio_duration(file_path: Path) -> float:
    cmd = [
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", str(file_path)
    ]
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode('utf-8').strip()
        return float(out)
    except Exception:
        return 180.0


class AnalysisWorker(QThread):
    progress_updated = Signal(int, str)
    analysis_finished = Signal(dict, dict)  # (result_dict, job_dict)
    analysis_failed = Signal(str)

    def __init__(self, media_path: str, separate_guitar: bool = False, parent=None):
        super().__init__(parent)
        self.media_path = Path(media_path)
        self.separate_guitar = separate_guitar

    def run(self):
        try:
            if not self.media_path.exists():
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {self.media_path}")

            self.progress_updated.emit(5, "미디어 파일 확인 중...")

            # 1. Check for existing runs cache
            file_hash = hashlib.sha256(self.media_path.read_bytes()[:1024 * 1024 * 4]).hexdigest()[:16]
            run_cache_dir = ROOT_DIR / "runs_desktop" / file_hash
            run_cache_dir.mkdir(parents=True, exist_ok=True)
            cached_result = run_cache_dir / "result.json"
            cached_job = run_cache_dir / "job.json"

            if cached_result.exists() and cached_job.exists():
                self.progress_updated.emit(95, "기존 분석 결과 로딩 중...")
                r_data = json.loads(cached_result.read_text(encoding='utf-8'))
                j_data = json.loads(cached_job.read_text(encoding='utf-8'))
                self.progress_updated.emit(100, "분석 완료")
                self.analysis_finished.emit(r_data, j_data)
                return

            # 2. Extract Audio
            self.progress_updated.emit(15, "오디오 추출 및 표준화 중...")
            audio_path = run_cache_dir / "audio.wav"
            is_video = self.media_path.suffix.lower() in [".mp4", ".mov", ".mkv", ".avi", ".webm"]

            if is_video:
                cmd = [
                    "ffmpeg", "-y", "-i", str(self.media_path),
                    "-vn", "-acodec", "pcm_s16le", "-ar", "22050", "-ac", "1",
                    str(audio_path),
                ]
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            else:
                shutil.copy2(self.media_path, audio_path)

            duration = get_audio_duration(audio_path)
            analysis_audio = audio_path
            separation_status = "original_audio"

            # 3. Guitar Separation (Demucs) if enabled
            if self.separate_guitar:
                self.progress_updated.emit(35, "Demucs AI로 기타 트랙 분리 중...")
                sep_py = ENGINE_DIR / "run_local_separation.py"
                if sep_py.exists():
                    sep_out = run_cache_dir / "separation"
                    cmd = [
                        PYTHON_EXE, str(sep_py),
                        "--input", str(audio_path),
                        "--model", "htdemucs_6s",
                        "--stem", "guitar",
                        "--output", str(sep_out),
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    guitar_stem = sep_out / "htdemucs_6s" / "audio" / "guitar.wav"
                    if guitar_stem.exists():
                        shutil.copyfile(guitar_stem, run_cache_dir / "guitar.wav")
                        analysis_audio = run_cache_dir / "guitar.wav"
                        separation_status = "separated_htdemucs_6s"

            # 4. Basic Pitch Note Transcription
            self.progress_updated.emit(60, "Basic Pitch AI 모델로 음표 및 화성 감지 중...")
            tasks = [dict(id='upload', audio=str(analysis_audio))]
            if audio_path.exists() and str(analysis_audio) != str(audio_path):
                tasks.append(dict(id='full_mix', audio=str(audio_path)))
            (run_cache_dir / 'tasks.json').write_text(json.dumps(tasks), encoding='utf-8')

            bp_worker = ENGINE_DIR / "basic_pitch_worker.py"
            cmd = [
                PYTHON_EXE, str(bp_worker),
                "--tasks", str(run_cache_dir / "tasks.json"),
                "--output", str(run_cache_dir / "prediction"),
                "--modes", "raw",
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)

            # 5. Beat Grid Quantization & Result Generation
            self.progress_updated.emit(85, "16박자 격자 정렬 및 화성 진행 정돈 중...")
            from chord_web_analysis import write_result
            write_result(run_cache_dir, duration)

            # Load results
            r_data = json.loads(cached_result.read_text(encoding='utf-8'))
            j_data = {}
            if cached_job.exists():
                j_data = json.loads(cached_job.read_text(encoding='utf-8'))
            else:
                j_data = {
                    "duration": duration,
                    "media": self.media_path.name,
                    "separation_status": separation_status,
                }
                cached_job.write_text(json.dumps(j_data, ensure_ascii=False, indent=2), encoding='utf-8')

            self.progress_updated.emit(100, "분석 완료!")
            self.analysis_finished.emit(r_data, j_data)

        except Exception as e:
            self.analysis_failed.emit(str(e))
