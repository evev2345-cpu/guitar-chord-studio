"""Chord Studio Pro - Native Windows Desktop Application.

Uses Microsoft Edge WebView2 (pywebview) for full native H.264/MP4/AAC hardware decoding,
lightweight memory usage, and 100% faithful rendering of the Dual-View UI.
"""

import os
import sys
import threading
import time
from pathlib import Path
from urllib.request import urlopen

ROOT_DIR = Path(__file__).resolve().parent
ENGINE_DIR = ROOT_DIR / "engine"
CHORD_V2_DIR = ROOT_DIR / "chord_studio_v2"
BIN_DIR = ROOT_DIR / "bin"

if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(ENGINE_DIR))
if str(CHORD_V2_DIR) not in sys.path:
    sys.path.insert(0, str(CHORD_V2_DIR))

if BIN_DIR.exists():
    os.environ["PATH"] = str(BIN_DIR) + os.pathsep + os.environ.get("PATH", "")

PORT = 8766
URL = f"http://127.0.0.1:{PORT}"


def is_server_ready():
    try:
        with urlopen(f"{URL}/", timeout=0.8) as res:
            return res.status == 200
    except Exception:
        return False


def run_embedded_server():
    """Runs server_v2 inside this process in a daemon thread."""
    try:
        import server_v2

        server_v2.seed_existing_runs()
        server = server_v2.ThreadingHTTPServer(("127.0.0.1", PORT), server_v2.HandlerV2)
        server.allow_public = False
        server.serve_forever()
    except Exception as e:
        print(f"Embedded server notice: {e}", flush=True)


def ensure_server():
    if is_server_ready():
        return
    t = threading.Thread(target=run_embedded_server, daemon=True)
    t.start()

    for _ in range(12):
        time.sleep(0.5)
        if is_server_ready():
            break


def main():
    ensure_server()

    import webview

    window = webview.create_window(
        title="🎸 Chord Studio Pro - 듀얼 뷰(지판 & 악보) 데스크톱 에디션",
        url=URL,
        width=1340,
        height=840,
        min_size=(1024, 680),
        background_color="#0b0f19",
    )
    # Starts the native Windows WebView2 window with full hardware H.264/MP4 video codec support
    webview.start(debug=False)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()

    # Exercise the same packaged upload/analysis pipeline without opening a GUI.
    # Useful for portable-release validation; never invokes a system interpreter.
    if '--serve-only' in sys.argv:
        import argparse
        import server_v2
        parser = argparse.ArgumentParser()
        parser.add_argument('--serve-only', action='store_true')
        parser.add_argument('--port', type=int, default=8766)
        args = parser.parse_args()
        server_v2.seed_existing_runs()
        http = server_v2.ThreadingHTTPServer(('127.0.0.1', args.port), server_v2.HandlerV2)
        http.allow_public = False
        http.serve_forever()
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1].endswith(".py"):
        script_file = Path(sys.argv[1])
        if script_file.exists():
            import runpy
            sys.argv = sys.argv[1:]
            runpy.run_path(str(script_file), run_name="__main__")
            sys.exit(0)

    main()
