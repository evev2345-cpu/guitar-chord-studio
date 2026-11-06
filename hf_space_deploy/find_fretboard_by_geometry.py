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
        return False, 0.0

    angles = []
    for i in range(4):
        v_prev = pts[(i - 1) % 4] - pts[i]
        v_next = pts[(i + 1) % 4] - pts[i]
        angles.append(angle_between_vectors(v_prev, v_next))

    if abs(sum(angles) - 360.0) > 5.0:
        return False, 0.0

    # 대각선 각도 대칭성 (둔각-둔각 / 예각-예각)
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
        return False, 0.0

    # 종횡비
    len_long = (np.linalg.norm(edges[0]) + np.linalg.norm(edges[2])) / 2.0
    len_short = (np.linalg.norm(edges[1]) + np.linalg.norm(edges[3])) / 2.0
    if len_short < 15:
        return False, 0.0
    ratio = len_long / len_short
    if not (4.0 <= ratio <= 15.0):
        return False, 0.0

    # 평행성 / 소실 각도
    taper = angle_between_vectors(edges[0], -edges[2])
    if taper > 20.0:
        return False, 0.0

    # 점수: 직사각형 및 대각선 각 대칭성이 얼마나 깔끔한지 (0 ~ 100)
    angle_sym_score = 100.0 - (abs(pair1[0] - pair1[1]) + abs(pair2[0] - pair2[1]))
    return True, max(0.0, angle_sym_score)

def detect_fretboard_geometric(img_path):
    img = cv2.imread(img_path)
    h, w, _ = img.shape
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 엣지 및 선 검출
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=40, minLineLength=40, maxLineGap=15)
    if lines is None:
        return None

    long_lines = []
    for l in lines:
        x1, y1, x2, y2 = l[0]
        length = np.hypot(x2-x1, y2-y1)
        angle = np.degrees(np.arctan2(y2-y1, x2-x1)) % 180
        if length > 50:
            long_lines.append((length, angle, (x1, y1, x2, y2)))

    print(f"[{img_path}] 검출된 긴 직선 개수: {len(long_lines)}개")
    return len(long_lines)

if __name__ == '__main__':
    detect_fretboard_geometric('sample_images/1051_5603_0000.jpg')
    detect_fretboard_geometric('sample_images/images (2).jpg')
