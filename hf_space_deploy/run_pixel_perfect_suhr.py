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

def detect_pixel_perfect(img_name):
    img_path = os.path.join('sample_images', img_name)
    img = cv2.imread(img_path)
    if img is None:
        print("Image load error")
        return None
    h, w, _ = img.shape

    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
    b64_img = base64.b64encode(buf).decode('utf-8')

    prompt = f"""You are a master guitar computer vision engineer and luthier.
Target Image dimensions: width={w}, height={h} (exact pixel coordinates).

Detect the 4 corners of the playable guitar fretboard:
1. "nut_top": Top corner of the nut (boundary between headstock/tuning pegs and fretboard, low E 6th string side).
   - CRITICAL: The headstock is on the far right (x ≈ 580~600). The nut is at the headstock boundary, NOT near the player's fretting hand!
2. "last_fret_top": Top end of the 22nd / final metal fret wire (near the guitar body/pickguard, low E 6th string side).
3. "last_fret_bottom": Bottom end of the 22nd / final metal fret wire (high E 1st string side).
   - CRITICAL: "last_fret_top" and "last_fret_bottom" MUST be on the exact same continuous metal fret wire!
4. "nut_bottom": Bottom corner of the nut (boundary between headstock and fretboard, high E 1st string side).

Self-Verification: Mentally verify that if these 4 corners are unwarped, the frets stand naturally vertical (perpendicular to strings at 90 degrees).

Return the EXACT PIXEL COORDINATES (x: 0..{w}, y: 0..{h}) as JSON:
```json
{{
  "reasoning": "...step by step check...",
  "nut_top": {{"x": int, "y": int}},
  "last_fret_top": {{"x": int, "y": int}},
  "last_fret_bottom": {{"x": int, "y": int}},
  "nut_bottom": {{"x": int, "y": int}}
}}
```
Return ONLY valid JSON."""

    payload = {
        'contents': [{'parts': [
            {'text': prompt},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_img}}
        ]}],
        'generationConfig': {'response_mime_type': 'application/json'}
    }

    res_data = None
    for k_idx, key in enumerate(API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
        try:
            resp = requests.post(url, json=payload, timeout=25)
            if resp.status_code == 200:
                res_data = resp.json()
                break
            elif resp.status_code == 429:
                print(f"Key {k_idx} 429 Rate Limit -> Next key")
                continue
        except Exception as e:
            print(f"Key {k_idx} error: {e}")

    if res_data is None:
        print("API call failed")
        return None

    raw_text = res_data['candidates'][0]['content']['parts'][0]['text']
    data = json.loads(raw_text)
    print("Reasoning:", data.get('reasoning'))
    
    pts = {
        'nut_top': (int(data['nut_top']['x']), int(data['nut_top']['y'])),
        'last_fret_top': (int(data['last_fret_top']['x']), int(data['last_fret_top']['y'])),
        'last_fret_bottom': (int(data['last_fret_bottom']['x']), int(data['last_fret_bottom']['y'])),
        'nut_bottom': (int(data['nut_bottom']['x']), int(data['nut_bottom']['y']))
    }

    print("\n[Exact Detected Pixels]:")
    for k, v in pts.items():
        print(f"  {k:16s}: {v}")

    # Visualization
    vis = img.copy()
    corners = np.array([
        pts['nut_top'],
        pts['last_fret_top'],
        pts['last_fret_bottom'],
        pts['nut_bottom']
    ], dtype=np.int32)

    cv2.polylines(vis, [corners], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["NutTop", "LastFretTop", "LastFretBot", "NutBot"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(corners):
        px, py = int(pt[0]), int(pt[1])
        cv2.circle(vis, (px, py), 6, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_det = "sample_images/suhr_pixel_perfect_detected.png"
    cv2.imwrite(out_det, vis)

    # Flat unwarping (800x150)
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = corners.astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(img, M, (CANVAS_W, CANVAS_H))
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)

    out_flat = "sample_images/suhr_pixel_perfect_flat.png"
    cv2.imwrite(out_flat, flat)

    print(f"\nSaved detected image: {out_det}")
    print(f"Saved flat image: {out_flat}")
    return pts

if __name__ == '__main__':
    detect_pixel_perfect('user_test_suhr_maple.png')
