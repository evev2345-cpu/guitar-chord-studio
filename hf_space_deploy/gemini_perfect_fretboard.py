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
MODEL = 'gemini-3-flash-preview'

def detect_with_gemini(img_name, key_idx=0):
    api_key = API_KEYS[key_idx % len(API_KEYS)]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={api_key}"
    
    img_path = os.path.join('sample_images', img_name)
    img = cv2.imread(img_path)
    if img is None:
        return None
    h, w, _ = img.shape
    
    scale = 1.0
    upload_img = img
    if max(h, w) > 1280:
        scale = 1280.0 / max(h, w)
        upload_img = cv2.resize(img, (int(w * scale), int(h * scale)))
    
    _, buf = cv2.imencode('.jpg', upload_img, [cv2.IMWRITE_JPEG_QUALITY, 92])
    b64_img = base64.b64encode(buf).decode('utf-8')

    prompt = """You are an expert guitar luthier and precision computer vision annotator.
Your goal is to detect the playable guitar fretboard boundary defined strictly between the NUT and the LAST METAL FRET WIRE:

1. "nut_top": Top corner of the nut (0-fret boundary line between headstock and fretboard, low E 6th string side).
2. "last_fret_top": Top end of the HIGHEST / LAST visible metal fret wire (near the guitar body, low E 6th string side).
   - CRITICAL: Do NOT pick the neck-body joint (14th/16th fret).
   - CRITICAL: Do NOT pick the bare wood edge overhang.
   - Pick the exact metal line of the final fret wire (usually fret 21, 22, or 24).
3. "last_fret_bottom": Bottom end of the HIGHEST / LAST visible metal fret wire (high E 1st string side).
4. "nut_bottom": Bottom corner of the nut (0-fret boundary line, high E 1st string side).

Return 2D normalized integer coordinates [y, x] in [0, 1000] scale:
```json
{
  "nut_top": [y, x],
  "last_fret_top": [y, x],
  "last_fret_bottom": [y, x],
  "nut_bottom": [y, x]
}
```
Return ONLY valid JSON."""

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
        resp = requests.post(url, json=payload, timeout=25)
        if resp.status_code != 200:
            print(f"[{img_name}] HTTP {resp.status_code}: {resp.text[:150]}")
            return None
        res = resp.json()
        raw = res['candidates'][0]['content']['parts'][0]['text']
        coords = json.loads(raw)
    except Exception as e:
        print(f"[{img_name}] API call failed: {e}")
        return None

    # Handle key naming variants
    nut_top_k = "nut_top"
    nut_bot_k = "nut_bottom"
    body_top_k = "last_fret_top" if "last_fret_top" in coords else "body_top"
    body_bot_k = "last_fret_bottom" if "last_fret_bottom" in coords else "body_bottom"
    
    pts = {}
    for standard_name, key_name in [
        ("nut_top", nut_top_k),
        ("body_top", body_top_k),
        ("body_bottom", body_bot_k),
        ("nut_bottom", nut_bot_k)
    ]:
        norm_y, norm_x = coords[key_name]
        px = int(round(norm_x / 1000.0 * w))
        py = int(round(norm_y / 1000.0 * h))
        pts[standard_name] = (px, py)
        
    return pts, img

def evaluate_image(img_name):
    res = detect_with_gemini(img_name)
    if res is None:
        return
    pts, img = res
    h, w, _ = img.shape
    
    corners = np.array([
        pts["nut_top"],
        pts["body_top"],
        pts["body_bottom"],
        pts["nut_bottom"]
    ], dtype=np.float32)

    # Compare with GT
    gt_file = os.path.join('dataset/labels', f"{os.path.splitext(img_name)[0]}.json")
    err = None
    if os.path.exists(gt_file):
        with open(gt_file) as f:
            gt_data = json.load(f)
        gt_pts = np.array([[c['x'], c['y']] for c in gt_data['corners']], dtype=np.float32)
        err = np.mean(np.linalg.norm(corners - gt_pts, axis=1))

    print(f"\n[{img_name}]")
    print(f"  Nut Top       : {pts['nut_top']}")
    print(f"  Last Fret Top : {pts['body_top']}")
    print(f"  Last Fret Bot : {pts['body_bottom']}")
    print(f"  Nut Bottom    : {pts['nut_bottom']}")
    if err is not None:
        print(f"  ★ 오차: {err:.1f} px (전체 {w}x{h})")

    # Visualization
    vis = img.copy()
    poly = corners.astype(np.int32)
    cv2.polylines(vis, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["NutTop", "LastFretTop", "LastFretBot", "NutBot"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(corners):
        px, py = int(pt[0]), int(pt[1])
        cv2.circle(vis, (px, py), 6, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    os.makedirs('sample_images/refined_results', exist_ok=True)
    out_vis = f"sample_images/refined_results/refined_{img_name}"
    cv2.imwrite(out_vis, vis)

    # Flat unwarping (800x150)
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    M = cv2.getPerspectiveTransform(corners, dst)
    flat = cv2.warpPerspective(img, M, (CANVAS_W, CANVAS_H))
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
    out_flat = f"sample_images/refined_results/refined_flat_{img_name}"
    cv2.imwrite(out_flat, flat)
    print(f"  -> 검출 이미지 저장: {out_vis}")
    print(f"  -> 평면화 이미지 저장: {out_flat}")

if __name__ == '__main__':
    for name in ['images (2).jpg', '1051_5603_0000.jpg', '1051_5605_0000.jpg', '2015111201921_0.jpg']:
        evaluate_image(name)
