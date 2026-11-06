import cv2
import json
import base64
import requests
import numpy as np
import shutil

API_KEYS = [
    'AQ.Ab8RN6IhY-wilaMIFRCmulAID2dziMh-0k2hatsTivUaIV-WIw',
    'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw',
    'AQ.Ab8RN6L2t1qF0iR-U_XDmsHoOwo3UU4EVkf9dtW1CvkUY4JL-A'
]
MODEL = 'gemini-3-flash-preview'

img = cv2.imread('sample_images/new_fender_flat_enhanced.png')
h, w, _ = img.shape
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 92])
b64 = base64.b64encode(buf).decode('utf-8')

prompt = """You are an expert guitar luthier and computer vision model.
Look at this CONTRAST-ENHANCED flattened rectangular guitar fretboard.
Frets are straight metal wires running vertically across the strings from top to bottom.

CRITICAL RULES:
1. Do NOT mistake faint shadows, wood grain, or lighting artifacts for frets!
2. Only detect ACTUAL, REAL CONTINUOUS METAL FRET WIRES.
3. The left edge (x=0) is the NUT line. Fret 1 is the large box right next to the nut!
4. Fret wires start from Wire 1 (near x~70-90) and progress to the final fret wire near x~780-800.

Your task: For every visible real metal fret wire (ordered from nut towards the body):
Identify TWO CERTAIN, UNAMBIGUOUS points on that same metal fret wire (points clearly visible on the wire).

Return a JSON list of frets:
{
  "frets": [
    {
      "fret_num": 1,
      "p1": [y, x],
      "p2": [y, x]
    }
  ]
}

Coordinates must be in normalized [0, 1000] scale: [y, x].
For each fret, p1 and p2 must be two distinct points on the SAME fret wire."""

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}, {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

for idx, k in enumerate(API_KEYS):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200:
            data = r.json()
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            with open('sample_images/new_fender_frets.json', 'w', encoding='utf-8') as f:
                f.write(raw_text)
            print(f"2nd API Success with Key {idx}!")
            print("Usage:", data.get('usageMetadata'))
            break
        elif r.status_code == 429:
            print(f"Key {idx} 429 -> next")
            continue
        else:
            print(f"Key {idx} status {r.status_code}")
    except Exception as e:
        print(f"Key {idx} error: {e}")
