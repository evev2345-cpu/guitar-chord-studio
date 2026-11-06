import cv2
import numpy as np
import json
import base64
import os

from fret_geometry import resolve_frets, build_cells
from fretboard_prompts import CANDIDATE_PROMPT, CORNER_PROMPT
from string_detector import detect_strings, render_strings, query_string_fret

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
from baze_client import call_baze_json, settings


def encode_cv2_image(img, quality=90):
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode('utf-8')

def resize_for_analysis(image, max_side=1400):
    scale = min(1.0, max_side / max(image.shape[:2]))
    return cv2.resize(image, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else image


CORNER_NAMES = ('nut_top', 'body_top', 'body_bottom', 'nut_bottom')


def prepare_candidate_crop(image, bbox, margin=0.15):
    values = np.asarray(bbox, dtype=float)
    if values.shape != (4,) or not np.isfinite(values).all() or (values < 0).any() or (values > 1000).any():
        raise ValueError('Invalid candidate bbox')
    h, w = image.shape[:2]
    ya, xa, yb, xb = values / 1000
    if xa >= xb or ya >= yb:
        raise ValueError('Empty candidate bbox')
    mx, my = (xb-xa)*margin, (yb-ya)*margin
    x0, y0 = max(0, int(np.floor((xa-mx)*w))), max(0, int(np.floor((ya-my)*h)))
    x1, y1 = min(w, int(np.ceil((xb+mx)*w))), min(h, int(np.ceil((yb+my)*h)))
    crop = image[y0:y1, x0:x1]
    scale = max(1.0, 1400/max(crop.shape[:2]))
    enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    return enlarged, (x0,y0,x1,y1)


def map_crop_corners(response, bounds):
    x0,y0,x1,y1 = bounds
    corners = []
    for name in CORNER_NAMES:
        point = np.asarray(response[name], dtype=float)
        if point.shape != (2,) or not np.isfinite(point).all() or (point < 0).any() or (point > 1000).any():
            raise ValueError(f'Invalid corner: {name}')
        corners.append((x0+point[1]/1000*(x1-x0), y0+point[0]/1000*(y1-y0)))
    polygon = np.asarray(corners, np.float32)
    if not cv2.isContourConvex(polygon) or abs(cv2.contourArea(polygon)) < 10:
        raise ValueError('Degenerate or crossed fretboard corners')
    return corners


class TwoStageFretPipeline:
    def __init__(self, raw_img_path, canvas_w=800, canvas_h=150, model=None, api_call=None):
        self.api_calls = []
        self.model = model
        self.api_call = api_call or call_baze_json
        self.raw_img_path = raw_img_path
        self.raw = cv2.imread(raw_img_path)
        if self.raw is None:
            raise FileNotFoundError(f"이미지를 찾을 수 없습니다: {raw_img_path}")
        self.h, self.w, _ = self.raw.shape
        self.canvas_w = canvas_w
        self.canvas_h = canvas_h

        self.corners = None
        self.flat = None
        self.flat_enhanced = None
        self.M = None
        self.M_inv = None
        self.frets = []

    def _call_json(self, contents, timeout=120):
        if self.model is None:
            _, self.model = settings()
        try:
            result, usage = self.api_call(contents, timeout=timeout, model=self.model)
        except Exception as error:
            self.api_calls.append(dict(model=self.model, error=str(error),
                                       usage=getattr(error, 'usage', {})))
            raise
        self.api_calls.append(dict(model=self.model, response=result, usage=usage))
        return result, usage

    def stage1_detect_corners(self):
        print("\n🔹 [1단계] 1차 API로 기타 지판 4개 코너 검출 중...")
        candidate_prompt = CANDIDATE_PROMPT
        candidate, candidate_usage = self._call_json([{'role': 'user', 'parts': [
            {'text': candidate_prompt},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': encode_cv2_image(resize_for_analysis(self.raw))}}]}])
        crop, bounds = prepare_candidate_crop(self.raw, candidate['bbox'])
        x0, y0, x1, y1 = bounds
        prompt = CORNER_PROMPT
        res, usage = self._call_json([{'role': 'user', 'parts': [
            {'text': prompt},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': encode_cv2_image(crop)}}]}], timeout=60)
        self.corners = map_crop_corners(res, bounds)
        self.corner_detection = dict(candidate_bbox=candidate['bbox'], crop_bounds=bounds,
                                     crop_corners=res, usage=[candidate_usage, usage])
        self.corner_crop = crop
        return self.corners

    def stage2_unwarp_and_enhance(self):
        print("\n🔹 [2단계] OpenCV 투시 변환 및 고대비 보정 (CLAHE + 언샵 마스크)...")
        src = np.array(self.corners, dtype=np.float32)
        dst = np.array([
            [0, 0],
            [self.canvas_w, 0],
            [self.canvas_w, self.canvas_h],
            [0, self.canvas_h]
        ], dtype=np.float32)

        self.M = cv2.getPerspectiveTransform(src, dst)
        self.M_inv = cv2.getPerspectiveTransform(dst, src)
        self.flat = cv2.warpPerspective(self.raw, self.M, (self.canvas_w, self.canvas_h))

        # 고대비 보정: LAB L-channel CLAHE + High-Pass 언샵 샤프닝
        lab = cv2.cvtColor(self.flat, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
        l_clahe = clahe.apply(l)
        bgr_enhanced = cv2.cvtColor(cv2.merge([l_clahe, a, b]), cv2.COLOR_LAB2BGR)
        blur = cv2.GaussianBlur(bgr_enhanced, (0, 0), 1.5)
        self.flat_enhanced = cv2.addWeighted(bgr_enhanced, 2.0, blur, -1.0, 0)

        print("  지판 평탄화 및 대비 보정 완료!")
        return self.flat_enhanced

    def stage3_detect_frets_two_points(self, result=None):
        """Detect with a human exemplar, or process a cached response offline."""
        if result is None:
            exemplar_path = os.path.join(BASE_DIR, 'sample_images/user_fret_example.png')
            label_path = os.path.join(BASE_DIR, 'dataset/fret_labels/user_fret_example.json')
            exemplar = cv2.imread(exemplar_path)
            if exemplar is None:
                raise FileNotFoundError(exemplar_path)
            with open(label_path, encoding='utf-8') as f:
                labels = json.load(f)
            examples = []
            for wire in labels['wires']:
                points = []
                for fraction in (0.1, 0.9):
                    x = wire['xt'] + (wire['xb'] - wire['xt']) * fraction
                    points.append([fraction * 1000, x / labels['width'] * 1000])
                examples.append(dict(fret_num=wire['wire_idx'], occluded=False,
                                     p1=points[0], p2=points[1]))
            prompt = """Inspect the target flattened guitar fretboard using the human exemplar.
Return JSON {"frets": [{"fret_num": 0, "occluded": false,
"p1": [y,x], "p2": [y,x]}, {"fret_num": 1, "occluded": true,
"reason": "covered by hand"}]} with coordinates normalized to [0,1000].
Fret 0 is the nut. Preserve actual physical fret numbers, including gaps.
Only mark two distinct points on a clearly visible segment of the SAME metal wire.
Short certain segments are welcome; never force points to the board edges.
The pixel-space segment must be steep: abs(dy) > abs(dx).
Do not mistake shadows, wood grain, fingers or inlays for wires.
When a wire is hidden or uncertain, report occluded=true with a reason and no points.
Do not infer which strings are pressed from occlusion alone.
Do not invent a visible wire or renumber later frets to close a gap.
The crop was mapped from nut corners to the LAST metal wire corners:
its left edge corresponds to the nut, and its right edge to the last fret wire.
A wire exactly on an image edge may be clipped; mark it occluded if not visible.
Include "last_fret_num": integer or null at the root of the JSON object.
Determine this number from the visible wire sequence and inlays; never assume
all guitars have the same last fret number. Use null if uncertain.
Inspect both the natural-color target and contrast-enhanced target, which share
exactly the same coordinates. Do not identify clothing or decorative overlays as wires."""
            contents = [
                {'role': 'user', 'parts': [
                    {'text': 'Human ground truth exemplar'},
                    {'inline_data': {'mime_type': 'image/jpeg', 'data': encode_cv2_image(exemplar)}}]},
                {'role': 'model', 'parts': [{'text': json.dumps({'frets': examples})}]},
                {'role': 'user', 'parts': [
                    {'text': prompt},
                    {'inline_data': {'mime_type': 'image/jpeg', 'data': encode_cv2_image(self.flat)}},
                    {'inline_data': {'mime_type': 'image/jpeg', 'data': encode_cv2_image(self.flat_enhanced)}}]}
            ]
            result, _ = self._call_json(contents, timeout=120)
        self.fret_records = resolve_frets(result, self.canvas_w, self.canvas_h, board_boundaries=self.corners is not None)
        self.frets = [f for f in self.fret_records if 'xt' in f]
        self.cells = build_cells(self.frets)
        return self.fret_records

    def stage4_detect_strings(self):
        """Local image processing only; does not invoke a model or network."""
        from string_geometry import analyze_saved_board
        board = dict(corners=self.corners, frets=self.fret_records, canvas_size=[self.canvas_w,self.canvas_h])
        self.string_result, _, _, _, _ = analyze_saved_board(self.raw, board, source_id=self.raw_img_path)
        return self.string_result

    def query_position(self, x, y, allow_estimates=False):
        return query_string_fret(x, y, self.string_result, self.fret_records, allow_estimates)

    def render_and_save(self, out_prefix="sample_images/two_stage_enhanced"):
        print("\n🔹 [4단계] 프렛 직선 및 '칸(Fret Box)' 시각화 생성 중...")
        self.stage4_detect_strings()
        vis_flat = self.flat.copy()
        overlay_flat = vis_flat.copy()

        colors = [
            (255, 90, 90), (90, 255, 90), (90, 150, 255),
            (255, 200, 70), (200, 90, 255), (70, 255, 255)
        ]

        num_cells = len(self.cells)
        for k in range(num_cells):
            f1, f2 = self.cells[k]

            poly = np.array([
                [f1['xt'], 0],
                [f2['xt'], 0],
                [f2['xb'], self.canvas_h],
                [f1['xb'], self.canvas_h]
            ], dtype=np.int32)

            color = colors[k % len(colors)]
            cv2.fillPoly(overlay_flat, [poly], color)

        cv2.addWeighted(overlay_flat, 0.35, vis_flat, 0.65, 0, vis_flat)

        for f in self.frets:
            pt_top = (int(round(f['xt'])), 0)
            pt_bot = (int(round(f['xb'])), self.canvas_h)
            cv2.line(vis_flat, pt_top, pt_bot, (255, 0, 255) if f.get('estimated') else ((255, 200, 0) if f.get('interpolated') else (0, 255, 0)), 2)

            if 'raw_p1' not in f:
                continue
            p1 = (int(round(f['raw_p1'][0])), int(round(f['raw_p1'][1])))
            p2 = (int(round(f['raw_p2'][0])), int(round(f['raw_p2'][1])))
            cv2.circle(vis_flat, p1, 3, (0, 255, 255), -1)
            cv2.circle(vis_flat, p2, 3, (0, 255, 255), -1)

        for k in range(num_cells):
            f1, f2 = self.cells[k]
            mid_x = int(round((f1['xt'] + f2['xt'] + f1['xb'] + f2['xb']) / 4.0))
            cv2.putText(vis_flat, str(f2['fret_num']), (mid_x - 5, int(self.canvas_h / 2) + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
            cv2.putText(vis_flat, str(f2['fret_num']), (mid_x - 5, int(self.canvas_h / 2) + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        out_flat_path = f"{out_prefix}_flat_boxes.png"
        cv2.imwrite(out_flat_path, vis_flat)

        vis_raw = self.raw.copy()
        overlay_raw = vis_raw.copy()

        for k in range(num_cells):
            f1, f2 = self.cells[k]

            pts_flat = np.array([
                [[f1['xt'], 0]],
                [[f2['xt'], 0]],
                [[f2['xb'], self.canvas_h]],
                [[f1['xb'], self.canvas_h]]
            ], dtype=np.float32)

            pts_raw = cv2.perspectiveTransform(pts_flat, self.M_inv)
            poly_raw = pts_raw.astype(np.int32).reshape(-1, 2)

            color = colors[k % len(colors)]
            cv2.fillPoly(overlay_raw, [poly_raw], color)

        cv2.addWeighted(overlay_raw, 0.35, vis_raw, 0.65, 0, vis_raw)

        for f in self.frets:
            p_top_flat = np.array([[[f['xt'], 0]]], dtype=np.float32)
            p_bot_flat = np.array([[[f['xb'], self.canvas_h]]], dtype=np.float32)
            pt_top = cv2.perspectiveTransform(p_top_flat, self.M_inv)[0][0]
            pt_bot = cv2.perspectiveTransform(p_bot_flat, self.M_inv)[0][0]
            p1 = (int(round(pt_top[0])), int(round(pt_top[1])))
            p2 = (int(round(pt_bot[0])), int(round(pt_bot[1])))
            cv2.line(vis_raw, p1, p2, (255, 0, 255) if f.get('estimated') else ((255, 200, 0) if f.get('interpolated') else (0, 255, 0)), 1)

        for k in range(num_cells):
            f1, f2 = self.cells[k]
            p_mid_flat = np.array([[[(f1['xt'] + f2['xt']) / 2.0, self.canvas_h / 2.0]]], dtype=np.float32)
            p_mid = cv2.perspectiveTransform(p_mid_flat, self.M_inv)[0][0]
            if k in [0, 2, 4, 6, 8, 11, 14, 16, 18, 20]:
                cv2.putText(vis_raw, str(f2['fret_num']), (int(p_mid[0]) - 4, int(p_mid[1]) + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 0), 2)
                cv2.putText(vis_raw, str(f2['fret_num']), (int(p_mid[0]) - 4, int(p_mid[1]) + 4),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.35, (255, 255, 255), 1)

        out_raw_path = f"{out_prefix}_raw_boxes.png"
        cv2.imwrite(out_raw_path, vis_raw)

        string_flat, string_raw = render_strings(self.flat, self.raw, self.M_inv, self.string_result)
        cv2.imwrite(f"{out_prefix}_flat_strings.png", string_flat)
        cv2.imwrite(f"{out_prefix}_raw_strings.png", string_raw)
        grid_flat, grid_raw = render_strings(vis_flat, vis_raw, self.M_inv, self.string_result)
        cv2.imwrite(f"{out_prefix}_flat_grid.png", grid_flat)
        cv2.imwrite(f"{out_prefix}_raw_grid.png", grid_raw)

        out_json_path = f"{out_prefix}_result.json"
        with open(out_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                'raw_image': self.raw_img_path,
                'model': self.model,
                'api_calls': self.api_calls,
                'corners': self.corners,
                'corner_detection': getattr(self, 'corner_detection', None),
                'strings': self.string_result,
                'frets': self.fret_records
            }, f, indent=2, ensure_ascii=False)

        print(f"\n🎉 [저장 완료]\n  - 평탄화 칸 시각화: {out_flat_path}\n  - 원본 투영 시각화: {out_raw_path}\n  - 최종 JSON: {out_json_path}")
        return out_flat_path, out_raw_path

    def run(self, corners=None, fret_result=None, out_prefix="sample_images/two_stage_enhanced"):
        if corners is None:
            self.stage1_detect_corners()
        else:
            if isinstance(corners, dict):
                self.corners = [(corners[n][1] / 1000 * self.w,
                                 corners[n][0] / 1000 * self.h)
                                for n in ('nut_top', 'body_top', 'body_bottom', 'nut_bottom')]
            else:
                self.corners = corners
        self.stage2_unwarp_and_enhance()
        self.stage3_detect_frets_two_points(fret_result)
        return self.render_and_save(out_prefix)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Few-shot fretboard detection and bounded occlusion interpolation')
    parser.add_argument('image', nargs='?', default='sample_images/new_user_fender_maple.jpg')
    parser.add_argument('--corners-json', help='Cached normalized [y,x] corners')
    parser.add_argument('--frets-json', help='Cached normalized fret response; skips the second API call')
    parser.add_argument('--out-prefix', default='sample_images/integrated_frets')
    args = parser.parse_args()
    def read_json(path):
        if path is None:
            return None
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    os.makedirs(os.path.dirname(os.path.abspath(args.out_prefix)), exist_ok=True)
    pipeline = TwoStageFretPipeline(args.image)
    try:
        return pipeline.run(read_json(args.corners_json), read_json(args.frets_json), args.out_prefix)
    finally:
        with open(args.out_prefix + '_api_calls.json', 'w', encoding='utf-8') as f:
            json.dump(dict(model=pipeline.model, calls=pipeline.api_calls), f, indent=2)



if __name__ == '__main__':
    main()
