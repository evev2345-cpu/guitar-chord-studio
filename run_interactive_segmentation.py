import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python.components.containers import keypoint

# 1. 대상 이미지 선택
img_name = '1051_5603_0000.jpg'
img_path = f'sample_images/{img_name}'
orig_img = cv2.imread(img_path)
h, w, _ = orig_img.shape

# 2. Interactive Segmenter 모델 로드 (MagicTouch)
segmenter = mp.tasks.vision.InteractiveSegmenterLegacy.create_from_model_path('magic_touch.tflite')
mp_img = mp.Image.create_from_file(img_path)

# 3. 프롬프트 좌표 설정 (손가락 운지 부근 / 지판 좌표)
# x=0.28, y=0.38 (정규화 좌표 0~1)
prompt_x, prompt_y = 0.28, 0.38
roi = mp.tasks.vision.InteractiveSegmenterLegacyRegionOfInterest(
    format=mp.tasks.vision.InteractiveSegmenterLegacyRegionOfInterest.Format.KEYPOINT,
    keypoint=keypoint.NormalizedKeypoint(x=prompt_x, y=prompt_y)
)

# 4. 세그멘테이션 실행
result = segmenter.segment(mp_img, roi)

# 5. 마스크 추출 (0.0 ~ 1.0 확률 맵)
mask = result.confidence_masks[0].numpy_view().squeeze()
binary_mask = (mask > 0.5).astype(np.uint8)

# 6. 시각화 (원본에 마스크를 반투명 초록색으로 덧씌우고 클릭 지점 표시)
overlay = orig_img.copy()
# 마스크 영역에 초록색 (BGR: 0, 255, 0) 적용
color_mask = np.zeros_like(orig_img)
color_mask[binary_mask == 1] = [0, 255, 0]

alpha = 0.5
vis = cv2.addWeighted(color_mask, alpha, overlay, 1 - alpha, 0)
vis[binary_mask == 0] = orig_img[binary_mask == 0]

# 클릭한 지점(ROI) 표시 (빨간 원과 십자선)
cx, cy = int(prompt_x * w), int(prompt_y * h)
cv2.circle(vis, (cx, cy), 8, (0, 0, 255), -1)
cv2.drawMarker(vis, (cx, cy), (255, 255, 255), cv2.MARKER_CROSS, 16, 2)
cv2.putText(vis, f"Prompt ({cx}, {cy})", (cx + 12, cy - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

out_file = f'sample_images/interactive_segmented_{img_name}'
cv2.imwrite(out_file, vis)

# 분리된 물체만 따로 검정 배경에 저장
segmented_cutout = cv2.bitwise_and(orig_img, orig_img, mask=binary_mask)
out_cutout = f'sample_images/cutout_{img_name}'
cv2.imwrite(out_cutout, segmented_cutout)

print(f"=== Interactive Segmenter 결과 ===")
print(f"이미지: {img_name} ({w}x{h})")
print(f"클릭 좌표: x={prompt_x:.2f}, y={prompt_y:.2f} (픽셀: {cx}, {cy})")
print(f"세그멘테이션된 픽셀 수: {np.sum(binary_mask)} / {w*h} ({np.sum(binary_mask)/(w*h)*100:.1f}%)")
print(f"시각화 결과 저장: {out_file}")
print(f"추출물 결과 저장: {out_cutout}")
