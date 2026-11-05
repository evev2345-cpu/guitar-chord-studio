import requests
import json
import base64
import cv2
import os
import numpy as np

API_KEYS = [
    'AQ.Ab8RN6IhY-wilaMIFRCmulAID2dziMh-0k2hatsTivUaIV-WIw',
    'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw',
    'AQ.Ab8RN6L2t1qF0iR-U_XDmsHoOwo3UU4EVkf9dtW1CvkUY4JL-A'
]

def detect_fretboard_with_gemini(img_name, key_idx=0):
    api_key = API_KEYS[key_idx % len(API_KEYS)]
    model = 'gemini-3.5-flash'
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"

    img_path = os.path.join('sample_images', img_name)
    img = cv2.imread(img_path)
    if img is None:
        return None, None
    h, w, _ = img.shape
    _, buf = cv2.imencode('.jpg', img)
    b64_img = base64.b64encode(buf).decode('utf-8')

    prompt = f"""You are an expert guitar luthier and computer vision annotator.
Identify the guitar fretboard (fingerboard) in the image.
Detect the exact 4 corners of the fretboard:
1. "nut_top": The top corner of the nut (0-fret boundary between headstock and neck, low E string side).
2. "body_top": The top corner of the fretboard where it meets the guitar body / last fret (fret 19-24).
3. "body_bottom": The bottom corner of the fretboard where it meets the guitar body / last fret (high E string side).
4. "nut_bottom": The bottom corner of the nut (0-fret boundary, high E string side).

Image dimensions: height={h}, width={w}.
Return the pixel coordinates [y, x] for each corner in JSON format:
{{
  "nut_top": [y, x],
  "body_top": [y, x],
  "body_bottom": [y, x],
  "nut_bottom": [y, x]
}}
Ensure the points strictly mark the fretboard boundaries, not headstock or body."""

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inline_data": {"mime_type": "image/jpeg", "data": b64_img}}
            ]
        }],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }

    try:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code != 200:
            print(f"[{img_name}] HTTP {resp.status_code}: {resp.text[:200]}")
            return None, img
        data = resp.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        coords = json.loads(raw_text)
        return coords, img
    except Exception as e:
        print(f"[{img_name}] Error with key {key_idx}: {e}")
        return None, img

def evaluate_and_visualize(img_name, key_idx=0):
    coords, img = detect_fretboard_with_gemini(img_name, key_idx)
    if coords is None:
        return
    h, w, _ = img.shape

    # Parse detected points: [nut_top, body_top, body_bottom, nut_bottom]
    det_pts = np.array([
        [coords['nut_top'][1], coords['nut_top'][0]],
        [coords['body_top'][1], coords['body_top'][0]],
        [coords['body_bottom'][1], coords['body_bottom'][0]],
        [coords['nut_bottom'][1], coords['nut_bottom'][0]]
    ], dtype=np.float32)

    # Compare with GT
    gt_file = os.path.join('dataset/labels', f"{os.path.splitext(img_name)[0]}.json")
    err = None
    if os.path.exists(gt_file):
        with open(gt_file) as f:
            gt_data = json.load(f)
        gt_pts = np.array([[c['x'], c['y']] for c in gt_data['corners']], dtype=np.float32)
        err = np.mean(np.linalg.norm(det_pts - gt_pts, axis=1))

    print(f"\n==========================================")
    print(f"[{img_name}] Gemini 2.5 Flash Detection:")
    print(f"  nut_top    : (x={det_pts[0][0]:.1f}, y={det_pts[0][1]:.1f})")
    print(f"  body_top   : (x={det_pts[1][0]:.1f}, y={det_pts[1][1]:.1f})")
    print(f"  body_bottom: (x={det_pts[2][0]:.1f}, y={det_pts[2][1]:.1f})")
    print(f"  nut_bottom : (x={det_pts[3][0]:.1f}, y={det_pts[3][1]:.1f})")
    if err is not None:
        print(f"  ★ GT 대비 평균 픽셀 오차: {err:.1f} px (전체 해상도: {w}x{h})")
    print(f"==========================================")

    # Save visualization
    vis = img.copy()
    poly = det_pts.astype(np.int32)
    cv2.polylines(vis, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["NutTop", "BodyTop", "BodyBot", "NutBot"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(det_pts):
        px, py = int(round(pt[0])), int(round(pt[1]))
        cv2.circle(vis, (px, py), 5, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    os.makedirs('sample_images/gemini_results', exist_ok=True)
    out_path = f"sample_images/gemini_results/gemini_{img_name}"
    cv2.imwrite(out_path, vis)

    # Warp flat fretboard
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(det_pts, dst)
    flat = cv2.warpPerspective(img, M, (CANVAS_W, CANVAS_H))
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
    cv2.imwrite(f"sample_images/gemini_results/gemini_flat_{img_name}", flat)
    print(f"  -> 결과 이미지 저장 완료: {out_path}")

if __name__ == '__main__':
    evaluate_and_visualize('images (2).jpg')
    evaluate_and_visualize('1051_5603_0000.jpg')
