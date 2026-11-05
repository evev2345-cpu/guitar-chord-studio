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

# 1. Load enhanced image
img = cv2.imread('sample_images/enhanced_color_sharp.png')
h, w, _ = img.shape
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 95])
b64 = base64.b64encode(buf).decode('utf-8')

prompt = """You are an expert guitar luthier and computer vision engineer.
Look at this CONTRAST-ENHANCED flattened guitar fretboard.
The left edge (x=0) is the NUT (0-fret).
The first fret wire (Wire 1) is located at x around 80~100.
IMPORTANT FRET POSITION RULES:
1. Inlay marker dots are located at frets: 3, 5, 7, 9, 12 (double dots), 15, 17, 19, 21!
   - Dot 1 is inside Fret Box 3 (between Wire 2 and Wire 3).
   - Double Dots are inside Fret Box 12 (between Wire 11 and Wire 12).
2. For each REAL METAL FRET WIRE:
   - Identify two clear points on the same metal wire: p1: [y, x] and p2: [y, x] in [0, 1000] scale.
   - Do NOT detect faint shadows inside Fret 1 near the nut!

Return JSON:
{
  "frets": [
    {"fret_num": 1, "p1": [y, x], "p2": [y, x]},
    {"fret_num": 2, "p1": [y, x], "p2": [y, x]}
  ]
}"""

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}, {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

for idx, k in enumerate(API_KEYS):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            with open('sample_images/enhanced_api_frets.json', 'w', encoding='utf-8') as f:
                f.write(data['candidates'][0]['content']['parts'][0]['text'])
            print(f"Success with key {idx}! Saved enhanced_api_frets.json")
            break
        elif r.status_code == 429:
            print(f"Key {idx} 429 Rate limit -> next")
            continue
        else:
            print(f"Key {idx} status {r.status_code}")
    except Exception as e:
        print(f"Key {idx} exception: {e}")
