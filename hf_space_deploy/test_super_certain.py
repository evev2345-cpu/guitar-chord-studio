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

prompt = """You are an expert guitar luthier and computer vision engineer.
Look at this CONTRAST-ENHANCED flattened guitar fretboard.

PRECISION GROUNDING RULES:
1. ONLY pick points on the MOST CERTAIN, CLEARLY VISIBLE segments of each metal fret wire!
2. The distance between p1 and p2 CAN BE CLOSE ENOUGH!
   - They do NOT need to reach the top and bottom edges of the fretboard.
   - Even a short, clean segment (where p1 and p2 are relatively close to each other on a clearly visible part of the wire) is COMPLETELY FINE and encouraged, as long as both points are 100% certainly on that same physical wire!
3. If any fret wire is uncertain, blurry, or covered by the guitarist's hand:
   - DO NOT GUESS!
   - Explicitly mark it as: {"fret_num": N, "occluded": true, "reason": "..."}
4. Slope condition: The line between p1 and p2 must be vertical/steep across the strings:
   - |(y2 - y1) / (x2 - x1)| > 1.
5. Normalized coordinates in [0, 1000]: [y, x].

Return valid JSON:
{
  "frets": [
    {
      "fret_num": 0,
      "occluded": false,
      "p1": [y, x],
      "p2": [y, x]
    },
    {
      "fret_num": 7,
      "occluded": true,
      "reason": "covered by hand"
    }
  ]
}"""

payload = {
    'contents': [{'role': 'user', 'parts': [
        {'text': prompt},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
    ]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

print("🚀 '확실한 구간에만 찍기 + 점 사이 거리 가까워도 됨 + 모르면 모른다고 하기' 실행 중...")

for idx, k in enumerate(API_KEYS):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
    try:
        r = requests.post(url, json=payload, timeout=45)
        if r.status_code == 200:
            data = r.json()
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            with open('sample_images/super_certain_frets.json', 'w', encoding='utf-8') as f:
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
