import os
import json
import shutil
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LABEL_DIR = os.path.join(BASE_DIR, 'dataset', 'labels')
IMG_DIR = os.path.join(BASE_DIR, 'sample_images')
YOLO_DIR = os.path.join(BASE_DIR, 'dataset', 'yolo_fretboard_corrected')

train_img_dir = os.path.join(YOLO_DIR, 'images', 'train')
val_img_dir = os.path.join(YOLO_DIR, 'images', 'val')
train_lbl_dir = os.path.join(YOLO_DIR, 'labels', 'train')
val_lbl_dir = os.path.join(YOLO_DIR, 'labels', 'val')

for d in [train_img_dir, val_img_dir, train_lbl_dir, val_lbl_dir]:
    os.makedirs(d, exist_ok=True)

# 1. 원본 라벨 파일 로드
label_files = [f for f in sorted(os.listdir(LABEL_DIR)) if f.endswith('.json')]
print(f"Loaded {len(label_files)} label files.")

def write_yolo_annotation(out_txt, w, h, corners):
    by_name = {p['name']: p for p in corners}
    corners = [by_name[n] for n in ('nut_top', 'body_top', 'body_bottom', 'nut_bottom')]
    xs = [p['x'] / w for p in corners]
    ys = [p['y'] / h for p in corners]
    bx_center = (min(xs) + max(xs)) / 2.0
    by_center = (min(ys) + max(ys)) / 2.0
    bw = max(xs) - min(xs)
    bh = max(ys) - min(ys)
    # 4개 키포인트 (x, y, v=2)
    kpts_str = " ".join([f"{x:.6f} {y:.6f} 2" for x, y in zip(xs, ys)])
    with open(out_txt, 'w', encoding='utf-8') as f:
        f.write(f"0 {bx_center:.6f} {by_center:.6f} {bw:.6f} {bh:.6f} {kpts_str}\n")

sample_idx = 0
for idx, lf in enumerate(label_files):
    with open(os.path.join(LABEL_DIR, lf), 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    img_name = data['image']
    orig_img_path = os.path.join(IMG_DIR, img_name)
    if not os.path.exists(orig_img_path):
        continue
        
    img = cv2.imread(orig_img_path)
    h, w, _ = img.shape
    corners = data['corners']
    
    # 80% train, 20% val
    is_val = (idx % 5 == 0)
    target_img_dir = val_img_dir if is_val else train_img_dir
    target_lbl_dir = val_lbl_dir if is_val else train_lbl_dir
    
    # 1) 원본 저장
    stem = f"sample_{sample_idx:03d}"
    out_img = os.path.join(target_img_dir, f"{stem}.jpg")
    out_txt = os.path.join(target_lbl_dir, f"{stem}.txt")
    cv2.imwrite(out_img, img)
    write_yolo_annotation(out_txt, w, h, corners)
    sample_idx += 1
    
    # 2) 데이터 증강 (밝기/대비 변화 및 가우시안 노이즈)
    if not is_val:
        # 밝기 어둡게
        stem_dark = f"sample_{sample_idx:03d}_dark"
        img_dark = np.clip(img.astype(np.float32) * 0.7 - 20, 0, 255).astype(np.uint8)
        cv2.imwrite(os.path.join(target_img_dir, f"{stem_dark}.jpg"), img_dark)
        write_yolo_annotation(os.path.join(target_lbl_dir, f"{stem_dark}.txt"), w, h, corners)
        sample_idx += 1
        
        # 밝기 밝게
        stem_bright = f"sample_{sample_idx:03d}_bright"
        img_bright = cv2.convertScaleAbs(img, alpha=1.2, beta=25)
        cv2.imwrite(os.path.join(target_img_dir, f"{stem_bright}.jpg"), img_bright)
        write_yolo_annotation(os.path.join(target_lbl_dir, f"{stem_bright}.txt"), w, h, corners)
        sample_idx += 1

# 3. YAML 파일 생성
yaml_content = f"""path: {YOLO_DIR.replace(chr(92), '/')}
train: images/train
val: images/val
kpt_shape: [4, 3] # 4 keypoints, (x, y, visibility)
flip_idx: [0, 1, 2, 3] # Physical string-side identities survive image mirroring

names:
  0: fretboard
"""

yaml_path = os.path.join(YOLO_DIR, 'dataset.yaml')
with open(yaml_path, 'w', encoding='utf-8') as f:
    f.write(yaml_content)

print(f"✅ YOLO 데이터셋 생성 완료! 총 {sample_idx}개 샘플 (학습용 + 증강용)")
print(f"YAML 설정 파일: {yaml_path}")
