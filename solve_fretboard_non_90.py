import cv2
import numpy as np
import os

def line_from_points(p1, p2):
    # Ax + By + C = 0
    A = p2[1] - p1[1]
    B = p1[0] - p2[0]
    C = p2[0] * p1[1] - p1[0] * p2[1]
    norm = np.hypot(A, B) + 1e-7
    return A / norm, B / norm, C / norm

def intersect_lines(L1, L2):
    # L1: (A1, B1, C1), L2: (A2, B2, C2)
    A1, B1, C1 = L1
    A2, B2, C2 = L2
    det = A1 * B2 - A2 * B1
    if abs(det) < 1e-5:
        return None
    x = (B1 * C2 - B2 * C1) / det
    y = (A2 * C1 - A1 * C2) / det
    return (int(round(x)), int(round(y)))

def run_non_90_detection(img_name):
    img_path = os.path.join('sample_images', img_name)
    img = cv2.imread(img_path)
    if img is None: return
    h, w, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # 1. 엣지 및 선 검출
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=30, minLineLength=35, maxLineGap=12)
    if lines is None: return

    # 2. 넥 방향(장축) 및 프렛/너트 방향(단축) 선 분리
    all_lines = []
    angle_lengths = {}
    for l in lines:
        x1, y1, x2, y2 = l[0]
        deg = np.degrees(np.arctan2(y2-y1, x2-x1)) % 180
        length = np.hypot(x2-x1, y2-y1)
        all_lines.append((deg, length, l[0]))
        b = int(round(deg / 5.0) * 5) % 180
        angle_lengths[b] = angle_lengths.get(b, 0) + length

    sorted_angles = sorted(angle_lengths.items(), key=lambda x: x[1], reverse=True)
    theta_neck = sorted_angles[0][0]

    # 3. 넥을 이루는 평행한 상단/하단 선 2개 찾기
    neck_lines = []
    for deg, length, l in all_lines:
        diff = abs(deg - theta_neck)
        if diff > 90: diff = 180 - diff
        if diff <= 6:
            neck_lines.append(l)

    # 넥과 수직인 축으로 투영하여 중심 띠 찾기
    normal_rad = np.radians((theta_neck + 90) % 180)
    normal_vec = np.array([np.cos(normal_rad), np.sin(normal_rad)])
    
    projs = []
    for l in neck_lines:
        p = ((l[0]+l[2])/2.0) * normal_vec[0] + ((l[1]+l[3])/2.0) * normal_vec[1]
        projs.append((p, l))
    projs.sort(key=lambda x: x[0])

    # 넥 띠 내부에서 가장 바깥쪽 상단/하단 라인
    top_l = projs[int(len(projs)*0.15)][1]
    bot_l = projs[int(len(projs)*0.85)][1]
    L_top = line_from_points((top_l[0], top_l[1]), (top_l[2], top_l[3]))
    L_bot = line_from_points((bot_l[0], bot_l[1]), (bot_l[2], bot_l[3]))

    # 4. [★ 핵심] 90도 강제 제거: 실제 사진에 찍힌 기울어진 너트선과 바디선 찾기
    # 넥과 교차하는(각도 차이 40도 ~ 85도) 실제 가로지르는 선들 탐색
    transverse_lines = []
    for deg, length, l in all_lines:
        diff = abs(deg - theta_neck)
        if diff > 90: diff = 180 - diff
        if 40 <= diff <= 85: # 90도가 아니라 비스듬한 선들!
            # 넥 중심 근처를 지나가는지 확인
            mid_p = ((l[0]+l[2])/2.0) * normal_vec[0] + ((l[1]+l[3])/2.0) * normal_vec[1]
            if projs[0][0] - 20 <= mid_p <= projs[-1][0] + 20:
                # 넥 축을 따른 위치 계산
                neck_rad = np.radians(theta_neck)
                along_d = ((l[0]+l[2])/2.0) * np.cos(neck_rad) + ((l[1]+l[3])/2.0) * np.sin(neck_rad)
                transverse_lines.append((along_d, deg, length, l))

    if len(transverse_lines) < 2:
        print(f"[{img_name}] 비스듬한 횡단선 부족")
        return

    transverse_lines.sort(key=lambda x: x[0])
    
    # 넥을 가로지르는 양 끝단 선 (실제 기울어진 각도를 가진 너트선 & 바디선)
    nut_cand = transverse_lines[-1][3]
    body_cand = transverse_lines[0][3]

    L_nut = line_from_points((nut_cand[0], nut_cand[1]), (nut_cand[2], nut_cand[3]))
    L_body = line_from_points((body_cand[0], body_cand[1]), (body_cand[2], body_cand[3]))

    # 5. [★ 실제 선들의 교점으로 4꼭짓점 계산 (90도 강제 없음!)]
    p1 = intersect_lines(L_top, L_nut)
    p2 = intersect_lines(L_top, L_body)
    p3 = intersect_lines(L_bot, L_body)
    p4 = intersect_lines(L_bot, L_nut)

    if None in [p1, p2, p3, p4]:
        print("교점 계산 불가")
        return

    corners = [p1, p2, p3, p4]

    # 내각 계산
    def get_angle(pt_prev, pt_curr, pt_next):
        v1 = np.array(pt_prev) - np.array(pt_curr)
        v2 = np.array(pt_next) - np.array(pt_curr)
        cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)
        return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

    angles = [
        get_angle(corners[3], corners[0], corners[1]),
        get_angle(corners[0], corners[1], corners[2]),
        get_angle(corners[1], corners[2], corners[3]),
        get_angle(corners[2], corners[3], corners[0])
    ]

    print(f"[{img_name}]")
    print(f"  -> 실제 검출된 모서리 내각: {[round(a,1) for a in angles]}도 (90도 강제 완전 해제!)")
    print(f"  -> 대각선 쌍 1: {angles[0]:.1f}도 & {angles[2]:.1f}도")
    print(f"  -> 대각선 쌍 2: {angles[1]:.1f}도 & {angles[3]:.1f}도")

    # 시각화 저장
    vis = img.copy()
    poly_pts = np.array(corners, dtype=np.int32)
    cv2.polylines(vis, [poly_pts], isClosed=True, color=(0, 255, 0), thickness=2)
    labels = ["P1(NutTop)", "P2(BodyTop)", "P3(BodyBot)", "P4(NutBot)"]
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    for i, pt in enumerate(corners):
        cv2.circle(vis, pt, 6, colors[i], -1)
        cv2.putText(vis, labels[i], (pt[0]+8, pt[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_det = f"sample_images/non_90_{img_name}"
    cv2.imwrite(out_det, vis)

    # 평면화 저장
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = np.array(corners, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(img, M, (CANVAS_W, CANVAS_H))
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
    out_flat = f"sample_images/non_90_flat_{img_name}"
    cv2.imwrite(out_flat, flat)

    print(f"  -> 원본 검출 저장: {out_det}")
    print(f"  -> 평면화 저장: {out_flat}\n")

if __name__ == '__main__':
    run_non_90_detection('1051_5603_0000.jpg')
    run_non_90_detection('images (2).jpg')
