import os
import json
import cv2
import numpy as np

# 폴더 설정
IMG_DIR = 'sample_images'
DATASET_DIR = 'dataset'
LABEL_DIR = os.path.join(DATASET_DIR, 'labels')
PREVIEW_DIR = os.path.join(DATASET_DIR, 'preview')

os.makedirs(LABEL_DIR, exist_ok=True)
os.makedirs(PREVIEW_DIR, exist_ok=True)

# 라벨링 대상 이미지 파일 목록 (디버그/결과 파일 제외)
all_files = sorted(os.listdir(IMG_DIR))
target_images = [
    f for f in all_files 
    if f.lower().endswith(('.jpg', '.jpeg', '.png')) 
    and not f.startswith(('result_', 'crop_', 'fretboard_', 'debug_', 'seg_', 'interactive_', 'cutout_'))
]

point_names = [
    "1. Nut Top (너트 6번줄쪽)",
    "2. Body Top (바디 6번줄쪽)",
    "3. Body Bottom (바디 1번줄쪽)",
    "4. Nut Bottom (너트 1번줄쪽)"
]
point_colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]

class FretboardLabeler:
    def __init__(self):
        self.current_points = []
        self.scale = 1.0

    def mouse_callback(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if len(self.current_points) < 4:
                # 화면 스케일 -> 원본 해상도 좌표 복원
                orig_x = int(x / self.scale)
                orig_y = int(y / self.scale)
                self.current_points.append((orig_x, orig_y))

def run_labeler():
    labeler = FretboardLabeler()
    window_name = "Guitar Fretboard 4-Point Labeler"
    cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
    cv2.setMouseCallback(window_name, labeler.mouse_callback)

    total_imgs = len(target_images)
    idx = 0

    print("=" * 65)
    print("      🎸 기타 지판 4개 꼭짓점 라벨링 도구 시작")
    print("=" * 65)
    print(" [클릭 순서]")
    for p in point_names:
        print(f"  👉 {p}")
    print("\n [키보드 조작]")
    print("  • [Space] 또는 [Enter] : 저장하고 다음 사진으로 이동")
    print("  • [R]                 : 현재 사진 클릭 초기화 (다시 찍기)")
    print("  • [S]                 : 현재 사진 건너뛰기")
    print("  • [Q] 또는 [ESC]       : 종료")
    print("=" * 65)

    while idx < total_imgs:
        img_name = target_images[idx]
        img_path = os.path.join(IMG_DIR, img_name)
        orig_img = cv2.imread(img_path)
        if orig_img is None:
            idx += 1
            continue

        h, w, _ = orig_img.shape
        label_file = os.path.join(LABEL_DIR, f"{os.path.splitext(img_name)[0]}.json")

        # 이미 라벨링된 경우 불러오기
        if os.path.exists(label_file) and len(labeler.current_points) == 0:
            with open(label_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
                labeler.current_points = [(p['x'], p['y']) for p in saved['corners']]

        # 화면 크기에 맞게 리사이즈 배율 계산 (최대 1200x800)
        max_disp_w, max_disp_h = 1200, 800
        scale = min(max_disp_w / w, max_disp_h / h, 1.0)
        labeler.scale = scale
        disp_w, disp_h = int(w * scale), int(h * scale)

        while True:
            # 베이스 디스플레이 이미지
            disp = cv2.resize(orig_img, (disp_w, disp_h))

            # 상단 상태바 (검은색 띠)
            bar_h = 60
            top_bar = np.zeros((bar_h, disp_w, 3), dtype=np.uint8)

            # 진행률 표시
            progress_text = f"[{idx+1}/{total_imgs}] {img_name} ({w}x{h})"
            cv2.putText(top_bar, progress_text, (10, 22), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1)

            # 현재 클릭할 단계 안내
            num_pts = len(labeler.current_points)
            if num_pts < 4:
                guide_text = f"Click: {point_names[num_pts]}"
                cv2.putText(top_bar, guide_text, (10, 48), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, point_colors[num_pts], 2)
            else:
                guide_text = "READY! Press [SPACE] to Save | [R] Reset | [S] Skip"
                cv2.putText(top_bar, guide_text, (10, 48), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

            # 상단바 + 이미지 합성
            canvas = np.vstack([top_bar, disp])

            # 클릭된 점 및 연결선 그리기
            scaled_pts = []
            for i, (ox, oy) in enumerate(labeler.current_points):
                sx = int(ox * scale)
                sy = int(oy * scale) + bar_h
                scaled_pts.append((sx, sy))
                cv2.circle(canvas, (sx, sy), 6, point_colors[i], -1)
                cv2.putText(canvas, str(i + 1), (sx + 8, sy - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, point_colors[i], 2)

            # 점 연결선 그리기
            for i in range(len(scaled_pts) - 1):
                cv2.line(canvas, scaled_pts[i], scaled_pts[i + 1], (0, 255, 255), 2)

            # 4점이 모두 찍히면 폐곡선 폴리곤 채우기
            if num_pts == 4:
                cv2.line(canvas, scaled_pts[3], scaled_pts[0], (0, 255, 255), 2)
                poly_pts = np.array(scaled_pts, np.int32)
                overlay = canvas.copy()
                cv2.fillPoly(overlay, [poly_pts], (0, 255, 0))
                canvas = cv2.addWeighted(overlay, 0.3, canvas, 0.7, 0)

            cv2.imshow(window_name, canvas)
            key = cv2.waitKey(20) & 0xFF

            # [SPACE] 또는 [ENTER] : 저장 후 다음
            if key in [32, 13]:
                if len(labeler.current_points) == 4:
                    # 1) JSON 저장
                    data_to_save = {
                        "image": img_name,
                        "image_size": [w, h],
                        "corners": [
                            {"name": "nut_top", "x": labeler.current_points[0][0], "y": labeler.current_points[0][1]},
                            {"name": "body_top", "x": labeler.current_points[1][0], "y": labeler.current_points[1][1]},
                            {"name": "body_bottom", "x": labeler.current_points[2][0], "y": labeler.current_points[2][1]},
                            {"name": "nut_bottom", "x": labeler.current_points[3][0], "y": labeler.current_points[3][1]}
                        ]
                    }
                    with open(label_file, 'w', encoding='utf-8') as f:
                        json.dump(data_to_save, f, indent=2, ensure_ascii=False)

                    # 2) YOLO OBB / Pose 용 정규화 좌표 TXT 저장
                    # bbox: [class, x_center, y_center, w, h, x1, y1, v1, x2, y2, v2, ...]
                    txt_file = os.path.join(LABEL_DIR, f"{os.path.splitext(img_name)[0]}.txt")
                    xs = [p[0] / w for p in labeler.current_points]
                    ys = [p[1] / h for p in labeler.current_points]
                    bx_center = (min(xs) + max(xs)) / 2.0
                    by_center = (min(ys) + max(ys)) / 2.0
                    bw = max(xs) - min(xs)
                    bh = max(ys) - min(ys)
                    kpts_str = " ".join([f"{x:.6f} {y:.6f} 2" for x, y in zip(xs, ys)])
                    with open(txt_file, 'w', encoding='utf-8') as f:
                        f.write(f"0 {bx_center:.6f} {by_center:.6f} {bw:.6f} {bh:.6f} {kpts_str}\n")

                    # 3) 미리보기 저장
                    preview_img = orig_img.copy()
                    poly_orig = np.array(labeler.current_points, np.int32)
                    cv2.polylines(preview_img, [poly_orig], True, (0, 255, 0), 3)
                    for i, (ox, oy) in enumerate(labeler.current_points):
                        cv2.circle(preview_img, (ox, oy), 8, point_colors[i], -1)
                        cv2.putText(preview_img, str(i + 1), (ox + 10, oy - 10),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, point_colors[i], 2)
                    preview_path = os.path.join(PREVIEW_DIR, f"{os.path.splitext(img_name)[0]}_preview.jpg")
                    cv2.imwrite(preview_path, preview_img)

                    print(f"✅ 저장 완료 [{idx+1}/{total_imgs}]: {img_name}")
                    labeler.current_points = []
                    idx += 1
                    break
                else:
                    print("⚠️ 4개 점을 모두 클릭해야 저장할 수 있습니다!")

            # [R] : 리셋
            elif key in [ord('r'), ord('R')]:
                labeler.current_points = []
                print("🔄 좌표 초기화!")

            # [S] : 스킵
            elif key in [ord('s'), ord('S')]:
                labeler.current_points = []
                idx += 1
                print(f"⏭ 건너뜀: {img_name}")
                break

            # [Q] 또는 [ESC] : 종료
            elif key in [ord('q'), ord('Q'), 27]:
                print("\n🛑 라벨링 도구를 종료합니다.")
                cv2.destroyAllWindows()
                return

    cv2.destroyAllWindows()
    print("\n🎉 모든 이미지 처리가 끝났습니다! dataset/labels 폴더를 확인하세요.")

if __name__ == '__main__':
    run_labeler()
