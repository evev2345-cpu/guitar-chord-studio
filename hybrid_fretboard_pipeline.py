import cv2
import numpy as np
import os
import json
from ultralytics import YOLO

def line_from_points(p1, p2):
    # Ax + By + C = 0
    A = p2[1] - p1[1]
    B = p1[0] - p2[0]
    C = p2[0] * p1[1] - p1[0] * p2[1]
    norm = np.hypot(A, B) + 1e-7
    return A / norm, B / norm, C / norm

def intersect_lines(L1, L2):
    A1, B1, C1 = L1
    A2, B2, C2 = L2
    det = A1 * B2 - A2 * B1
    if abs(det) < 1e-5:
        return None
    x = (B1 * C2 - B2 * C1) / det
    y = (A2 * C1 - A1 * C2) / det
    return np.array([x, y], dtype=np.float32)

def get_angle(pt_prev, pt_curr, pt_next):
    v1 = np.array(pt_prev) - np.array(pt_curr)
    v2 = np.array(pt_next) - np.array(pt_curr)
    cos = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)
    return np.degrees(np.arccos(np.clip(cos, -1.0, 1.0)))

def run_hybrid_pipeline(img_name, yolo_model, debug_dir="sample_images/hybrid_results"):
    os.makedirs(debug_dir, exist_ok=True)
    img_path = os.path.join('sample_images', img_name)
    img = cv2.imread(img_path)
    if img is None:
        return None
    h, w, _ = img.shape

    # 1. YOLO Rough ROI Detection (낮은 임계값으로 대략적인 위치 무조건 확보)
    results = yolo_model(img, conf=0.08, verbose=False)[0]
    if len(results.keypoints) == 0 or len(results.keypoints.data) == 0:
        print(f"[{img_name}] YOLO 검출 실패 -> 전체 이미지에서 탐색")
        min_x, min_y, max_x, max_y = 0, 0, w, h
        rough_pts = np.array([[0,0], [w, 0], [w, h], [0, h]], dtype=np.float32)
    else:
        kpts = results.keypoints.data[0].cpu().numpy() # [4, 3] (x, y, conf)
        rough_pts = kpts[:, :2]

        # 패딩을 준 관심 영역(ROI) 계산
        pad = int(max(w, h) * 0.08) # 8% 여유 마진
        min_x = max(0, int(np.min(rough_pts[:, 0]) - pad))
        max_x = min(w, int(np.max(rough_pts[:, 0]) + pad))
        min_y = max(0, int(np.min(rough_pts[:, 1]) - pad))
        max_y = min(h, int(np.max(rough_pts[:, 1]) + pad))

    roi_w = max_x - min_x
    roi_h = max_y - min_y
    if roi_w < 30 or roi_h < 30:
        return None

    roi_img = img[min_y:max_y, min_x:max_x]

    # 2. ROI 내부에서 에지 및 직선 검출 (배경이 없으므로 지판 신호만 매우 강함)
    gray_roi = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray_roi, (5, 5), 0)
    edges = cv2.Canny(blurred, 30, 100)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=15, minLineLength=15, maxLineGap=8)

    if lines is None or len(lines) < 4:
        # 직선이 부족할 경우 YOLO의 거친 예측점을 그대로 사용
        final_corners = rough_pts
    else:
        # 각도 히스토그램으로 넥 축 각도 탐색
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

        # 넥 평행선들 (rails)
        neck_lines = []
        for deg, length, l in all_lines:
            diff = abs(deg - theta_neck)
            if diff > 90: diff = 180 - diff
            if diff <= 6:
                neck_lines.append(l)

        # 넥 수직축 투영
        normal_rad = np.radians((theta_neck + 90) % 180)
        normal_vec = np.array([np.cos(normal_rad), np.sin(normal_rad)])
        projs = []
        for l in neck_lines:
            p = ((l[0]+l[2])/2.0) * normal_vec[0] + ((l[1]+l[3])/2.0) * normal_vec[1]
            projs.append((p, l))
        projs.sort(key=lambda x: x[0])

        if len(projs) >= 2:
            top_l = projs[int(len(projs)*0.10)][1]
            bot_l = projs[int(len(projs)*0.90)][1]
            L_top = line_from_points((top_l[0], top_l[1]), (top_l[2], top_l[3]))
            L_bot = line_from_points((bot_l[0], bot_l[1]), (bot_l[2], bot_l[3]))

            # 넥을 가로지르는 프렛선들 (transverse lines)
            transverse_lines = []
            for deg, length, l in all_lines:
                diff = abs(deg - theta_neck)
                if diff > 90: diff = 180 - diff
                if 40 <= diff <= 85: # 비스듬한 선 (90도 강제 없음)
                    neck_rad = np.radians(theta_neck)
                    along_d = ((l[0]+l[2])/2.0) * np.cos(neck_rad) + ((l[1]+l[3])/2.0) * np.sin(neck_rad)
                    transverse_lines.append((along_d, deg, length, l))

            if len(transverse_lines) >= 2:
                transverse_lines.sort(key=lambda x: x[0])
                nut_cand = transverse_lines[-1][3]
                body_cand = transverse_lines[0][3]

                L_nut = line_from_points((nut_cand[0], nut_cand[1]), (nut_cand[2], nut_cand[3]))
                L_body = line_from_points((body_cand[0], body_cand[1]), (body_cand[2], body_cand[3]))

                # ROI 좌표계에서의 교점 계산
                p1_roi = intersect_lines(L_top, L_nut)
                p2_roi = intersect_lines(L_top, L_body)
                p3_roi = intersect_lines(L_bot, L_body)
                p4_roi = intersect_lines(L_bot, L_nut)

                if all(p is not None for p in [p1_roi, p2_roi, p3_roi, p4_roi]):
                    # 원본 전체 이미지 좌표계로 복원 (+ min_x, + min_y)
                    offset = np.array([min_x, min_y], dtype=np.float32)
                    final_corners = np.array([p1_roi, p2_roi, p3_roi, p4_roi]) + offset
                else:
                    final_corners = rough_pts
            else:
                final_corners = rough_pts
        else:
            final_corners = rough_pts

    # 3. Ground Truth 비교 평가
    gt_file = os.path.join('dataset/labels', f"{os.path.splitext(img_name)[0]}.json")
    err = None
    if os.path.exists(gt_file):
        with open(gt_file) as f:
            gt_data = json.load(f)
        gt_pts = np.array([[c['x'], c['y']] for c in gt_data['corners']], dtype=np.float32)

        # 4점의 순서 매칭 (최적 회전/반전 매칭)
        min_dist = 1e9
        best_ordered = final_corners
        for shift in range(4):
            rolled = np.roll(final_corners, shift, axis=0)
            d = np.mean(np.linalg.norm(rolled - gt_pts, axis=1))
            if d < min_dist:
                min_dist = d
                best_ordered = rolled
            d_flip = np.mean(np.linalg.norm(rolled[::-1] - gt_pts, axis=1))
            if d_flip < min_dist:
                min_dist = d_flip
                best_ordered = rolled[::-1]
        err = min_dist
        final_corners = best_ordered

    # 4. 시각화 저장
    vis = img.copy()
    # ROI 박스 표시 (파란색)
    cv2.rectangle(vis, (min_x, min_y), (max_x, max_y), (255, 100, 0), 2)
    # 지판 외곽 다각형 (초록색)
    poly = final_corners.astype(np.int32)
    cv2.polylines(vis, [poly], isClosed=True, color=(0, 255, 0), thickness=2)
    # 꼭짓점 점 찍기
    colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    labels = ["NutTop", "BodyTop", "BodyBot", "NutBot"]
    for i, pt in enumerate(final_corners):
        px, py = int(round(pt[0])), int(round(pt[1]))
        cv2.circle(vis, (px, py), 5, colors[i], -1)
        cv2.putText(vis, labels[i], (px + 6, py - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[i], 1)

    out_det_path = os.path.join(debug_dir, f"hybrid_{img_name}")
    cv2.imwrite(out_det_path, vis)

    # 5. 평면화 (Warp Perspective)
    CANVAS_W, CANVAS_H = 800, 150
    dst = np.array([[0,0], [CANVAS_W, 0], [CANVAS_W, CANVAS_H], [0, CANVAS_H]], dtype=np.float32)
    src = final_corners.astype(np.float32)
    try:
        M = cv2.getPerspectiveTransform(src, dst)
        flat = cv2.warpPerspective(img, M, (CANVAS_W, CANVAS_H))
        for s in range(6):
            sy = int((s + 0.5) / 6.0 * CANVAS_H)
            cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
        cv2.imwrite(os.path.join(debug_dir, f"hybrid_flat_{img_name}"), flat)
    except:
        pass

    return err, final_corners
