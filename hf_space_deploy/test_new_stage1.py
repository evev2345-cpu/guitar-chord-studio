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

img = cv2.imread('sample_images/new_user_fender_maple.jpg')
h, w, _ = img.shape
_, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 90])
b64 = base64.b64encode(buf).decode('utf-8')

prompt = """You are an expert guitar computer vision engineer.
Look at this photo.
There is a guitarist sitting and playing a blue electric guitar with a light MAPLE neck and maple fretboard.
(Note: Do NOT detect the white guitar standing on the guitar stand on the right!).

Detect the exact 4 corners of the fretboard of the BLUE GUITAR BEING PLAYED in the guitarist's hands:
1. "nut_top": where the headstock meets the maple fretboard (0-fret) at the top edge (near the low E string / tuning pegs side).
2. "nut_bottom": where the headstock meets the maple fretboard at the bottom edge (near high E string).
3. "body_top": at the EXACT last metal fret wire near the body/pickguard at the top edge (low E string).
4. "body_bottom": at the SAME last metal fret wire at the bottom edge (high E string).

Return valid JSON with normalized [y, x] in [0, 1000]:
{
  "reasoning": "...step by step identification of the blue guitar's nut and last fret...",
  "nut_top": [y, x],
  "body_top": [y, x],
  "body_bottom": [y, x],
  "nut_bottom": [y, x]
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
            raw_text = data['candidates'][0]['content']['parts'][0]['text']
            print("API Success!")
            print("Token usage:", data.get('usageMetadata'))
            with open('sample_images/new_guitar_corners.json', 'w', encoding='utf-8') as f:
                f.write(raw_text)
            break
        elif r.status_code == 429:
            print(f"Key {idx} 429 -> next")
            continue
        else:
            print(f"Key {idx} status {r.status_code}")
    except Exception as e:
        print(f"Key {idx} error: {e}")
