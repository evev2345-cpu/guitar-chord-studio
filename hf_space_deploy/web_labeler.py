import os
import json
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, 'sample_images')
LABEL_DIR = os.path.join(BASE_DIR, 'dataset', 'labels')
os.makedirs(LABEL_DIR, exist_ok=True)

class LabelerHandler(BaseHTTPRequestHandler):
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

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip('/')

        # 1. 메인 HTML
        if path == '' or path == '/index.html':
            html_path = os.path.join(BASE_DIR, 'web_labeler.html')
            self.send_file_response(html_path, 'text/html; charset=utf-8')
            return

        # 2. 이미지 목록 API
        elif path == '/api/images':
            all_files = sorted(os.listdir(IMG_DIR))
            valid = [
                f for f in all_files 
                if f.lower().endswith(('.jpg', '.jpeg', '.png')) 
                and not f.startswith(('result_', 'crop_', 'fretboard_', 'debug_', 'seg_', 'interactive_', 'cutout_'))
            ]
            items = []
            for img in valid:
                lbl_file = os.path.join(LABEL_DIR, f"{os.path.splitext(img)[0]}.json")
                labeled = os.path.exists(lbl_file)
                data = None
                if labeled:
                    try:
                        with open(lbl_file, 'r', encoding='utf-8') as lf:
                            data = json.load(lf)
                    except:
                        pass
                items.append({'filename': img, 'labeled': labeled, 'data': data})
            
            resp_data = json.dumps(items, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(resp_data)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(resp_data)
            return

        # 3. 이미지 서빙 (/image/<filename> 또는 /sample_images/<filename>)
        elif path.startswith('/image/') or path.startswith('/sample_images/'):
            raw_name = path.replace('/image/', '').replace('/sample_images/', '')
            filename = urllib.parse.unquote(raw_name)
            img_path = os.path.join(IMG_DIR, filename)
            
            ext = os.path.splitext(filename)[1].lower()
            ctype = 'image/png' if ext == '.png' else 'image/jpeg'
            self.send_file_response(img_path, ctype)
            return

        self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path.rstrip('/') == '/api/save':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            payload = json.loads(body.decode('utf-8'))
            
            img_name = payload['image']
            w = payload['width']
            h = payload['height']
            corners = payload['corners']
            
            # JSON 저장
            json_path = os.path.join(LABEL_DIR, f"{os.path.splitext(img_name)[0]}.json")
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
                
            # YOLO txt 저장 (keypoints normalized)
            txt_path = os.path.join(LABEL_DIR, f"{os.path.splitext(img_name)[0]}.txt")
            xs = [p['x'] / w for p in corners]
            ys = [p['y'] / h for p in corners]
            bx_center = (min(xs) + max(xs)) / 2.0
            by_center = (min(ys) + max(ys)) / 2.0
            bw = max(xs) - min(xs)
            bh = max(ys) - min(ys)
            kpts_str = " ".join([f"{x:.6f} {y:.6f} 2" for x, y in zip(xs, ys)])
            with open(txt_path, 'w', encoding='utf-8') as f:
                f.write(f"0 {bx_center:.6f} {by_center:.6f} {bw:.6f} {bh:.6f} {kpts_str}\n")
                
            resp = json.dumps({'status': 'ok'}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)
            print(f"✅ 저장 완료: {img_name}")
            return

def start_server():
    server = HTTPServer(('127.0.0.1', PORT), LabelerHandler)
    print(f"🚀 웹 지판 라벨러 실행: http://127.0.0.1:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()

if __name__ == '__main__':
    start_server()
