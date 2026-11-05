import requests
import json
import base64
import cv2
import os
import numpy as np

API_KEY = 'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw'
MODEL = 'gemini-3-flash-preview'
url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

img_path = 'sample_images/user_test_suhr_maple.png'
img = cv2.imread(img_path)
h, w, _ = img.shape
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
b64_img = base64.b64encode(buf).decode('utf-8')

prompt = """You are a master guitar computer vision engineer and luthier.
Your goal is to detect the playable guitar fretboard boundary [nut_top, body_top, body_bottom, nut_bottom].

Step-by-step verification instructions:
1. Locate the HEADSTOCK (the blue head with tuning pegs/machines on the far right). The NUT is the white bone divider directly touching the headstock at the 0-fret! Even if the guitarist is fretting high frets (12th-14th fret) with his left hand, DO NOT confuse the hand with the nut! The nut is next to the tuning pegs on the far right (x > 550).
2. Locate the LAST FRET WIRE (near the guitar body/pickguard on the left). The line between body_top and body_bottom MUST be on the exact same metal fret wire!
3. Self-Check: Mentally verify that if this quadrilateral is unwarped, the frets would stand naturally vertical (perpendicular to the strings).

Output JSON:
{
  "reasoning": "...short verification check...",
  "nut_top": [y, x],
  "body_top": [y, x],
  "body_bottom": [y, x],
  "nut_bottom": [y, x]
}
Coordinates normalized [0, 1000]."""

payload = {
    'contents': [{'parts': [
        {'text': prompt},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_img}}
    ]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

resp = requests.post(url, json=payload, timeout=25)
print('HTTP Status:', resp.status_code)
if resp.status_code == 200:
    res = resp.json()
    ans = json.loads(res['candidates'][0]['content']['parts'][0]['text'])
    print('Reasoning:', ans.get('reasoning'))
    pts = {}
    for k in ['nut_top', 'body_top', 'body_bottom', 'nut_bottom']:
        y = int(round(ans[k][0]/1000.0 * h))
        x = int(round(ans[k][1]/1000.0 * w))
        pts[k] = (x, y)
        print(f"  {k:12s}: x={x}, y={y}")
        
    # Visualize and save
    vis = img.copy()
    corners = [pts['nut_top'], pts['body_top'], pts['body_bottom'], pts['nut_bottom']]
    poly = np.array(corners, dtype=np.int32)
    cv2.polylines(vis, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    for k, pt in pts.items():
        cv2.circle(vis, pt, 6, (0, 0, 255), -1)
    cv2.imwrite('sample_images/suhr_verified_result.png', vis)
    print('Saved sample_images/suhr_verified_result.png!')
