import os
import torch
from ultralytics import YOLO

def main():
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    yaml_path = os.path.join(BASE_DIR, 'dataset', 'yolo_fretboard_corrected', 'dataset.yaml')
    
    torch.set_num_threads(4)
    # GPU 사용 가능 여부 확인
    device = '0' if torch.cuda.is_available() else 'cpu'
    print(f"🎸 학습 디바이스: {device} (PyTorch {torch.__version__})")
    
    # 초경량 나노 포즈 모델 로드 (yolov8n-pose.pt - 약 6.5MB)
    print("📦 사전학습 모델 다운로드 및 로드 중...")
    model = YOLO('yolov8n-pose.pt')
    
    # 4개 꼭짓점(Keypoint) 전이학습 (Transfer Learning)
    print("🚀 지판 꼭짓점 4개 검출 AI 학습 시작...")
    model.train(
        data=yaml_path,
        epochs=120,
        imgsz=640,
        batch=4,
        device=device,
        project=os.path.join(BASE_DIR, 'runs', 'pose', 'fretboard_corrected'),
        name='identity_no_mosaic',
        exist_ok=False,
        workers=0,
        seed=0,
        patience=40,
        mosaic=0.0,
        mixup=0.0,
        fliplr=0.0,
        flipud=0.0,
        translate=0.05,
        scale=0.15,
        degrees=10.0,
        perspective=0.0,
        plots=True,
        verbose=True
    )
    
    print("\n🎉 학습 완료! 최종 가중치: runs/pose/fretboard_corrected/identity_no_mosaic/weights/best.pt")

if __name__ == '__main__':
    main()
