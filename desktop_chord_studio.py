"""Chord Studio Pro - Native Desktop Application with Polished Dual-View UI."""

import os
import sys
import time
import subprocess
from pathlib import Path
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parent
PYTHON_EXE = ROOT_DIR / ".venv-audio-model" / "Scripts" / "python.exe"
if not PYTHON_EXE.exists():
    PYTHON_EXE = Path(sys.executable)

PORT = 8766
URL = f"http://127.0.0.1:{PORT}"

server_process = None


def is_server_running():
    try:
        with urlopen(f"{URL}/", timeout=1.0) as res:
            return res.status == 200
    except Exception:
        return False


def start_server_if_needed():
    global server_process
    if is_server_running():
        return

    server_script = ROOT_DIR / "chord_studio_v2" / "server_v2.py"
    server_process = subprocess.Popen(
        [
            str(PYTHON_EXE),
            str(server_script),
            "--port", str(PORT),
            "--host", "127.0.0.1",
        ],
        cwd=str(ROOT_DIR),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )

    # Wait up to 5 seconds for server to be ready
    for _ in range(10):
        time.sleep(0.5)
        if is_server_running():
            break


def main():
    # High-DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    # Start backend server
    start_server_if_needed()

    from PySide6.QtCore import Qt, QUrl
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QApplication, QMainWindow
    from PySide6.QtWebEngineWidgets import QWebEngineView

    app = QApplication(sys.argv)
    app.setApplicationName("Chord Studio Pro")
    app.setOrganizationName("GuitarLab")

    window = QMainWindow()
    window.setWindowTitle("🎸 Chord Studio Pro - 듀얼 뷰(지판 & 악보) 데스크톱")
    window.resize(1340, 840)
    window.setMinimumSize(1024, 680)

    # Dark background for the window frame
    window.setStyleSheet("QMainWindow { background-color: #0b0f19; }")

    view = QWebEngineView(window)
    view.load(QUrl(URL))
    window.setCentralWidget(view)

    # Clean shutdown of server when desktop window closes
    def on_close(event):
        global server_process
        if server_process and server_process.poll() is None:
            server_process.terminate()
        event.accept()

    window.closeEvent = on_close

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
