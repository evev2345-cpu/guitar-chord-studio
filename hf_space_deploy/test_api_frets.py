import requests
import json
import base64
import cv2

API_KEYS = [
    'AQ.Ab8RN6IhY-wilaMIFRCmulAID2dziMh-0k2hatsTivUaIV-WIw',
    'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw',
    'AQ.Ab8RN6L2t1qF0iR-U_XDmsHoOwo3UU4EVkf9dtW1CvkUY4JL-A'
]
MODEL = 'gemini-3-flash-preview'

img = cv2.imread('sample_images/user_test_suhr_maple.png')
h, w, _ = img.shape
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
b64 = base64.b64encode(buf).decode('utf-8')

prompt = """You are an expert guitar luthier and computer vision model.
Look at the electric guitar neck in this image.
Identify all visible fret wires (from the headstock nut to the last fret near the body).
For each fret wire, identify its top endpoint (near the low E string / top edge) and bottom endpoint (near the high E string / bottom edge) in [0, 1000] normalized scale [y, x].

Return a JSON list of frets, ordered from nut (fret 0) towards the body:
{
  "frets": [
    {"fret_num": 0, "label": "nut", "top": [y, x], "bottom": [y, x]},
    {"fret_num": 1, "top": [y, x], "bottom": [y, x]}
  ]
}"""

payload = {
    'contents': [{'role': 'user', 'parts': [{'text': prompt}, {'inline_data': {'mime_type': 'image/jpeg', 'data': b64}}]}],
    'generationConfig': {'response_mime_type': 'application/json'}
}

for k in API_KEYS:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={k}"
    try:
        r = requests.post(url, json=payload, timeout=30)
        if r.status_code == 200:
            data = r.json()
            text = data['candidates'][0]['content']['parts'][0]['text']
            print('Token Usage:', data.get('usageMetadata'))
            with open('sample_images/api_frets_test.json', 'w', encoding='utf-8') as f:
                f.write(text)
            print('Success! Saved api_frets_test.json')
            break
        else:
            print(f'Status {r.status_code}: {r.text[:100]}')
    except Exception as e:
        print(f'Exception: {e}')
