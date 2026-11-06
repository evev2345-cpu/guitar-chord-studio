import os
import cv2
import numpy as np

def angle_between_vectors(v1, v2):
    cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))

def check_fretboard_geometry(pts):
    pts = np.array(pts, dtype=np.float32)
    # 1. 볼록성 검사
    edges = [pts[(i + 1) % 4] - pts[i] for i in range(4)]
    cross_products = [edges[i][0] * edges[(i + 1) % 4][1] - edges[i][1] * edges[(i + 1) % 4][0] for i in range(4)]
    if not (all(cp > 0 for cp in cross_products) or all(cp < 0 for cp in cross_products)):
        return False, "Not convex"

    # 2. 내각 계산
    angles = []
    for i in range(4):
        v_prev = pts[(i - 1) % 4] - pts[i]
        v_next = pts[(i + 1) % 4] - pts[i]
        angles.append(angle_between_vectors(v_prev, v_next))

    # 3. 대각선 각도 대칭성 (둔각-둔각 / 예각-예각)
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
        return False, "Invalid angles"

    # 4. 종횡비 검사
    len_long = (np.linalg.norm(edges[0]) + np.linalg.norm(edges[2])) / 2.0
    len_short = (np.linalg.norm(edges[1]) + np.linalg.norm(edges[3])) / 2.0
    if len_short < 15: return False, "Too narrow"
    ratio = len_long / len_short
    if not (3.5 <= ratio <= 15.0):
        return False, f"Aspect ratio {ratio:.1f} out of range"

    return True, f"Valid Fretboard (Ratio: {ratio:.1f}, Angles: {[round(a,1) for a in angles]})"

def line_intersection(line1, line2):
    """두 직선의 교점 (x, y) 계산"""
    x1, y1, x2, y2 = line1
    x3, y3, x4, y4 = line2
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-6:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return (px, py)

def extract_fretboard_by_geometry(img_path, out_prefix):
    orig = cv2.imread(img_path)
    if orig is None: return
    h, w, _ = orig.shape
    gray = cv2.cvtColor(orig, cv2.COLOR_BGR2GRAY)
    
    # 노이즈 제거 및 엣지 추출
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    
    # 선분 검출
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=35, minLineLength=40, maxLineGap=12)
    if lines is None: return

    # 1. 각도별 라인 분류
    all_lines = []
    angle_lengths = {}
    for l in lines:
        x1, y1, x2, y2 = l[0]
        deg = np.degrees(np.arctan2(y2-y1, x2-x1)) % 180
        length = np.hypot(x2-x1, y2-y1)
        all_lines.append((deg, length, l[0]))
        b = int(round(deg / 5.0) * 5) % 180
        angle_lengths[b] = angle_lengths.get(b, 0) + length

    # 가장 긴 직선들이 모인 넥 각도 (θ_neck)
    sorted_angles = sorted(angle_lengths.items(), key=lambda x: x[1], reverse=True)
    theta_neck = sorted_angles[0][0]

    # 넥과 직각에 가까운 프렛 각도 (θ_fret)
    theta_fret = None
    for ang, total_len in sorted_angles[1:]:
        diff = abs(ang - theta_neck)
        if diff > 90: diff = 180 - diff
        if 70 <= diff <= 110:
            theta_fret = ang
            break

    if theta_fret is None:
        theta_fret = (theta_neck + 90) % 180

    print(f"[{os.path.basename(img_path)}] 검출된 메인 넥 각도: {theta_neck}도, 프렛 각도: {theta_fret}도")

    # 2. 넥 방향 라인 필터링
    neck_lines = []
    for deg, length, l in all_lines:
        diff = abs(deg - theta_neck)
        if diff > 90: diff = 180 - diff
        if diff <= 7:
            neck_lines.append(l)

    # 3. 프렛 방향 라인 필터링
    fret_lines = []
    for deg, length, l in all_lines:
        diff = abs(deg - theta_fret)
        if diff > 90: diff = 180 - diff
        if diff <= 10:
            fret_lines.append(l)

    if len(neck_lines) < 2 or len(fret_lines) < 2:
        print("라인 부족")
        return

    # 4. 넥의 양쪽 외곽선(상단/하단) 분리
    # 넥과 수직인 축으로 투영하여 양 끝단 라인 2개 선정
    normal_rad = np.radians((theta_neck + 90) % 180)
    normal_vec = np.array([np.cos(normal_rad), np.sin(normal_rad)])

    proj_dists = []
    for l in neck_lines:
        mid_x = (l[0] + l[2]) / 2.0
        mid_y = (l[1] + l[3]) / 2.0
        d = mid_x * normal_vec[0] + mid_y * normal_vec[1]
        proj_dists.append((d, l))

    proj_dists.sort(key=lambda x: x[0])
    # 양 끝 15% 지점의 대표 라인
    top_line = proj_dists[0][1]
    bottom_line = proj_dists[-1][1]

    # 5. 프렛의 양 끝단 라인(너트/바디끝) 분리
    neck_rad = np.radians(theta_neck)
    neck_vec = np.array([np.cos(neck_rad), np.sin(neck_rad)])

    fret_projs = []
    for l in fret_lines:
        mid_x = (l[0] + l[2]) / 2.0
        mid_y = (l[1] + l[3]) / 2.0
        d = mid_x * neck_vec[0] + mid_y * neck_vec[1]
        fret_projs.append((d, l))

    fret_projs.sort(key=lambda x: x[0])
    nut_line = fret_projs[0][1]
    body_line = fret_projs[-1][1]

    # 6. 4개 교점 계산
    p1 = line_intersection(top_line, nut_line)
    p2 = line_intersection(top_line, body_line)
    p3 = line_intersection(bottom_line, body_line)
    p4 = line_intersection(bottom_line, nut_line)

    if None in [p1, p2, p3, p4]:
        print("교점 계산 실패")
        return

    candidate_pts = [p1, p2, p3, p4]

    # 7. [★ 사용자 기하학 규칙 검증]
    is_valid, msg = check_fretboard_geometry(candidate_pts)
    print(f"기하학 규칙 검증 결과: {is_valid} ({msg})")

    # 시각화 저장
    vis = orig.copy()
    pts_int = np.array(candidate_pts, dtype=np.int32)
    cv2.polylines(vis, [pts_int], isClosed=True, color=(0, 255, 0), thickness=2)
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    labels = ["P1(NutTop)", "P2(BodyTop)", "P3(BodyBot)", "P4(NutBot)"]
    for i, pt in enumerate(candidate_pts):
        ip = (int(pt[0]), int(pt[1]))
        cv2.circle(vis, ip, 7, colors[i], -1)
        cv2.putText(vis, labels[i], (ip[0]+8, ip[1]-5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_det = f"sample_images/geom_{out_prefix}_detected.jpg"
    cv2.imwrite(out_det, vis)

    # 8. 평면화 (Warp)
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = np.array(candidate_pts, dtype=np.float32)
    M = cv2.getPerspectiveTransform(src, dst)
    flat = cv2.warpPerspective(orig, M, (CANVAS_W, CANVAS_H))
    
    # 6줄 가이드라인
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * CANVAS_H)
        cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)

    out_flat = f"sample_images/geom_{out_prefix}_flat.jpg"
    cv2.imwrite(out_flat, flat)

    print(f"✅ 저장 완료:\n  - 원본 검출: {out_det}\n  - 평면화: {out_flat}")

if __name__ == '__main__':
    extract_fretboard_by_geometry('sample_images/1051_5603_0000.jpg', '1051_5603')
    extract_fretboard_by_geometry('sample_images/1051_5605_0000.jpg', '1051_5605')
