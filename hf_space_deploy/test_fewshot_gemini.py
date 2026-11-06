import requests
import json
import base64
import cv2
import os
import numpy as np

API_KEY = 'AQ.Ab8RN6KNQRxgDsUHDKKyZ8WOel6-G1vzuMzHv25tv68RsUUiLw'
MODEL = 'gemini-3-flash-preview'
url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"

def encode_img(name, max_dim=800):
    img = cv2.imread(os.path.join('sample_images', name))
    h, w, _ = img.shape
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        img = cv2.resize(img, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode('utf-8'), h, w

# 1. Example 1: 1051_5605_0000.jpg
b64_ex1, h1, w1 = encode_img('1051_5605_0000.jpg')
with open('dataset/labels/1051_5605_0000.json') as f:
    gt1 = json.load(f)
pts1 = {c['name']: [int(round(c['y']/h1*1000)), int(round(c['x']/w1*1000))] for c in gt1['corners']}

# 2. Example 2: 2015111201921_0.jpg
b64_ex2, h2, w2 = encode_img('2015111201921_0.jpg')
with open('dataset/labels/2015111201921_0.json') as f:
    gt2 = json.load(f)
pts2 = {c['name']: [int(round(c['y']/h2*1000)), int(round(c['x']/w2*1000))] for c in gt2['corners']}

# 3. Target: images (2).jpg
target_name = 'images (2).jpg'
b64_target, ht, wt = encode_img(target_name)

prompt_intro = """You are a master guitar computer vision specialist.
Here are two GROUND TRUTH expert examples annotated by a human guitar luthier:
Notice how the 4 corners are strictly defined:
- "nut_top": Nut corner at low E 6th string
- "body_top": Last fret corner at low E 6th string
- "body_bottom": Last fret corner at high E 1st string
- "nut_bottom": Nut corner at high E 1st string
Coordinates are [y, x] in [0, 1000] scale. Observe carefully how the human annotator marks the fretboard even when fingers or hands are present."""

contents = [
    {'role': 'user', 'parts': [
        {'text': prompt_intro + '\n\nExample 1 Image:'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_ex1}}
    ]},
    {'role': 'model', 'parts': [
        {'text': json.dumps(pts1)}
    ]},
    {'role': 'user', 'parts': [
        {'text': 'Example 2 Image:'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_ex2}}
    ]},
    {'role': 'model', 'parts': [
        {'text': json.dumps(pts2)}
    ]},
    {'role': 'user', 'parts': [
        {'text': 'Now, following the exact same annotation rules, standard, and precision as Example 1 and Example 2, detect the 4 corners for this Target Image. Return JSON only.'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
    ]}
]

payload = {
    'contents': contents,
    'generationConfig': {'response_mime_type': 'application/json'}
}

resp = requests.post(url, json=payload, timeout=25)
print('HTTP Status:', resp.status_code)
if resp.status_code == 200:
    res = resp.json()
    coords = json.loads(res['candidates'][0]['content']['parts'][0]['text'])
    print('\nFew-Shot In-Context Gemini Response:', coords)

    with open(f'dataset/labels/{os.path.splitext(target_name)[0]}.json') as f:
        gt_target = json.load(f)

    print(f"\n[{target_name}] Human Ground Truth vs Few-Shot AI:")
    total_err = 0
    for c in gt_target['corners']:
        name = c['name']
        pred = coords.get(name)
        if pred:
            pred_y = int(round(pred[0]/1000.0 * ht))
            pred_x = int(round(pred[1]/1000.0 * wt))
            err_px = np.hypot(pred_x - c['x'], pred_y - c['y'])
            total_err += err_px
            print(f"  {name:12s} | GT: ({c['x']}, {c['y']}) -> AI: ({pred_x}, {pred_y}) | Error: {err_px:.1f}px")

    print(f"\n★ AVERAGE PIXEL ERROR: {total_err / 4.0:.1f} px (Resolution: {wt}x{ht})")
