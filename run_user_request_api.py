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

def encode_img_file(path, quality=92):
    img = cv2.imread(path)
    if img is None:
        raise FileNotFoundError(path)
    _, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    return base64.b64encode(buf).decode('utf-8')

# 1. 유저의 모범 답안 예시 데이터 준비 (user_fret_example.png + user_fret_example.json)
b64_exemplar = encode_img_file('sample_images/user_fret_example.png')
with open('dataset/fret_labels/user_fret_example.json', 'r', encoding='utf-8') as f:
    ex_data = json.load(f)

# 예시 와이어 좌표를 [0, 1000] 정규화 스케일로 변환
ex_frets = []
ex_w, ex_h = ex_data['width'], ex_data['height']
for w_item in ex_data['wires']:
    # p1 (상단): y=10 (약 67/1000), x=xt
    # p2 (하단): y=140 (약 933/1000), x=xb
    ny1 = int(round(15.0 / ex_h * 1000.0))
    nx1 = int(round(w_item['xt'] / ex_w * 1000.0))
    ny2 = int(round(135.0 / ex_h * 1000.0))
    nx2 = int(round(w_item['xb'] / ex_w * 1000.0))
    ex_frets.append({
        'fret_num': w_item['wire_idx'],
        'p1': [ny1, nx1],
        'p2': [ny2, nx2]
    })

# 2. 타겟 이미지 (3번 사진: fender_bw_super_contrast.png)
target_path = 'sample_images/fender_bw_super_contrast.png'
b64_target = encode_img_file(target_path)

prompt_rules = """You are an expert guitar luthier and computer vision engineer.
Examine the provided HUMAN GROUND TRUTH EXEMPLAR first to understand how a human expert labels fret wires on a flattened fretboard.

Now analyze the TARGET IMAGE (Contrast-Enhanced Black & White flattened guitar fretboard).
For every visible real metal fret wire (ordered from nut/fret 0 towards the body):
Identify TWO completely, unambiguously CERTAIN points (p1 and p2) on that same continuous metal fret wire.

MANDATORY RULES:
1. Slope Condition: The line between p1 and p2 must satisfy |m| = |(y2 - y1) / (x2 - x1)| > 1.
   (Frets are vertical/steep transverse lines across the strings, NEVER horizontal!).
2. For each fret wire, choose two points that are 100% clearly visible and not obscured by fingers or inlays.
3. Coordinates must be in [0, 1000] normalized scale: [y, x].

Return valid JSON:
{
  "frets": [
    {
      "fret_num": 0,
      "p1": [y, x],
      "p2": [y, x]
    }
  ]
}"""

contents = [
    # Few-shot 예시
    {'role': 'user', 'parts': [
        {'text': '[HUMAN GROUND TRUTH EXEMPLAR: Fretboard Image]'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_exemplar}}
    ]},
    {'role': 'model', 'parts': [
        {'text': json.dumps({'frets': ex_frets})}
    ]},
    # 타겟 질의
    {'role': 'user', 'parts': [
        {'text': prompt_rules + '\n\n[TARGET IMAGE: Please detect all fret wires]'},
        {'inline_data': {'mime_type': 'image/jpeg', 'data': b64_target}}
    ]}
]

payload = {
    'contents': contents,
    'generationConfig': {'response_mime_type': 'application/json'}
}

print("🚀 2차 API (유저 예시 페어 + 고대비 3번 사진 + |m|>1 조건) 호출 시작...")

res_json = None
used_key = 0
for idx, key in enumerate(API_KEYS):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={key}"
    try:
        r = requests.post(url, json=payload, timeout=60)
        if r.status_code == 200:
            res_json = r.json()
            used_key = idx
            print(f"✅ Key {idx} 호출 성공!")
            print("토큰 사용량:", res_json.get('usageMetadata'))
            break
        elif r.status_code == 429:
            print(f"Key {idx} 429 Rate Limit -> 다음 키 전환")
            continue
        else:
            print(f"Key {idx} HTTP {r.status_code}: {r.text[:120]}")
    except Exception as e:
        print(f"Key {idx} 예외: {e}")

if res_json is None:
    raise RuntimeError("모든 API 호출 실패")

raw_text = res_json['candidates'][0]['content']['parts'][0]['text']
with open('sample_images/fender_user_guided_frets.json', 'w', encoding='utf-8') as f:
    f.write(raw_text)

# 3. 결과 파싱 및 시각화
target_img = cv2.imread(target_path)
h, w, _ = target_img.shape
data = json.loads(raw_text)
frets = data.get('frets', [])
print(f"\n총 {len(frets)}개 프렛 검출됨.")

fret_lines = []
for item in frets:
    f_num = item.get('fret_num')
    p1 = item['p1']
    p2 = item['p2']
    x1 = p1[1] / 1000.0 * w
    y1 = p1[0] / 1000.0 * h
    x2 = p2[1] / 1000.0 * w
    y2 = p2[0] / 1000.0 * h

    # 기울기 계산 |dy / dx|
    dx = x2 - x1
    dy = y2 - y1
    slope = abs(dy / dx) if abs(dx) > 1e-4 else 999.0

    if abs(dy) > 1e-4:
        m_geom = dx / dy
        b_geom = x1 - m_geom * y1
        xt = b_geom
        xb = m_geom * h + b_geom
    else:
        xt = (x1 + x2) / 2.0
        xb = xt
        m_geom = 0.0

    fret_lines.append({
        'fret_num': f_num,
        'xt': float(xt),
        'xb': float(xb),
        'slope': float(slope),
        'raw_p1': (x1, y1),
        'raw_p2': (x2, y2)
    })
    print(f"  Fret {f_num:2d}: xt={xt:5.1f}, xb={xb:5.1f} | 기울기 |dy/dx|={slope:5.1f} (|m|>1 만족: {slope > 1.0})")

fret_lines.sort(key=lambda f: f['xt'])

# 4. 칸(Fret Box) 시각화 렌더링
vis = target_img.copy()
overlay = vis.copy()
colors = [
    (255, 90, 90), (90, 255, 90), (90, 150, 255),
    (255, 200, 70), (200, 90, 255), (70, 255, 255)
]

for k in range(len(fret_lines) - 1):
    f1 = fret_lines[k]
    f2 = fret_lines[k + 1]
    poly = np.array([
        [f1['xt'], 0],
        [f2['xt'], 0],
        [f2['xb'], h],
        [f1['xb'], h]
    ], dtype=np.int32)
    cv2.fillPoly(overlay, [poly], colors[k % len(colors)])

cv2.addWeighted(overlay, 0.35, vis, 0.65, 0, vis)

# 와이어 직선 & 검출된 2점 표시
for f in fret_lines:
    pt_top = (int(round(f['xt'])), 0)
    pt_bot = (int(round(f['xb'])), h)
    cv2.line(vis, pt_top, pt_bot, (0, 255, 0), 2)
    p1 = (int(round(f['raw_p1'][0])), int(round(f['raw_p1'][1])))
    p2 = (int(round(f['raw_p2'][0])), int(round(f['raw_p2'][1])))
    cv2.circle(vis, p1, 3, (0, 255, 255), -1)
    cv2.circle(vis, p2, 3, (0, 255, 255), -1)

# 칸 번호
for k in range(len(fret_lines) - 1):
    f1 = fret_lines[k]
    f2 = fret_lines[k + 1]
    mid_x = int(round((f1['xt'] + f2['xt'] + f1['xb'] + f2['xb']) / 4.0))
    cv2.putText(vis, str(k + 1), (mid_x - 5, int(h / 2) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 0), 2)
    cv2.putText(vis, str(k + 1), (mid_x - 5, int(h / 2) + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

out_flat = "sample_images/fender_user_guided_flat.png"
cv2.imwrite(out_flat, vis)

# 원본 사진에도 역투영
raw_original = cv2.imread('sample_images/new_user_fender_maple.jpg')
with open('sample_images/new_guitar_corners.json', 'r') as f:
    c_data = json.load(f)

c_pts = []
for name in ['nut_top', 'body_top', 'body_bottom', 'nut_bottom']:
    val = c_data[name]
    px = int(round(val[1] / 1000.0 * raw_original.shape[1]))
    py = int(round(val[0] / 1000.0 * raw_original.shape[0]))
    c_pts.append((px, py))

src_c = np.array(c_pts, dtype=np.float32)
dst_c = np.array([[0,0], [w, 0], [w, h], [0, h]], dtype=np.float32)
M_inv = cv2.getPerspectiveTransform(dst_c, src_c)

vis_raw = raw_original.copy()
overlay_raw = vis_raw.copy()

for k in range(len(fret_lines) - 1):
    f1 = fret_lines[k]
    f2 = fret_lines[k + 1]
    pts_flat = np.array([
        [[f1['xt'], 0]],
        [[f2['xt'], 0]],
        [[f2['xb'], h]],
        [[f1['xb'], h]]
    ], dtype=np.float32)
    pts_raw = cv2.perspectiveTransform(pts_flat, M_inv)
    poly_raw = pts_raw.astype(np.int32).reshape(-1, 2)
    cv2.fillPoly(overlay_raw, [poly_raw], colors[k % len(colors)])

cv2.addWeighted(overlay_raw, 0.35, vis_raw, 0.65, 0, vis_raw)

for f in fret_lines:
    p_top_flat = np.array([[[f['xt'], 0]]], dtype=np.float32)
    p_bot_flat = np.array([[[f['xb'], h]]], dtype=np.float32)
    pt_top = cv2.perspectiveTransform(p_top_flat, M_inv)[0][0]
    pt_bot = cv2.perspectiveTransform(p_bot_flat, M_inv)[0][0]
    cv2.line(vis_raw, (int(round(pt_top[0])), int(round(pt_top[1]))),
                      (int(round(pt_bot[0])), int(round(pt_bot[1]))), (0, 255, 0), 2)

out_raw = "sample_images/fender_user_guided_raw.png"
cv2.imwrite(out_raw, vis_raw)

# 아티팩트 디렉터리 복사
art_dir = "C:/Users/evev2/.gemini/antigravity/brain/b097f49a-587f-45e1-b717-5940c8f33184"
shutil.copy(out_flat, f"{art_dir}/fender_user_guided_flat.png")
shutil.copy(out_raw, f"{art_dir}/fender_user_guided_raw.png")
print("🎉 시각화 및 아티팩트 복사 완료!")
