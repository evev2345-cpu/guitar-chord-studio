import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# 1. Load Image
img_path = 'sample_images/acoustic_close_2.jpg'
img = cv2.imread(img_path)
h, w, _ = img.shape
vis_img = img.copy()

# 2. Run MediaPipe Hand Landmarker
base_options = python.BaseOptions(model_asset_path='hand_landmarker.task')
options = vision.HandLandmarkerOptions(base_options=base_options, num_hands=2)
detector = vision.HandLandmarker.create_from_options(options)

image_mp = mp.Image.create_from_file(img_path)
detection_result = detector.detect(image_mp)

tips = {4: 'Thumb', 8: 'Index', 12: 'Middle', 16: 'Ring', 20: 'Pinky'}
detected_fingertips = {}

if detection_result.hand_landmarks:
    for hand_idx, hand_lms in enumerate(detection_result.hand_landmarks):
        for tip_idx, tip_name in tips.items():
            lm = hand_lms[tip_idx]
            px, py = int(lm.x * w), int(lm.y * h)
            detected_fingertips[tip_name] = (px, py)
            cv2.circle(vis_img, (px, py), 7, (0, 0, 255), -1)
            cv2.putText(vis_img, tip_name, (px + 10, py - 5), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

print("=== 검출된 손가락 끝(Fingertip) 픽셀 좌표 ===")
for name, pt in detected_fingertips.items():
    print(f"{name:<8}: x={pt[0]}, y={pt[1]}")

cv2.imwrite('sample_images/fretboard_test_step1.jpg', vis_img)
print("\n[Step 1 완료] 손가락 끝 인식 결과가 'sample_images/fretboard_test_step1.jpg'에 저장되었습니다.")
