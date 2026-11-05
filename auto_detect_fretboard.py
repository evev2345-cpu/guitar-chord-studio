import os
import cv2
import numpy as np
from ultralytics import YOLO

def run_auto_detection(weights_path='runs/pose/fretboard_model/pose_exp/weights/best.pt'):
    if not os.path.exists(weights_path):
        print(f"❌ 가중치 파일을 찾을 수 없습니다: {weights_path}")
        return

    model = YOLO(weights_path)
    
    IMG_DIR = 'sample_images'
    OUT_DETECTED = 'dataset/auto_detected'
    OUT_UNWARPED = 'dataset/auto_unwarped'
    os.makedirs(OUT_DETECTED, exist_ok=True)
    os.makedirs(OUT_UNWARPED, exist_ok=True)

    CANVAS_W = 800
    CANVAS_H = 150
    dst_corners = np.array([
        [0, 0],
        [CANVAS_W, 0],
        [CANVAS_W, CANVAS_H],
        [0, CANVAS_H]
    ], dtype=np.float32)

    point_colors = [(255, 0, 0), (0, 255, 0), (0, 255, 255), (0, 0, 255)]
    point_names = ["NutTop", "BodyTop", "BodyBot", "NutBot"]

    test_images = [
        f for f in sorted(os.listdir(IMG_DIR))
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        and not f.startswith(('result_', 'crop_', 'fretboard_', 'debug_', 'seg_', 'interactive_', 'cutout_'))
    ]

    print("=" * 65)
    print("      🎸 YOLOv8-Pose 지판 4코너 자동 검출 & 평면화 테스트")
    print("=" * 65)

    for img_name in test_images:
        img_path = os.path.join(IMG_DIR, img_name)
        orig_img = cv2.imread(img_path)
        if orig_img is None: continue
        h, w, _ = orig_img.shape

        # AI 추론 실행
        results = model(img_path, verbose=False)
        res = results[0]

        if len(res.keypoints) == 0 or len(res.keypoints.xy[0]) < 4:
            print(f"⚠️ {img_name:<30} | 지판 미검출")
            continue

        # 검출된 4개 꼭짓점 좌표 추출
        kpts = res.keypoints.xy[0].cpu().numpy()[:4] # shape: (4, 2)
        conf = float(res.boxes.conf[0].cpu().numpy()) if len(res.boxes) > 0 else 0.0

        vis_img = orig_img.copy()

        # 1) 원본에 지판 4각형 폴리곤 그리기
        poly_pts = np.array(kpts, dtype=np.int32)
        cv2.polylines(vis_img, [poly_pts], isClosed=True, color=(0, 255, 0), thickness=2)

        for i, pt in enumerate(kpts):
            px, py = int(pt[0]), int(pt[1])
            cv2.circle(vis_img, (px, py), 6, point_colors[i], -1)
            cv2.putText(vis_img, point_names[i], (px + 8, py - 6),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.45, point_colors[i], 1)

        det_out = os.path.join(OUT_DETECTED, f"auto_{img_name}")
        cv2.imwrite(det_out, vis_img)

        # 2) Homography로 자동 평면화 (Unwarp)
        src_pts = np.array(kpts, dtype=np.float32)
        M = cv2.getPerspectiveTransform(src_pts, dst_corners)
        flat = cv2.warpPerspective(orig_img, M, (CANVAS_W, CANVAS_H))

        # 가이드 6현 그리기
        for s in range(6):
            sy = int((s + 0.5) / 6.0 * CANVAS_H)
            cv2.line(flat, (0, sy), (CANVAS_W, sy), (0, 255, 255), 1)

        unwarp_out = os.path.join(OUT_UNWARPED, f"auto_flat_{img_name}")
        cv2.imwrite(unwarp_out, flat)

        print(f"✅ {img_name:<30} | 신뢰도: {conf*100:.1f}% | 자동 평면화 완료!")

    print("=" * 65)
    print(f"결과 저장 위치:")
    print(f" 1) 자동 검출 시각화: {OUT_DETECTED}")
    print(f" 2) 자동 평면화 지판: {OUT_UNWARPED}")

if __name__ == '__main__':
    run_auto_detection()
