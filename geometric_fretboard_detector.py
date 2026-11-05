import os
import cv2
import numpy as np

def angle_between_vectors(v1, v2):
    """두 벡터 사이의 내각 (0 ~ 180도) 계산"""
    cos_theta = np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2) + 1e-7)
    cos_theta = np.clip(cos_theta, -1.0, 1.0)
    return np.degrees(np.arccos(cos_theta))

def check_fretboard_geometry(pts):
    """
    사용자의 기하학 규칙 검증:
    pts: 4개의 꼭짓점 [(x1,y1), (x2,y2), (x3,y3), (x4,y4)] (시계방향)
    """
    pts = np.array(pts, dtype=np.float32)
    
    # 1. 볼록 사각형(Convex Polygon) 검증
    # 인접한 변 벡터들의 외적이 모두 같은 부호여야 함 (꼬인 사각형 원천 차단)
    edges = [pts[(i + 1) % 4] - pts[i] for i in range(4)]
    cross_products = [edges[i][0] * edges[(i + 1) % 4][1] - edges[i][1] * edges[(i + 1) % 4][0] for i in range(4)]
    if not (all(cp > 0 for cp in cross_products) or all(cp < 0 for cp in cross_products)):
        return False, "Not convex (꼬인 사각형)"

    # 2. 4개 꼭짓점의 내각 계산 (θ1, θ2, θ3, θ4)
    angles = []
    for i in range(4):
        v_prev = pts[(i - 1) % 4] - pts[i]
        v_next = pts[(i + 1) % 4] - pts[i]
        angles.append(angle_between_vectors(v_prev, v_next))

    # 내각의 합이 약 360도인지 확인
    if abs(sum(angles) - 360.0) > 5.0:
        return False, f"Sum of angles is {sum(angles):.1f} != 360"

    # 3. [★ 사용자님 규칙] 대각선 각도 대칭성 (둔각-둔각 / 예각-예각)
    # 한 쌍의 대각선 각: (θ0, θ2), 다른 쌍: (θ1, θ3)
    pair1 = (angles[0], angles[2])
    pair2 = (angles[1], angles[3])

    # 기울어진 사각형의 사영: 한 쌍은 둔각(>90도), 다른 쌍은 예각(<90도)이거나 모두 90도 부근
    # 각 대각선 쌍 내부의 각도 차이가 너무 벌어지면 사영 왜곡이 아니라 찌그러진 다각형임
    is_pair1_acute = (pair1[0] <= 95 and pair1[1] <= 95)
    is_pair1_obtuse = (pair1[0] >= 85 and pair1[1] >= 85)
    is_pair2_acute = (pair2[0] <= 95 and pair2[1] <= 95)
    is_pair2_obtuse = (pair2[0] >= 85 and pair2[1] >= 85)

    valid_angles = (is_pair1_acute and is_pair2_obtuse) or (is_pair1_obtuse and is_pair2_acute)
    if not valid_angles:
        # 정면 직사각형인 경우 (모두 80~100도 사이)
        if all(75 <= a <= 105 for a in angles):
            valid_angles = True

    if not valid_angles:
        return False, f"Angles violate projective rule: {angles}"

    # 4. 종횡비(Aspect Ratio) 제약: 긴 변 / 짧은 변
    # edge 0 (NutTop -> BodyTop), edge 2 (BodyBot -> NutBot) : 긴 변 (넥 길이)
    # edge 1 (BodyTop -> BodyBot), edge 3 (NutBot -> NutTop) : 짧은 변 (지판 폭)
    len_long = (np.linalg.norm(edges[0]) + np.linalg.norm(edges[2])) / 2.0
    len_short = (np.linalg.norm(edges[1]) + np.linalg.norm(edges[3])) / 2.0
    
    if len_short < 10: # 너무 작은 노이즈
        return False, "Too small"

    ratio = len_long / len_short
    if not (2.5 <= ratio <= 12.0):
        return False, f"Aspect ratio {ratio:.2f} is not between 2.5 and 12.0"

    # 5. 두 긴 변의 평행성 / 소실 각도 (테이퍼링 각도 < 20도)
    neck_taper_angle = angle_between_vectors(edges[0], -edges[2])
    if neck_taper_angle > 20.0:
        return False, f"Neck taper angle {neck_taper_angle:.1f} > 20 deg (너무 많이 벌어짐)"

    return True, f"Valid Fretboard Quad (Ratio: {ratio:.1f}, Angles: {[round(a,1) for a in angles]})"

# 테스트: 사용자가 라벨링한 실제 좌표가 이 규칙을 통과하는지 검증
if __name__ == '__main__':
    import json
    label_dir = 'dataset/labels'
    print("=" * 65)
    print("  📐 사용자 기하학 규칙(대각선 각도 & 종횡비 & 소실점) 검증 테스트")
    print("=" * 65)

    passed_cnt = 0
    total = 0
    for f in sorted(os.listdir(label_dir)):
        if not f.endswith('.json'): continue
        total += 1
        with open(os.path.join(label_dir, f), 'r', encoding='utf-8') as jf:
            d = json.load(jf)
        pts = [(c['x'], c['y']) for c in d['corners']]
        is_valid, msg = check_fretboard_geometry(pts)
        if is_valid:
            passed_cnt += 1
            print(f"✅ {d['image']:<30} | {msg}")
        else:
            print(f"❌ {d['image']:<30} | 탈락: {msg}")

    print("=" * 65)
    print(f"결과: {passed_cnt} / {total} 개의 실제 기타 지판이 이 기하학 규칙을 완벽히 통과했습니다!")
