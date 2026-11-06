import cv2
import numpy as np
from scipy.signal import find_peaks
import shutil
import os

def detect_visual_frets(raw_img_path, corners, canvas_w=800, canvas_h=150, out_prefix="sample_images/suhr"):
    raw = cv2.imread(raw_img_path)
    if raw is None:
        raise FileNotFoundError(f"Cannot load image: {raw_img_path}")

    # corners: [nut_top, body_top, body_bottom, nut_bottom]
    src = np.array(corners, dtype=np.float32)
    dst = np.array([[0,0], [canvas_w, 0], [canvas_w, canvas_h], [0, canvas_h]], dtype=np.float32)

    M = cv2.getPerspectiveTransform(src, dst)
    M_inv = cv2.getPerspectiveTransform(dst, src)

    # 1. Canonical Flat Fretboard 추출
    flat = cv2.warpPerspective(raw, M, (canvas_w, canvas_h))
    gray = cv2.cvtColor(flat, cv2.COLOR_BGR2GRAY)

    # 2. 기타줄 제거 (세로 Morphological Opening)
    k_vert = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 11))
    fret_ridges = cv2.morphologyEx(gray, cv2.MORPH_OPEN, k_vert)

    # 3. 로컬 대비 강화 (CLAHE) - 메이플 넥의 은색 금속 와이어 대비 극대화
    clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(fret_ridges)

    # 4. 세로 방향 엣지 신호 검출
    grad_x = cv2.Sobel(enhanced, cv2.CV_64F, 1, 0, ksize=3)
    grad_abs = np.uint8(np.absolute(grad_x))

    # 5. 중앙 포지션 마크(점) 회피: 상단/하단 스트립의 세로 에너지 평균
    strip_top = grad_abs[15:50, :]
    strip_bot = grad_abs[100:135, :]
    col_profile = (np.mean(strip_top, axis=0) + np.mean(strip_bot, axis=0)) / 2.0

    # 1D 가우시안 스무딩
    smoothed = cv2.GaussianBlur(col_profile.reshape(1, -1), (1, 5), 1.2).ravel()

    # 6. 피크 검출 (와이어 양쪽 엣지 포함)
    raw_peaks, _ = find_peaks(smoothed, distance=12, prominence=4.5)

    # 7. 단일 와이어 중심화 (양쪽 엣지 클러스터링)
    # 한 금속 와이어의 폭(약 16px 이내)에 잡힌 쌍(좌우 엣지)을 하나의 중심선으로 병합
    frets = []
    curr = [raw_peaks[0]]
    for p in raw_peaks[1:]:
        if p - curr[-1] <= 16:
            curr.append(p)
        else:
            frets.append(int(round(np.mean(curr))))
            curr = [p]
    if curr:
        frets.append(int(round(np.mean(curr))))

    # 8. 평면 지판 시각화
    vis_flat = flat.copy()
    # 6개 기타줄 가로선 (노란색)
    for s in range(6):
        sy = int((s + 0.5) / 6.0 * canvas_h)
        cv2.line(vis_flat, (0, sy), (canvas_w, sy), (0, 220, 255), 1)

    # 검출된 프렛 와이어 (형광 연두색 세로선)
    for idx, fx in enumerate(frets):
        color = (0, 255, 0)
        cv2.line(vis_flat, (fx, 0), (fx, canvas_h), color, 2)
        cv2.putText(vis_flat, str(idx), (fx - 4, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 255), 1)

    out_flat = f"{out_prefix}_visual_frets_flat.png"
    cv2.imwrite(out_flat, vis_flat)

    # 9. 원본 원근 사진 위에 직접 투영
    vis_raw = raw.copy()
    for idx, fx in enumerate(frets):
        pt_top = np.array([[[fx, 0]]], dtype=np.float32)
        pt_bot = np.array([[[fx, canvas_h]]], dtype=np.float32)
        raw_top = cv2.perspectiveTransform(pt_top, M_inv)[0][0]
        raw_bot = cv2.perspectiveTransform(pt_bot, M_inv)[0][0]

        p1 = (int(round(raw_top[0])), int(round(raw_top[1])))
        p2 = (int(round(raw_bot[0])), int(round(raw_bot[1])))
        cv2.line(vis_raw, p1, p2, (0, 255, 0), 1)
        # 번호 표기
        if idx % 2 == 0 or idx in [1, 3, 5, 7, 9, 12, 15, 17, 19, 21]:
            cv2.putText(vis_raw, str(idx), (p1[0] - 3, p1[1] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 0, 255), 1)

    # 6개 줄도 투영
    for s in range(6):
        sy = (s + 0.5) / 6.0 * canvas_h
        p_nut = cv2.perspectiveTransform(np.array([[[0, sy]]], dtype=np.float32), M_inv)[0][0]
        p_body = cv2.perspectiveTransform(np.array([[[canvas_w, sy]]], dtype=np.float32), M_inv)[0][0]
        cv2.line(vis_raw, (int(round(p_nut[0])), int(round(p_nut[1]))),
                          (int(round(p_body[0])), int(round(p_body[1]))), (0, 220, 255), 1)

    out_raw = f"{out_prefix}_visual_frets_raw.png"
    cv2.imwrite(out_raw, vis_raw)

    # 아티팩트 디렉터리로 복사
    art_dir = "C:/Users/evev2/.gemini/antigravity/brain/b097f49a-587f-45e1-b717-5940c8f33184"
    shutil.copy(out_flat, os.path.join(art_dir, "suhr_visual_frets_flat.png"))
    shutil.copy(out_raw, os.path.join(art_dir, "suhr_visual_frets_raw.png"))

    print("==========================================")
    print(f"🎸 [순수 이미지 기반 프렛 검출 완료!]")
    print(f"  - 식별된 실제 프렛 와이어: 총 {len(frets)}개")
    print("  - 실제 프렛 X 좌표 목록:")
    print(f"    {frets}")
    print("==========================================")
    return frets

if __name__ == "__main__":
    corners = [[435, 239], [249, 258], [265, 298], [439, 256]]
    detect_visual_frets("sample_images/user_test_suhr_maple.png", corners)
