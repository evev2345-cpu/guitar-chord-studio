import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
import webbrowser
import threading

PORT = 8081
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LABEL_DIR = os.path.join(BASE_DIR, 'dataset', 'fret_labels')
os.makedirs(LABEL_DIR, exist_ok=True)

class FretLabelerHandler(BaseHTTPRequestHandler):
    def send_file_response(self, filepath, content_type):
        if not os.path.exists(filepath):
            self.send_error(404, "File not found")
            return
        with open(filepath, 'rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')

        if path == '' or path == '/index.html':
            html_path = os.path.join(BASE_DIR, 'fret_labeler.html')
            self.send_file_response(html_path, 'text/html; charset=utf-8')
            return

        elif path == '/fret_label_model.js':
            self.send_file_response(os.path.join(BASE_DIR, 'fret_label_model.js'), 'text/javascript; charset=utf-8')
            return

        elif path.startswith('/image/'):
            filename = path.replace('/image/', '')
            img_path = os.path.join(BASE_DIR, 'sample_images', filename)
            self.send_file_response(img_path, 'image/png')
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip('/') == '/api/save_frets':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            payload = json.loads(body.decode('utf-8'))

            ids=[w.get('fret_num',w.get('wire_idx')) for w in payload.get('wires',[])]
            if any(type(n) is not int or not 0<=n<=36 for n in ids) or len(ids)!=len(set(ids)):
                self.send_error(400,'Physical fret numbers must be unique integers 0..36')
                return
            for wire, number in zip(payload.get('wires',[]),ids):
                wire['fret_num']=wire['wire_idx']=number
            payload['numbering_semantics']='physical_fret_number; gaps preserved'
            img_name = os.path.basename(payload.get('image', 'user_fret_example.png'))
            json_path = os.path.join(LABEL_DIR, f"{os.path.splitext(img_name)[0]}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)

            print(f"\n[저장 완료] {json_path} 에 {len(payload.get('wires', []))}개 프렛 라벨 저장됨!")

            resp = json.dumps({'status': 'ok', 'saved': json_path}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            return

        self.send_error(404, "Not Found")

def run_server():
    server = HTTPServer(('127.0.0.1', PORT), FretLabelerHandler)
    print(f"🎸 [프렛 라벨러 서버 시작] http://localhost:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()

if __name__ == '__main__':
    # 브라우저 자동 실행
    threading.Timer(0.8, lambda: webbrowser.open(f"http://localhost:{PORT}")).start()
    run_server()
