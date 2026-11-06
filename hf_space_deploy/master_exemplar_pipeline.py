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

def encode_img(path, max_dim=800):
    img = cv2.imread(path)
    if img is None:
        return None, 0, 0
    h, w, _ = img.shape
    resized = img
    if max(h, w) > max_dim:
        scale = max_dim / max(h, w)
        resized = cv2.resize(img, (int(w * scale), int(h * scale)))
    _, buf = cv2.imencode('.jpg', resized, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf).decode('utf-8'), h, w

def build_exemplar_pair(img_name):
    raw_path = os.path.join('sample_images', img_name)
    flat_path = os.path.join('dataset/unwarped', f"flat_{img_name}")
    json_path = os.path.join('dataset/labels', f"{os.path.splitext(img_name)[0]}.json")

    b64_raw, rh, rw = encode_img(raw_path)
    b64_flat, fh, fw = encode_img(flat_path)

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 0..1000 normalized coordinates
    norm_pts = {}
    for c in data['corners']:
        ny = int(round(c['y'] / rh * 1000.0))
        nx = int(round(c['x'] / rw * 1000.0))
        norm_pts[c['name']] = [ny, nx]

    return b64_raw, b64_flat, norm_pts, rh, rw

def run_master_pipeline(target_name):
    target_path = os.path.join('sample_images', target_name)
    b64_target, th, tw = encode_img(target_path)
    target_img = cv2.imread(target_path)

    # 1. 유저의 모범 답안 2세트 (원본 사진 + 유저가 펼친 지판 사진 + 유저의 4점 좌표)
    ex1_raw, ex1_flat, ex1_pts, _, _ = build_exemplar_pair('1051_5605_0000.jpg')
    ex2_raw, ex2_flat, ex2_pts, _, _ = build_exemplar_pair('2015111201921_0.jpg')

    prompt_intro = """You are a master guitar computer vision engineer and luthier.
Study the provided HUMAN GROUND TRUTH PAIRS:
For each example, you see:
1. The original perspective photo of the guitar.
2. The user's annotated 4 corners [nut_top, body_top, body_bottom, nut_bottom] in [0, 1000] normalized scale.
3. The resulting UNWARPED FLATTENED FRETBOARD: Notice that when the 4 points are accurately placed on the true nut and true last fret wire, the unwarped fretboard has perfectly vertical frets (perpendicular to horizontal strings)."""

    contents = [
        # Pair 1
        {'role': 'user', 'parts': [
            {'text': prompt_intro + '\n\n[Human Ground Truth Example 1: Original Perspective Photo]'},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': ex1_raw}},
            {'text': '[Example 1: Resulting Unwarped Flattened Fretboard]'},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': ex1_flat}}
        ]},
        {'role': 'model', 'parts': [
            {'text': json.dumps({
                "reasoning": "The 4 corners align with the nut line and the last fret line, so the flattened fretboard has clean horizontal strings and vertical frets.",
                **ex1_pts
            })}
        ]},
        # Pair 2
        {'role': 'user', 'parts': [
            {'text': '[Human Ground Truth Example 2: Original Perspective Photo]'},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': ex2_raw}},
            {'text': '[Example 2: Resulting Unwarped Flattened Fretboard]'},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': ex2_flat}}
        ]},
        {'role': 'model', 'parts': [
            {'text': json.dumps({
                "reasoning": "Nut boundaries and last fret boundaries correctly matched, producing an undistorted rectangular fretboard.",
                **ex2_pts
            })}
        ]},
        # Target Query with Self-Verification
        {'role': 'user', 'parts': [
            {'text': """Now examine this Target Image.
Detect the exact 4 corners [nut_top, body_top, body_bottom, nut_bottom] in [0, 1000] scale.

SELF-VERIFICATION RULES:
1. Nut Line: Identify the boundary where headstock meets the fretboard (0-fret).
2. Last Fret Line: Both body_top and body_bottom MUST lie on the EXACT SAME final metal fret wire near the body/pickguard!
3. Mental Flattening Check: Verify that if these 4 points are unwarped, the frets will stand naturally vertical without diagonal skew.

Return valid JSON:
{
  "reasoning": "...step-by-step verification of nut line and same last fret wire...",
  "nut_top": [y, x],
  "body_top": [y, x],
  "body_bottom": [y, x],
  "nut_bottom": [y, x]
}"""},
            {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
        ]}
    ]

    payload = {
        'contents': contents,
        'generationConfig': {'response_mime_type': 'application/json'}
    }

    res_json = None
    used_key_idx = 0
    for k_idx, key in enumerate(API_KEYS):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                res_json = resp.json()
                used_key_idx = k_idx
                break
            elif resp.status_code == 429:
                print(f"Key {k_idx} 429 Rate Limit -> Next key")
                continue
            else:
                print(f"Key {k_idx} HTTP {resp.status_code}: {resp.text[:150]}")
        except Exception as e:
            print(f"Key {k_idx} exception: {e}")

    if res_json is None:
        print("All API calls failed.")
        return

    # 토큰 사용량 확인
    usage = res_json.get('usageMetadata', {})
    prompt_tokens = usage.get('promptTokenCount', 0)
    candidate_tokens = usage.get('candidatesTokenCount', 0)
    total_tokens = usage.get('totalTokenCount', 0)

    print("==========================================")
    print("📊 API 실제 토큰 사용량 보고서:")
    print(f"  입력 토큰 (Prompt Tokens)     : {prompt_tokens:,} tokens")
    print(f"  출력 토큰 (Candidates Tokens) : {candidate_tokens:,} tokens")
    print(f"  총 소모 토큰 (Total Tokens)    : {total_tokens:,} tokens")
    print("==========================================")

    raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
    data = json.loads(raw_text)
    print("\n🧠 AI 자기 검증 추론 (Reasoning):")
    print(f"  {data.get('reasoning')}")

    pts = {}
    for name in ["nut_top", "body_top", "body_bottom", "nut_bottom"]:
        val = data[name]
        py = int(round(val[0] / 1000.0 * th))
        px = int(round(val[1] / 1000.0 * tw))
        pts[name] = (px, py)
        print(f"  {name:12s}: (x={px}, y={py}) [정규화: y={val[0]}, x={val[1]}]")

    # 시각화 저장
    vis = target_img.copy()
    corners = np.array([
        pts['nut_top'],
        pts['body_top'],
        pts['body_bottom'],
        pts['nut_bottom']
    ], dtype=np.int32)

    cv2.polylines(vis, [corners], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["NutTop", "BodyTop", "BodyBot", "NutBot"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(corners):
        px, py = int(pt[0]), int(pt[1])
        cv2.circle(vis, (px, py), 6, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_vis = "sample_images/suhr_master_detected.png"
    cv2.imwrite(out_vis, vis)

    # 평면화 저장
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = corners.astype(np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(target_img, M, (CANVAS_W, CANVAS_H))
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)

    out_flat = "sample_images/suhr_master_flat.png"
    cv2.imwrite(out_flat, flat)

    # 프렛 각도 측정
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=20, minLineLength=25, maxLineGap=5)
    if lines is not None:
        angles = [np.degrees(np.arctan2(l[0][3]-l[0][1], l[0][2]-l[0][0])) % 180 for l in lines if 70 < (np.degrees(np.arctan2(l[0][3]-l[0][1], l[0][2]-l[0][0])) % 180) < 110]
        if angles:
            print(f"\n📐 자연 평면화 프렛 각도: 평균 {np.mean(angles):.1f}도 (목표: 90.0도)")

    print(f"\n저장 완료:\n  - 원본 검출: {out_vis}\n  - 평면화: {out_flat}")
    return total_tokens

if __name__ == '__main__':
    run_master_pipeline('user_test_suhr_maple.png')
