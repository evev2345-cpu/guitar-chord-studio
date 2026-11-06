---
title: Guitar Lab Chord Studio
emoji: 🎸
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
---

# Guitar Lab — Chord Studio v2

전체 음원에서 기타 트랙을 고품질(htdemucs_6s)로 분리하고, 16박자 비트 격자에 맞춘 정교한 코드 진행 분석과 인터랙티브 DAW 뷰를 제공하는 AI 기타 코드 분석기입니다.

## ✨ 주요 기능
- **AI 6-Stem 기타 트랙 분리**: htdemucs_6s 모델을 활용하여 보컬, 드럼, 베이스 등으로부터 기타 단독 연주 트랙 분리 분석
- **16박자 스마트 비트 격자(Quantized Beat Grid)**: 마디 단위 자동 템포(BPM) 및 위상 오프셋 정렬
- **실시간 리드 시트 & 2D 인터랙티브 지판**: 재생 동기화 및 카포/조성 운지 변환 지원
- **사용자 코드 교정 & 저장**: 오분석 구간을 웹 UI에서 직접 클릭하여 실시간 수정 및 영구 보존
- **사용자 직접 4점 지판 캘리브레이션**: 비전 트래킹을 위한 손쉬운 지판 4포인트 매핑

## 📁 프로젝트 구조 (Clean Architecture)

```
GUITAR/
├── chord_studio_v2/       # Chord Studio v2 웹 어플리케이션
│   ├── server_v2.py       # 메인 웹/API 서버 (포트 8766 / 7860)
│   ├── static/            # 모던 스튜디오 UI (index.html, app.js, style.css)
│   └── vision_profiles/   # 지판 캘리브레이션 프로필
├── engine/                # 핵심 분석 및 인퍼런스 엔진
│   ├── harmony_engine.py  # 크로마 풀링, 코드 템플릿 매칭 & 스코어링
│   ├── harmonic_context.py# 조성 추정 및 전체 음원 앵커링 보정
│   ├── chord_presentation.py # 코드 표시 안정화 및 시간축 리드 시트 정돈
│   ├── beat_grid.py       # 16박자 템포 추정 및 격자 정렬
│   ├── onset_transition.py# 온셋 전환 감지
│   ├── run_local_separation.py # 로컬 Demucs 6-stem 음원 분리
│   └── basic_pitch_worker.py   # Basic Pitch 음 전사 워커
├── models/                # AI 모델 가중치 파일
│   └── hand_landmarker.task
├── dataset/               # 검증 및 튜토리얼 데모 데이터
├── tests/                 # 유닛 테스트 & 계약 테스트 모음
│   ├── test_chord_presentation.py
│   ├── test_full_mix_anchor.py
│   ├── test_studio_v2.py
│   └── test_chord_web_ui.js
├── Dockerfile             # Docker 배포 설정 (Hugging Face / 클라우드 지원)
├── docker-compose.yml     # Docker Compose 설정
├── deploy_oracle_ubuntu.sh# 오라클 클라우드 우분투 1-Click 자동 배포 스크립트
├── requirements-deploy.txt# 경량 배포용 패키지 목록
└── docs/                  # 연구/개발 일지 (로컬 보존)
```

## 🚀 빠른 시작

### 1. 로컬 개발 환경 실행
```powershell
python chord_studio_v2/server_v2.py --port 8766 --open
```

### 2. 테스트 실행
```powershell
# 파이썬 유닛 테스트
python -m unittest discover tests

# 프론트엔드 계약 검증 테스트
node tests/test_chord_web_ui.js
```

### 3. Docker 배포
```bash
docker compose up --build
```
