import cv2
import json
import base64
import requests

API_KEYS = [
    'AQ.Ab8RN6IhY-wilaMIFRCmulAID2dziMh-0k2hatsTivUaIV-WIw',
    'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw',
    'AQ.Ab8RN6L2t1qF0iR-U_XDmsHoOwo3UU4EVkf9dtW1CvkUY4JL-A'
]
MODEL = 'gemini-3-flash-preview'

target_path = 'sample_images/fender_bw_super_contrast.png'
img = cv2.imread(target_path)
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
b64_target = base64.b64encode(buf).decode('utf-8')

b64_exemplar = None
with open('sample_images/user_fret_b64.txt', 'r') as f:
    b64_exemplar = f.read().strip()

prompt = """You are an expert guitar luthier and computer vision engineer.
Look at this CONTRAST-ENHANCED flattened guitar fretboard.
Notice that the guitarist's LEFT HAND is pressing on the fretboard around frets 6~9!

CRITICAL HONESTY & OCCLUSION RULES:
1. ONLY detect fret wires where you are 100% CERTAIN of the physical metal wire.
2. If a fret wire is completely or mostly COVERED by the guitarist's hand/fingers, DO NOT GUESS OR HALLUCINATE!
   - Mark it explicitly with: {"fret_num": N, "occluded": true, "reason": "covered by hand"}
   - Or if only a small segment (e.g. at the top or bottom of the hand) is visible, you may note it, but if uncertain, mark "occluded": true.
3. For all clearly VISIBLE frets:
   - Provide two certain points on that wire: p1: [y, x] and p2: [y, x] in [0, 1000] scale.
   - Must satisfy slope |(y2 - y1) / (x2 - x1)| > 1.

Return valid JSON:
{
  "frets": [
    {"fret_num": 1, "occluded": false, "p1": [y, x], "p2": [y, x]},
    {"fret_num": 7, "occluded": true, "reason": "covered by hand"}
  ]
}"""

payload = {
    'contents': [{'role': 'user', 'parts': [
        {'text': prompt},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
    ]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

print("🚀 '모르면 모른다고 해라 (Occlusion Aware)' 프롬프트 테스트 시작...")

for idx, k in enumerate(API_KEYS):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if r.status_code == 200:
            data = r.json()
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            with open('sample_images/occlusion_aware_frets.json', 'w', encoding='utf-8') as f:
                f.write(raw_text)
            print(f"✅ Key {idx} 호출 성공!")
            print(raw_text[:600] + "...")
            break
        elif r.status_code == 429:
            print(f"Key {idx} 429 -> next")
            continue
        else:
            print(f"Key {idx} status {r.status_code}")
    except Exception as e:
        print(f"Key {idx} error: {e}")
