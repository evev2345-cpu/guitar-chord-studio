import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

def run_fretboard_tab_analysis(img_path, src_corners, num_frets=12):
    # 1. 이미지 로드
    orig_img = cv2.imread(img_path)
    h, w, _ = orig_img.shape
    vis_orig = orig_img.copy()

    # 2. 평면 캔버스 크기 정의 (가로 800px, 세로 180px)
    CANVAS_W = 800
    CANVAS_H = 180
    dst_corners = np.array([
        [0, 0],                 # 너트 상단 (Top-Left)
        [CANVAS_W, 0],         # 바디쪽 상단 (Top-Right)
        [CANVAS_W, CANVAS_H],  # 바디쪽 하단 (Bottom-Right)
        [0, CANVAS_H]          # 너트 하단 (Bottom-Left)
    ], dtype=np.float32)

    src_pts = np.array(src_corners, dtype=np.float32)

    # 3. Homography (원근 변환 행렬) 계산
    # M: 원본 사진 -> 평면 지판 변환
    # M_inv: 평면 지판 -> 원본 사진 역변환
    M = cv2.getPerspectiveTransform(src_pts, dst_corners)
    M_inv = cv2.getPerspectiveTransform(dst_corners, src_pts)

    # 4. 지판 영역을 평면으로 쫙 펴기 (Warp Perspective)
    flat_board = cv2.warpPerspective(orig_img, M, (CANVAS_W, CANVAS_H))

    # 5. 수학적 프렛 간격(Fret Spacing) 및 6개 기타 줄 계산
    # 물리 법칙: d_n = L * (1 - 2^(-n/12))
    scale_length = CANVAS_W / (1.0 - 2.0 ** (-num_frets / 12.0))
    fret_x_positions = [0]
    for n in range(1, num_frets + 1):
        fx = int(scale_length * (1.0 - 2.0 ** (-n / 12.0)))
        fret_x_positions.append(min(fx, CANVAS_W - 1))

    # 6개 줄 높이 (0번: 1번줄 High-E ~ 5번: 6번줄 Low-E)
    string_names = ['1번줄(e)', '2번줄(B)', '3번줄(G)', '4번줄(D)', '5번줄(A)', '6번줄(E)']
    string_y_positions = [int((s + 0.5) / 6.0 * CANVAS_H) for s in range(6)]

    # 6. 평면 지판에 격자(Grid) 그리기
    vis_flat = flat_board.copy()
    # 프렛 세로선 (은색)
    for fret_num, fx in enumerate(fret_x_positions):
        cv2.line(vis_flat, (fx, 0), (fx, CANVAS_H), (200, 200, 200), 2)
        if fret_num > 0:
            mid_fret = int((fret_x_positions[fret_num - 1] + fx) / 2)
            cv2.putText(vis_flat, str(fret_num), (mid_fret - 5, CANVAS_H - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 255), 1)

    # 기타 줄 가로선 (노란색)
    for s_idx, sy in enumerate(string_y_positions):
        cv2.line(vis_flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)
        cv2.putText(vis_flat, string_names[s_idx], (5, sy - 4),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)

    # 7. MediaPipe로 손가락 끝(Fingertip) 검출
    base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
    options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
    detector = vision.HandLandmarker.create_from_options(options)

    mp_image = mp.Image.create_from_file(img_path)
    hand_result = detector.detect(mp_image)

    fingertip_indices = {8: 'Index(검지)', 12: 'Middle(중지)', 16: 'Ring(약지)', 20: 'Pinky(새끼)'}
    colors = {
        'Index(검지)': (0, 0, 255),
        'Middle(중지)': (0, 255, 0),
        'Ring(약지)': (255, 0, 0),
        'Pinky(새끼)': (255, 0, 255)
    }

    tab_detections = []

    if hand_result.hand_landmarks:
        for hand in hand_result.hand_landmarks:
            for tip_idx, tip_name in fingertip_indices.items():
                lm = hand[tip_idx]
                orig_px, orig_py = int(lm.x * w), int(lm.y * h)

                # 원본 픽셀 좌표를 평면 지판(Homography) 좌표로 투영!
                pt_mat = np.array([[[orig_px, orig_py]]], dtype=np.float32)
                transformed_pt = cv2.perspectiveTransform(pt_mat, M)[0][0]
                tx, ty = int(transformed_pt[0]), int(transformed_pt[1])

                # 지판 영역 내부인지 확인
                if 0 <= tx < CANVAS_W and 0 <= ty < CANVAS_H:
                    # 1) 몇 번 프렛인가?
                    fret_detected = 0
                    for fn in range(1, len(fret_x_positions)):
                        if fret_x_positions[fn - 1] <= tx < fret_x_positions[fn]:
                            fret_detected = fn
                            break

                    # 2) 몇 번 줄에 가장 가까운가?
                    string_dists = [abs(ty - sy) for sy in string_y_positions]
                    string_detected = int(np.argmin(string_dists))

                    tab_detections.append({
                        'finger': tip_name,
                        'string': string_detected + 1,
                        'string_name': string_names[string_detected],
                        'fret': fret_detected,
                        'flat_pt': (tx, ty),
                        'orig_pt': (orig_px, orig_py),
                        'color': colors[tip_name]
                    })

                    # 평면 지판에 운지 마커 찍기
                    cv2.circle(vis_flat, (tx, ty), 9, colors[tip_name], -1)
                    cv2.putText(vis_flat, tip_name.split('(')[0], (tx + 12, ty + 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.45, colors[tip_name], 2)

    # 8. 원본 사진에도 정밀 지판 격자선 & 손가락 포인트 투영 (Inverse Warp)
    # 지판 외곽선
    pts_int = np.array(src_corners, dtype=np.int32)
    cv2.polylines(vis_orig, [pts_int], isClosed=True, color=(0, 255, 0), thickness=2)

    # 프렛선과 줄을 원본 사진에 정밀하게 그리기
    for fx in fret_x_positions:
        line_pts = np.array([[[fx, 0]], [[fx, CANVAS_H]]], dtype=np.float32)
        trans_line = cv2.perspectiveTransform(line_pts, M_inv).astype(np.int32)
        cv2.line(vis_orig, tuple(trans_line[0][0]), tuple(trans_line[1][0]), (255, 200, 0), 1)

    for sy in string_y_positions:
        line_pts = np.array([[[0, sy]], [[CANVAS_W, sy]]], dtype=np.float32)
        trans_line = cv2.perspectiveTransform(line_pts, M_inv).astype(np.int32)
        cv2.line(vis_orig, tuple(trans_line[0][0]), tuple(trans_line[1][0]), (0, 255, 255), 1)

    for td in tab_detections:
        cv2.circle(vis_orig, td['orig_pt'], 8, td['color'], -1)
        cv2.putText(vis_orig, f"{td['finger']}: {td['string']}s {td['fret']}f", 
                    (td['orig_pt'][0] + 10, td['orig_pt'][1] - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

    # 9. 결과 저장
    out_flat = 'sample_images/fretboard_flat_canonical.jpg'
    out_orig = 'sample_images/fretboard_warped_grid.jpg'
    cv2.imwrite(out_flat, vis_flat)
    cv2.imwrite(out_orig, vis_orig)

    # 10. 콘솔 출력 (TAB 악보 생성)
    print("=" * 60)
    print("      [OpenCV Homography & MediaPipe 기반 기타 TAB 판정 결과]")
    print("=" * 60)
    if tab_detections:
        for td in tab_detections:
            print(f"👉 {td['finger']:<12} | 누른 위치: {td['string_name']} | {td['fret']}번 프렛")
        
        print("\n=== 실시간 생성된 TAB 악보 ===")
        tab_board = {i: ['-'] * (num_frets + 1) for i in range(1, 7)}
        for td in tab_detections:
            tab_board[td['string']][td['fret']] = str(td['fret'])

        for s in range(1, 7):
            s_name = string_names[s - 1].split('(')[0]
            line_str = "".join([f"-{tab_board[s][f]}-" for f in range(1, num_frets + 1)])
            print(f"{s_name} |{line_str}|")
    else:
        print("지판 격자 내에서 감지된 손가락이 없습니다.")
    print("=" * 60)
    print(f"1) 평면으로 쫙 펴진 지판: {out_flat}")
    print(f"2) 원본에 투영된 정밀 격자: {out_orig}")

# 실행: 1051_5603_0000.jpg에 적용
# 너트 상단, 바디 상단, 바디 하단, 너트 하단
src_corners = [
    [85, 230],   # Top-Left (너트 6번줄쪽)
    [370, 240],  # Top-Right (바디 6번줄쪽)
    [370, 275],  # Bottom-Right (바디 1번줄쪽)
    [85, 275]    # Bottom-Left (너트 1번줄쪽)
]

run_fretboard_tab_analysis('sample_images/1051_5603_0000.jpg', src_corners, num_frets=10)
