import os
import cv2
import numpy as np

def angle_between_vectors(v1, v2):
    cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))

def check_fretboard_geometry(pts):
    pts = np.array(pts, dtype=np.float32)
    edges = [pts[(i + 1) % 4] - pts[i] for i in range(4)]
    cross_products = [edges[i][0] * edges[(i + 1) % 4][1] - edges[i][1] * edges[(i + 1) % 4][0] for i in range(4)]
    if not (all(cp > 0 for cp in cross_products) or all(cp < 0 for cp in cross_products)):
        return False, "Not convex"

    angles = []
    for i in range(4):
        v_prev = pts[(i - 1) % 4] - pts[i]
        v_next = pts[(i + 1) % 4] - pts[i]
        angles.append(angle_between_vectors(v_prev, v_next))

    # [사용자 규칙] 대각선 각도 대칭성 (둔각-둔각 / 예각-예각)
    pair1 = (angles[0], angles[2])
    pair2 = (angles[1], angles[3])
    is_pair1_acute = (pair1[0] <= 95 and pair1[1] <= 95)
    is_pair1_obtuse = (pair1[0] >= 85 and pair1[1] >= 85)
    is_pair2_acute = (pair2[0] <= 95 and pair2[1] <= 95)
    is_pair2_obtuse = (pair2[0] >= 85 and pair2[1] >= 85)
    valid_angles = (is_pair1_acute and is_pair2_obtuse) or (is_pair1_obtuse and is_pair2_acute)
    if not valid_angles and all(75 <= a <= 105 for a in angles):
        valid_angles = True
    if not valid_angles:
        return False, f"Angles {angles} violate projective rule"

    # 종횡비
    len_long = (np.linalg.norm(edges[0]) + np.linalg.norm(edges[2])) / 2.0
    len_short = (np.linalg.norm(edges[1]) + np.linalg.norm(edges[3])) / 2.0
    if len_short < 15: return False, "Too narrow"
    ratio = len_long / len_short
    if not (3.5 <= ratio <= 15.0):
        return False, f"Aspect ratio {ratio:.1f} out of range"

    return True, f"Valid Fretboard (Ratio: {ratio:.1f})"

def auto_locate_fretboard(img_path, out_prefix):
    orig = cv2.imread(img_path)
    if orig is None: return False
    h, w, _ = orig.shape
    gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)

    # 1. 엣지 및 허프 선분 추출
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=35, minLineLength=40, maxLineGap=12)
    if lines is None: return False

    # 2. 넥의 메인 방향(각도) 탐색
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

    # 3. 넥 방향에 정렬된 라인들의 1D 밀도 투영 (가장 평행선이 밀집된 넥 띠 탐색)
    normal_rad = np.radians((theta_neck + 90) % 180)
    normal_vec = np.array([np.cos(normal_rad), np.sin(normal_rad)])

    neck_lines = []
    projs = []
    for deg, length, l in all_lines:
        diff = abs(deg - theta_neck)
        if diff > 90: diff = 180 - diff
        if diff <= 6:
            mid_x = (l[0] + l[2]) / 2.0
            mid_y = (l[1] + l[3]) / 2.0
            p = mid_x * normal_vec[0] + mid_y * normal_vec[1]
            projs.append(p)
            neck_lines.append(l)

    if len(projs) < 4: return False

    # 1D 히스토그램으로 넥 중심 축 찾기
    min_p, max_p = min(projs), max(projs)
    hist, bin_edges = np.histogram(projs, bins=np.arange(min_p, max_p + 15, 12))
    if len(hist) == 0: return False
    max_idx = np.argmax(hist)
    neck_center_proj = (bin_edges[max_idx] + bin_edges[max_idx + 1]) / 2.0

    # 넥 띠 내부의 라인만 선별 (반경 35px 이내)
    neck_band_lines = []
    for l in neck_lines:
        mid_x = (l[0] + l[2]) / 2.0
        mid_y = (l[1] + l[3]) / 2.0
        p = mid_x * normal_vec[0] + mid_y * normal_vec[1]
        if abs(p - neck_center_proj) <= 35.0:
            neck_band_lines.append((p, l))

    if len(neck_band_lines) < 2: return False
    neck_band_lines.sort(key=lambda x: x[0])
    
    # 상단 모서리 & 하단 모서리
    top_p = neck_band_lines[0][0]
    bot_p = neck_band_lines[-1][0]
    
    # 4. 넥 축을 따른 시작점(너트)과 끝점(바디) 범위 탐색
    neck_rad = np.radians(theta_neck)
    neck_vec = np.array([np.cos(neck_rad), np.sin(neck_rad)])
    
    along_dists = []
    for _, l in neck_band_lines:
        d1 = l[0] * neck_vec[0] + l[1] * neck_vec[1]
        d2 = l[2] * neck_vec[0] + l[3] * neck_vec[1]
        along_dists.extend([d1, d2])

    min_along = np.percentile(along_dists, 5)
    max_along = np.percentile(along_dists, 95)

    # 5. 4개 꼭짓점 좌표 역투영
    # 점 P = along * neck_vec + perp * normal_vec
    def to_xy(along, perp):
        # [neck_vec, normal_vec] 역행렬로 (x, y) 복원
        mat = np.array([neck_vec, normal_vec])
        xy = np.linalg.inv(mat).T @ np.array([along, perp])
        return (int(xy[0]), int(xy[1]))

    p1 = to_xy(max_along, top_p) # NutTop
    p2 = to_xy(min_along, top_p) # BodyTop
    p3 = to_xy(min_along, bot_p) # BodyBot
    p4 = to_xy(max_along, bot_p) # NutBot
    
    candidate_pts = [p1, p2, p3, p4]

    # 6. [★ 사용자 기하학 규칙 검증]
    is_valid, msg = check_fretboard_geometry(candidate_pts)
    print(f"[{os.path.basename(img_path)}] 기하학 검증: {is_valid} ({msg})")

    # 7. 시각화 저장
    vis = orig.copy()
    poly_pts = np.array(candidate_pts, dtype=np.int32)
    cv2.polylines(vis, [poly_pts], isClosed=True, color=(0, 255, 0), thickness=2)
    
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    labels = ["P1(NutTop)", "P2(BodyTop)", "P3(BodyBot)", "P4(NutBot)"]
    for i, pt in enumerate(candidate_pts):
        cv2.circle(vis, pt, 6, colors[i], -1)
        cv2.putText(vis, labels[i], (pt[0]+8, pt[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_det = f"sample_images/auto_geom_{out_prefix}_detected.jpg"
    cv2.imwrite(out_det, vis)

    # 8. 평면화
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = np.array(candidate_pts, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(orig, M, (CANVAS_W, CANVAS_H))
    
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)

    out_flat = f"sample_images/auto_geom_{out_prefix}_flat.jpg"
    cv2.imwrite(out_flat, flat)

    print(f"  -> 검출 이미지: {out_det}")
    print(f"  -> 평면화 이미지: {out_flat}")
    return True

if __name__ == '__main__':
    for f in ['1051_5603_0000.jpg', 'images (2).jpg', 'escgE1715241981.jpg']:
        p = os.path.join('sample_images', f)
        stem = os.path.splitext(f)[0]
        auto_locate_fretboard(p, stem)
