import cv2
import numpy as np
import shutil
import os

class FretBoxSegmenter:
    """
    프렛 와이어를 일차함수(x = m*y + b)로 모델링하고,
    와이어 사이의 '칸(Fret Cell/Box)' 단위로 지판을 분할하는 모듈.
    """
    def __init__(self, raw_img_path, corners, canvas_w=800, canvas_h=150):
        self.raw_img_path = raw_img_path
        self.raw = cv2.imread(raw_img_path)
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        # corners: [nut_top, body_top, body_bottom, nut_bottom]
        self.src = np.array(corners, dtype=np.float32)
        self.dst = np.array([[0,0], [canvas_w, 0], [canvas_w, canvas_h], [0, canvas_h]], dtype=np.float32)

        self.M = cv2.getPerspectiveTransform(self.src, self.dst)
        self.M_inv = cv2.getPerspectiveTransform(self.dst, self.src)

        self.flat = cv2.warpPerspective(self.raw, self.M, (canvas_w, canvas_h))
        self.wires = [] # [(m, b, xt, xb), ...]
        self.cells = [] # [Cell 1, Cell 2, ...]

    def detect_wires(self):
        gray = cv2.cvtColor(self.flat, cv2.COLOR_BGR2GRAY)

        # 1. 기타줄 신호 제거
        k_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11))
        fret_ridges = cv2.morphologyEx(gray, cv2.MORPH_OPEN, k_vert)

        # 2. 로컬 대비 강화
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(fret_ridges)

        # 3. 엣지 그래디언트
        grad_x = np.abs(cv2.Sobel(enhanced, cv2.CV_64F, 1, 0, ksize=3))

        # 4. 상단 스트립(y: 15..50)과 하단 스트립(y: 100..135)에서 독립적으로 피크 검출
        from scipy.signal import find_peaks
        strip_top = np.mean(grad_x[15:50, :], axis=0)
        strip_bot = np.mean(grad_x[100:135, :], axis=0)

        p_top, _ = find_peaks(strip_top, distance=12, prominence=4.0)
        p_bot, _ = find_peaks(strip_bot, distance=12, prominence=4.0)

        def cluster_peaks(peaks, max_dist=16):
            clusters = []
            if len(peaks) == 0:
                return clusters
            curr = [peaks[0]]
            for p in peaks[1:]:
                if p - curr[-1] <= max_dist:
                    curr.append(p)
                else:
                    clusters.append(float(np.mean(curr)))
                    curr = [p]
            if curr:
                clusters.append(float(np.mean(curr)))
            return clusters

        top_centers = cluster_peaks(p_top)
        bot_centers = cluster_peaks(p_bot)

        # 페어링 및 일차함수 계산: x(y) = m * y + b
        # y=0 일 때 x = xt = b
        # y=canvas_h 일 때 x = xb
        # m = (xb - xt) / canvas_h
        min_len = min(len(top_centers), len(bot_centers))
        self.wires = []
        for i in range(min_len):
            xt = top_centers[i]
            xb = bot_centers[i]
            m = (xb - xt) / float(self.canvas_h)
            b = xt
            self.wires.append({
                'wire_idx': i,
                'm': m,
                'b': b,
                'xt': xt,
                'xb': xb,
                'formula': f"x = {m:+.4f}*y + {b:6.1f}"
            })

        print(f"✅ 총 {len(self.wires)}개의 프렛 와이어 일차함수 모델링 완료.")
        return self.wires

    def query_fret_box(self, px, py):
        """
        주어진 (px, py) 좌표가 몇 번 프렛 '칸(Box)'에 위치하는지 판정.
        Wire[k-1] <= x(y) < Wire[k] -> Fret Box k
        """
        if len(self.wires) < 2:
            return None

        # 각 와이어의 현재 y 위치에서의 x값 계산
        wire_xs = [w['m'] * py + w['b'] for w in self.wires]

        if px < wire_xs[0]:
            return 0 # 너트 바깥 (헤드스톡 쪽)

        for k in range(1, len(wire_xs)):
            if wire_xs[k-1] <= px < wire_xs[k]:
                # 6개 현 중 몇 번 줄인지도 함께 판정 (0: 6번줄, 5: 1번줄)
                string_num = 6 - int(py / (self.canvas_h / 6.0))
                string_num = max(1, min(6, string_num))
                return {
                    'fret_cell': k,
                    'string': string_num,
                    'left_wire_x': wire_xs[k-1],
                    'right_wire_x': wire_xs[k]
                }

        return {'fret_cell': len(wire_xs), 'string': 1}

    def render_cells(self, out_prefix="sample_images/suhr_boxes"):
        """
        프렛 단위가 아닌 '칸(Cell)' 단위로 색상을 입혀 시각화
        """
        vis_flat = self.flat.copy()
        overlay = vis_flat.copy()

        # 각 칸을 구분하는 교대 색상 (반투명 파스텔 톤)
        colors = [
            (255, 100, 100), (100, 255, 100), (100, 150, 255),
            (255, 200, 100), (200, 100, 255), (100, 255, 255)
        ]

        # 1. 칸(Cell) 단위 다각형 채우기
        num_cells = len(self.wires) - 1
        for k in range(num_cells):
            w_left = self.wires[k]
            w_right = self.wires[k + 1]

            # 4개 꼭짓점 다각형 (사다리꼴)
            poly = np.array([
                [w_left['xt'], 0],
                [w_right['xt'], 0],
                [w_right['xb'], self.canvas_h],
                [w_left['xb'], self.canvas_h]
            ], dtype=np.int32)

            color = colors[k % len(colors)]
            cv2.fillPoly(overlay, [poly], color)

        # 반투명 블렌딩
        cv2.addWeighted(overlay, 0.25, vis_flat, 0.75, 0, vis_flat)

        # 2. 와이어 경계선 (일차함수 선) 및 칸 번호 라벨링
        for k, w in enumerate(self.wires):
            pt_top = (int(round(w['xt'])), 0)
            pt_bot = (int(round(w['xb'])), self.canvas_h)
            cv2.line(vis_flat, pt_top, pt_bot, (0, 255, 0), 2)

        for k in range(num_cells):
            w_left = self.wires[k]
            w_right = self.wires[k + 1]
            mid_x = int(round((w_left['xt'] + w_right['xt'] + w_left['xb'] + w_right['xb']) / 4.0))
            cv2.putText(vis_flat, f"{k+1}칸", (mid_x - 12, int(self.canvas_h / 2) + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
            cv2.putText(vis_flat, f"{k+1}칸", (mid_x - 12, int(self.canvas_h / 2) + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # 6개 기타줄 가로선
        for s in range(6):
            sy = int((s + 0.5) / 6.0 * self.canvas_h)
            cv2.line(vis_flat, (0, sy), (self.canvas_w, sy), (0, 220, 255), 1)

        out_flat_path = f"{out_prefix}_flat.png"
        cv2.imwrite(out_flat_path, vis_flat)

        # 3. 원본 원근 사진에 '칸' 다각형 투영
        vis_raw = self.raw.copy()
        overlay_raw = vis_raw.copy()

        for k in range(num_cells):
            w_left = self.wires[k]
            w_right = self.wires[k + 1]

            pts_flat = np.array([
                [[w_left['xt'], 0]],
                [[w_right['xt'], 0]],
                [[w_right['xb'], self.canvas_h]],
                [[w_left['xb'], self.canvas_h]]
            ], dtype=np.float32)

            pts_raw = cv2.perspectiveTransform(pts_flat, self.M_inv)
            poly_raw = pts_raw.astype(np.int32).reshape(-1, 2)

            color = colors[k % len(colors)]
            cv2.fillPoly(overlay_raw, [poly_raw], color)

        cv2.addWeighted(overlay_raw, 0.35, vis_raw, 0.65, 0, vis_raw)

        # 원본에 와이어 선분 및 칸 번호 표시
        for k, w in enumerate(self.wires):
            p_top_flat = np.array([[[w['xt'], 0]]], dtype=np.float32)
            p_bot_flat = np.array([[[w['xb'], self.canvas_h]]], dtype=np.float32)
            pt_top = cv2.perspectiveTransform(p_top_flat, self.M_inv)[0][0]
            pt_bot = cv2.perspectiveTransform(p_bot_flat, self.M_inv)[0][0]
            p1 = (int(round(pt_top[0])), int(round(pt_top[1])))
            p2 = (int(round(pt_bot[0])), int(round(pt_bot[1])))
            cv2.line(vis_raw, p1, p2, (0, 255, 0), 1)

        for k in range(num_cells):
            w_left = self.wires[k]
            w_right = self.wires[k + 1]
            p_mid_flat = np.array([[[(w_left['xt'] + w_right['xt']) / 2.0, self.canvas_h / 2.0]]], dtype=np.float32)
            p_mid = cv2.perspectiveTransform(p_mid_flat, self.M_inv)[0][0]
            if k in [0, 2, 4, 6, 8, 11, 14, 16, 18, 20]: # 1,3,5,7,9,12,15,17,19,21칸
                cv2.putText(vis_raw, f"{k+1}", (int(p_mid[0]) - 4, int(p_mid[1]) + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 2)
                cv2.putText(vis_raw, f"{k+1}", (int(p_mid[0]) - 4, int(p_mid[1]) + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        out_raw_path = f"{out_prefix}_raw.png"
        cv2.imwrite(out_raw_path, vis_raw)

        # 아티팩트 디렉터리 복사
        art_dir = "C:/Users/evev2/.gemini/antigravity/brain/b097f49a-587f-45e1-b717-5940c8f33184"
        shutil.copy(out_flat_path, os.path.join(art_dir, "suhr_fret_boxes_flat.png"))
        shutil.copy(out_raw_path, os.path.join(art_dir, "suhr_fret_boxes_raw.png"))

        print(f"💾 시각화 완료:\n  - 평면 칸 박스: {out_flat_path}\n  - 원본 투영 박스: {out_raw_path}")
        return out_flat_path, out_raw_path

if __name__ == "__main__":
    corners = [[435, 239], [249, 258], [265, 298], [439, 256]]
    segmenter = FretBoxSegmenter("sample_images/user_test_suhr_maple.png", corners)
    wires = segmenter.detect_wires()
    segmenter.render_cells()

    # 테스트 좌표 Hit Test
    print("\n🎯 [손가락 좌표 Hit-Test 테스트]")
    test_pts = [
        (45, 30),   # 2칸 6번줄
        (180, 75),  # 5칸 3번줄
        (480, 110), # 13칸 2번줄
        (720, 25)   # 20칸 6번줄
    ]
    for px, py in test_pts:
        res = segmenter.query_fret_box(px, py)
        print(f"  좌표 ({px:3d}, {py:3d}) ➔ {res['fret_cell']}번 프렛 칸, {res['string']}번 줄 연주!")
