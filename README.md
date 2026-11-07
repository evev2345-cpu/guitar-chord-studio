---
title: Guitar Chord Studio v2.0
emoji: 🎸
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# Guitar Chord Studio v2.0 🎸

> **AI 기반 6-Stem 기타 트랙 분리, 16박자 악보 에디터, 4점 지판 캘리브레이션 및 MediaPipe C++ 손가락 비전 추적 데스크톱 솔루션**

음원(MP3, WAV) 또는 연주 영상(MP4, AVI, MOV)을 업로드하면, AI 딥러닝 모델(`htdemucs_6s`, `Basic Pitch`)이 기타 음원을 고품질로 분리하여 16박자 단위 정밀 코드 악보를 생성하고, 화면 위 연주자의 손가락과 기타 지판을 3차원으로 실시간 추적해 주는 전문 기타 연습 및 채보 프로그램입니다.

---

## ✨ 핵심 기능 (Key Features)

* **100% 무설치 독립 실행 데스크톱 앱 (Standalone)**:
  * 파이썬, Visual C++, FFMpeg 등이 설치되지 않은 순정 Windows PC에서도 더블 클릭만으로 즉시 구동 (`GuitarChordStudio.exe`).
  * Microsoft Edge WebView2 엔진 기반 H.264 하드웨어 가속 동영상 재생.
  * 백그라운드 무소음 프로세싱 (콘솔 검은 창 깜빡임 0%).
* **AI 6-Stem 기타 음향 분리 (Demucs v4)**:
  * 보컬, 베이스, 드럼 등 복잡한 믹스에서 기타 단독 트랙(`guitar.wav`)을 분리하여 코드 인식 정확도 극대화.
* **16박자 스마트 비트 격자 & 오프라인 선확인 (Look-Ahead v2)**:
  * 마디 단위 자동 템포(BPM) 및 위상 오프셋 정렬.
  * 0.25초 오프라인 선확인을 통해 코드 깜빡임 36.7% 제거 및 `D/F#` 등 분수코드(Bass Inversion) 정밀 복원.
  * 카포(Capo 0~12) 설정에 따른 실음(Concert) / 운지(Shape) 즉시 변환.
* **마우스 클릭 코드 즉각 교정 & 영구 저장**:
  * 악보 상의 특정 코드 블록을 클릭하여 즉시 수정 가능하며, 수정 내역은 디스크에 자동 보존.
* **사용자 주도 4점 지판 캘리브레이션 & MediaPipe C++ 비전 추적**:
  * 1번 줄/6번 줄 너트와 브릿지 4점 클릭으로 기타 지판의 원근 투영 변환(Homography) 도출.
  * Google `MediaPipe Hand Landmarker` C++ 바이너리(`libmediapipe.dll`) 연동으로 왼손 21개 관절 좌표 프레임별 실시간 추적.
  * 상단 툴바 실시간 비전 인디케이터(`⏳ 지판 비전 분석 중 (0%~100%)` → `✓ 지판 비전 활성`).
* **영구 보관함 (History Storage)**:
  * 앱을 껐다 켜거나 PC를 재부팅해도 이전 분석 곡들이 100% 보존되며 0.1초 만에 즉시 복원.
  * 보관함 목록에 `✓ 음성 완료`와 `✓ 비전 완료` 배지 분리 제공.

---

## 📁 프로젝트 구조 (Clean Architecture)

```text
GUITAR/
├── 🎸 desktop_chord_studio.py # 데스크톱 실행 진입점 (PyWebView + Edge WebView2)
├── 📦 GuitarChordStudio.spec  # PyInstaller 무설치 단독 패키징 명세서
├── 📄 00_프로젝트_개발일지_및_전체문서_총괄_마스터.md # 5일간의 전체 개발일지 및 80여 편 문서 총괄 색인
├── chord_studio_v2/           # 모던 Chord Studio v2 애플리케이션
│   ├── server_v2.py           # 고속 비동기 API 서버 (포트 8766 / 7860)
│   ├── static/                # 모던 스튜디오 UI (index.html, app.js, style.css)
│   └── runs/                  # 영구 분석 보관함 디렉토리
├── engine/                    # 핵심 분석 & 인퍼런스 엔진
│   ├── harmony_engine.py      # 크로마 풀링, 코드 템플릿 매칭 & 스코어링
│   ├── harmonic_context.py    # 조성 추정 및 전체 음원 앵커링 보정
│   ├── chord_presentation.py  # Look-Ahead v2 코드 표시 안정화 & 분수코드 복원
│   ├── beat_grid.py           # 16박자 템포 추정 및 비트 격자 정렬
│   ├── onset_transition.py    # 온셋 전환 감지
│   ├── run_local_separation.py# Demucs 6-stem 음원 분리 워커
│   ├── basic_pitch_worker.py  # Spotify Basic Pitch ONNX 전사 워커
│   ├── virtual_string_grid.py # 가상 6현 & 22프렛 지오메트리 그리드 생성
│   ├── hand_fret_tracker.py   # 지판 위 손가락 프렛 추적기
│   ├── improve_hand_skeleton.py # MediaPipe 관절 지터 완화 및 스켈레톤 보정
│   └── low_string_root_prior.py # 저음현(6·5번현) 운지 근음 우선 가점
├── models/                    # AI 모델 가중치
│   ├── nmp.onnx               # 음향 코드 판단 ONNX 모델
│   └── hand_landmarker.task   # MediaPipe 손가락 21개 관절 랜드마크 모델
├── dataset/                   # 검증 및 튜토리얼 벤치마크 데이터
├── tests/                     # 326개 전체 유닛 테스트 및 계약 테스트 모음
├── Dockerfile                 # 클라우드/Hugging Face Spaces 배포 Dockerfile
└── docker-compose.yml         # 원클릭 컨테이너 배포 설정
```

---

## 🚀 실행 가이드

### 1. 배포용 무설치 데스크톱 앱 (일반 사용자)
1. `GuitarChordStudio_v2.0_Windows.zip` (약 405 MB) 압축 해제
2. 폴더 내 `GuitarChordStudio.exe` 더블 클릭하여 즉시 실행 (Python 설치 불필요)

### 2. 개발자 로컬 개발 모드
```powershell
# 1. 의존성 설치
pip install -r requirements-deploy.txt

# 2. 데스크톱 앱 실행
python desktop_chord_studio.py

# 또는 웹 브라우저 모드 실행
python chord_studio_v2/server_v2.py --port 8766 --open
```

### 3. 유닛 및 통합 테스트 실행
```powershell
# 파이썬 유닛 테스트 (326개 항목)
python -m unittest discover tests

# 프론트엔드 계약 검증 테스트
node tests/test_chord_web_ui.js
```

---

## 📚 개발일지 및 기술 문서 (Devlogs & Technical Docs)

프로젝트 진행 과정에서 작성된 모든 연구 일지, 벤치마크 성적표, 설계 스키마는 [00_프로젝트_개발일지_및_전체문서_총괄_마스터.md](00_프로젝트_개발일지_및_전체문서_총괄_마스터.md)에서 확인하실 수 있습니다:
* **2026-11-03**: 가상 현 격자, 손 좌표계, 모델 파이프라인 착수
* **2026-11-04**: 손 해부학적 유효성(Anatomical Validity) 및 바레 코드 처리
* **2026-11-05**: Basic Pitch ONNX 격리 연동, GuitarSet 180곡 벤치마크, 웹앱 1차 릴리즈
* **2026-11-06**: Look-Ahead v2 알고리즘 도입, 코드 깜빡임 36.7% 개선, 326개 테스트 통과
* **2026-11-07**: 네이티브 데스크톱 단독 앱 변환, MediaPipe C++ DLL 복원, 비전 인디케이터 및 405MB 무설치 배포본 빌드
