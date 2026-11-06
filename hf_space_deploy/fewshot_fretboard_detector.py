import requests
import json
import base64
import cv2
import os
import sys
import numpy as np

# 3개의 API 키 자동 로테이션 및 페일오버 지원
API_KEYS = [
    'AQ.Ab8RN6IhY-wilaMIFRCmulAID2dziMh-0k2hatsTivUaIV-WIw',
    'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw',
    'AQ.Ab8RN6L2t1qF0iR-U_XDmsHoOwo3UU4EVkf9dtW1CvkUY4JL-A'
]
MODEL = 'gemini-3-flash-preview'

def encode_image(img_path, max_dim=800):
    img = cv2.imread(img_path)
    if img is None:
        return None, 0, 0, None
    h, w, _ = img.shape
    resized = img
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        resized = cv2.resize(img, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    b64_str = base64.b64encode(buf).decode('utf-8')
    return b64_str, h, w, img

def load_ground_truth(json_path, h, w):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    pts = {}
    for c in data['corners']:
        name = c['name']
        norm_y = int(round(c['y'] / h * 1000.0))
        norm_x = int(round(c['x'] / w * 1000.0))
        pts[name] = [norm_y, norm_x]
    return pts, data['corners']

def auto_verticalize_frets(flat_img):
    # 평면화된 지판에서 프렛들이 정확히 90도(수직)로 서도록 전단 변형(Shear) 자동 교정
    h, w, _ = flat_img.shape
    gray = cv2.cvtColor(flat_img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=25, maxLineGap=6)
    if lines is None:
        return flat_img

    dx_list, dy_list = [], []
    for l in lines:
        x1, y1, x2, y2 = l[0]
        deg = np.degrees(np.arctan2(y2-y1, x2-x1)) % 180
        if 65 < deg < 115:
            if y2 < y1:
                x1, y1, x2, y2 = x2, y2, x1, y1
            dx_list.append(x2 - x1)
            dy_list.append(y2 - y1)

    if len(dx_list) < 2:
        return flat_img

    median_dx = np.median(dx_list)
    median_dy = np.median(dy_list)
    if abs(median_dy) < 1e-5:
        return flat_img

    shear = - (median_dx / median_dy)
    M_shear = np.array([
        [1.0, shear, -shear * (h / 2.0)],
        [0.0, 1.0, 0.0]
    ], dtype=np.float32)

    corrected = cv2.warpAffine(flat_img, M_shear, (w, h), borderMode=cv2.BORDER_REPLICATE)
    return corrected

def detect_fretboard_fewshot(target_img_name, exemplar_names=None, output_dir="sample_images/fewshot_results"):
    os.makedirs(output_dir, exist_ok=True)
    target_path = os.path.join('sample_images', target_img_name)
    b64_target, th, tw, target_img = encode_image(target_path)
    if b64_target is None:
        print(f"[{target_img_name}] 이미지 로드 실패")
        return None

    # 모범 예시 선정 (기본 2장: 각도가 명확한 라벨)
    if exemplar_names is None:
        candidates = ['1051_5605_0000.jpg', '2015111201921_0.jpg', '1347539285769.jpg']
        exemplar_names = [c for c in candidates if c != target_img_name][:2]

    # Few-Shot 컨텐츠 빌드
    prompt_intro = """You are a master guitar luthier and precision computer vision annotator.
Here are verified HUMAN GROUND TRUTH examples showing the exact expert standard for guitar fretboard corners:
- "nut_top": Top corner of the nut (0-fret boundary line, low E 6th string side).
- "body_top": Top corner of the fretboard at the last fret (low E 6th string side).
- "body_bottom": Bottom corner of the fretboard at the last fret (high E 1st string side).
- "nut_bottom": Bottom corner of the nut (0-fret boundary line, high E 1st string side).
Coordinates are normalized [y, x] in [0, 1000] scale. Observe carefully how the human annotator marks the fretboard boundaries even with hand occlusion or complex backgrounds."""

    contents = []
    # 1. 시스템 인트로 및 예시 1
    ex1_name = exemplar_names[0]
    ex1_path = os.path.join('sample_images', ex1_name)
    ex1_json = os.path.join('dataset/labels', f"{os.path.splitext(ex1_name)[0]}.json")
    b64_ex1, h1, w1, _ = encode_image(ex1_path)
    pts1, _ = load_ground_truth(ex1_json, h1, w1)

    contents.append({'role': 'user', 'parts': [
        {'text': prompt_intro + f'\n\n[Human Expert Example 1: {ex1_name}]'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_ex1}}
    ]})
    contents.append({'role': 'model', 'parts': [
        {'text': json.dumps(pts1)}
    ]})

    # 2. 예시 2
    if len(exemplar_names) > 1:
        ex2_name = exemplar_names[1]
        ex2_path = os.path.join('sample_images', ex2_name)
        ex2_json = os.path.join('dataset/labels', f"{os.path.splitext(ex2_name)[0]}.json")
        b64_ex2, h2, w2, _ = encode_image(ex2_path)
        pts2, _ = load_ground_truth(ex2_json, h2, w2)

        contents.append({'role': 'user', 'parts': [
            {'text': f'[Human Expert Example 2: {ex2_name}]'},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_ex2}}
        ]})
        contents.append({'role': 'model', 'parts': [
            {'text': json.dumps(pts2)}
        ]})

    # 3. 타겟 쿼리
    contents.append({'role': 'user', 'parts': [
        {'text': f'Now, analyze this new Target Image and extract the exact 4 corners following the identical human expert standard. Output JSON only:\n{{"nut_top": [y, x], "body_top": [y, x], "body_bottom": [y, x], "nut_bottom": [y, x]}}'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
    ]})

    payload = {
        'contents': contents,
        'generationConfig': {'response_mime_type': 'application/json'}
    }

    # API 호출 (3개 키 자동 순환)
    resp_json = None
    for k_idx, key in enumerate(API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                resp_json = resp.json()
                break
            elif resp.status_code == 429:
                print(f"  [Key {k_idx}] 429 Rate Limit -> 다음 키로 자동 전환")
                continue
            else:
                print(f"  [Key {k_idx}] HTTP {resp.status_code}")
        except Exception as e:
            print(f"  [Key {k_idx}] 호출 예외: {e}")

    if resp_json is None:
        print(f"[{target_img_name}] 모든 API 키 호출 실패")
        return None

    raw_text = resp_json['candidates'][0]['content']['parts'][0]['text']
    coords = json.loads(raw_text)

    # 픽셀 좌표 복원
    pts = {}
    for name in ["nut_top", "body_top", "body_bottom", "nut_bottom"]:
        val = coords.get(name)
        if val is None:
            # 대체 키 탐색
            for k in coords:
                if name.replace('_', '') in k.replace('_', ''):
                    val = coords[k]
                    break
        if val is not None:
            py = int(round(val[0] / 1000.0 * th))
            px = int(round(val[1] / 1000.0 * tw))
            pts[name] = (px, py)
        else:
            pts[name] = (0, 0)

    # 4점 배열
    ordered_corners = np.array([
        pts["nut_top"],
        pts["body_top"],
        pts["body_bottom"],
        pts["nut_bottom"]
    ], dtype=np.float32)

    # Ground Truth 비교
    target_json = os.path.join('dataset/labels', f"{os.path.splitext(target_img_name)[0]}.json")
    err = None
    if os.path.exists(target_json):
        with open(target_json, 'r', encoding='utf-8') as f:
            gt_data = json.load(f)
        gt_pts = np.array([[c['x'], c['y']] for c in gt_data['corners']], dtype=np.float32)
        err = np.mean(np.linalg.norm(ordered_corners - gt_pts, axis=1))

    # 시각화 저장
    vis = target_img.copy()
    poly = ordered_corners.astype(np.int32)
    cv2.polylines(vis, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["NutTop", "BodyTop", "BodyBot", "NutBot"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(ordered_corners):
        px, py = int(pt[0]), int(pt[1])
        cv2.circle(vis, (px, py), 6, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_vis_path = os.path.join(output_dir, f"fewshot_{target_img_name}")
    cv2.imwrite(out_vis_path, vis)

    # 평면화 (Warp Perspective)
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(ordered_corners, dst)
    flat = cv2.warpPerspective(target_img, M, (CANVAS_W, CANVAS_H))
    
    # [★ 핵심] 프렛 수직화 자동 보정 (90.0도 정렬)
    flat = auto_verticalize_frets(flat)

    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
    out_flat_path = os.path.join(output_dir, f"fewshot_flat_{target_img_name}")
    cv2.imwrite(out_flat_path, flat)

    if err is not None:
        print(f"[{target_img_name}] 검출 완료! 오차: {err:.1f}px (저장: {out_vis_path})")
    else:
        print(f"[{target_img_name}] 검출 완료! (저장: {out_vis_path})")
    return err, ordered_corners, pts

if __name__ == '__main__':
    # 테스트할 이미지
    target = 'images (2).jpg'
    if len(sys.argv) > 1:
        target = sys.argv[1]
    detect_fretboard_fewshot(target)
