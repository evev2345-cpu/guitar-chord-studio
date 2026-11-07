import os
import shutil
import zipfile
from pathlib import Path
import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def build_bundle():
    root = Path('E:/GUITAR')
    docs_src = root / 'docs'
    artifacts_src = Path(r'C:\Users\evev2\.gemini\antigravity\brain\4d6a6d70-1263-4f56-a0a9-6c2b7fea1875')
    bundle_dir = root / 'ChordStudio_전체_개발문서_모음'
    
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir, ignore_errors=True)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    dirs = {
        '01_개발일지_및_타임라인': bundle_dir / '01_개발일지_및_타임라인',
        '02_사용자설명서_및_가이드': bundle_dir / '02_사용자설명서_및_가이드',
        '03_오디오_및_화성분석_연구': bundle_dir / '03_오디오_및_화성분석_연구',
        '04_컴퓨터비전_및_지판추적_연구': bundle_dir / '04_컴퓨터비전_및_지판추적_연구',
        '05_UI_UX_디자인_및_배포': bundle_dir / '05_UI_UX_디자인_및_배포',
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
        
    print("1. Categorizing and copying documents...")
    
    # Category 1: Devlogs
    devlog_keywords = ['DEVLOG', 'WORK_', 'NEXT_TASKS', 'DEVELOPMENT_DIRECTIVE', 'WORK_PLAN']
    # Category 2: Manuals
    manual_files = ['README.md', 'REPORTING_GUIDELINES.md', 'REPOSITORY_SETUP.md', '사용자_설명서.md', 'ChordStudio_v2.0_사용자_매뉴얼.docx']
    # Category 4: Vision
    vision_keywords = ['HAND', 'FRET', 'VISION', 'SKELETON', 'BARRE', 'VIRTUAL', 'FRAME', 'NUT_', 'LOW_STRING_HAND', 'LOW_STRING_ROOT', 'VISUAL_ROOT', 'JOINT_FAILURE']
    # Category 5: UI & Deployment
    ui_deploy_keywords = ['LAYOUT', 'LOOKAHEAD', 'MOCKUP', 'DEPLOY', 'AUDIT', 'CLEANUP', 'INVENTORY']
    
    copied_counts = {k: 0 for k in dirs}
    
    # Process docs_src
    for f in docs_src.glob('*'):
        fname = f.name
        if not f.is_file():
            continue
            
        target_dir = None
        if any(k in fname for k in devlog_keywords):
            target_dir = dirs['01_개발일지_및_타임라인']
        elif fname in manual_files:
            target_dir = dirs['02_사용자설명서_및_가이드']
        elif any(k in fname for k in vision_keywords):
            target_dir = dirs['04_컴퓨터비전_및_지판추적_연구']
        elif any(k in fname.upper() for k in ui_deploy_keywords):
            target_dir = dirs['05_UI_UX_디자인_및_배포']
        else:
            # Default to Audio/Harmony
            target_dir = dirs['03_오디오_및_화성분석_연구']
            
        shutil.copy2(f, target_dir / fname)
        for dname, dpath in dirs.items():
            if target_dir == dpath:
                copied_counts[dname] += 1

    # Include root manual files & artifacts
    if (root / 'ChordStudio_v2.0_사용자_매뉴얼.docx').exists():
        shutil.copy2(root / 'ChordStudio_v2.0_사용자_매뉴얼.docx', dirs['02_사용자설명서_및_가이드'] / 'ChordStudio_v2.0_사용자_매뉴얼.docx')
        copied_counts['02_사용자설명서_및_가이드'] += 1
    if (root / 'dist' / 'GuitarChordStudio' / '사용자_설명서.md').exists():
        shutil.copy2(root / 'dist' / 'GuitarChordStudio' / '사용자_설명서.md', dirs['02_사용자설명서_및_가이드'] / '사용자_설명서.md')
        copied_counts['02_사용자설명서_및_가이드'] += 1
    if (root / 'README.md').exists() and not (dirs['02_사용자설명서_및_가이드'] / 'README.md').exists():
        shutil.copy2(root / 'README.md', dirs['02_사용자설명서_및_가이드'] / 'README.md')
        copied_counts['02_사용자설명서_및_가이드'] += 1

    # Artifacts (mockups, layout proposals, reports)
    for art in artifacts_src.glob('*'):
        if art.is_file() and not art.name.endswith('.metadata.json') and not art.name.endswith('.log'):
            if art.suffix in ['.html', '.md']:
                shutil.copy2(art, dirs['05_UI_UX_디자인_및_배포'] / art.name)
                copied_counts['05_UI_UX_디자인_및_배포'] += 1

    for k, v in copied_counts.items():
        print(f"  - {k}: {v} files")

    # Generate 00 Master Markdown
    print("2. Generating Master Markdown Index...")
    master_md_path = bundle_dir / '00_프로젝트_개발일지_및_전체문서_총괄_마스터.md'
    
    master_md_content = f"""# Chord Studio v2.0 개발일지 및 프로젝트 전체 문서 총괄 마스터

본 문서는 **Chord Studio (Guitar Chord Studio v2.0)** 프로젝트의 초기 프로토타입 설계부터 음향 AI 모델링, 컴퓨터 비전 지판 추적 연구, 웹앱 개발, 네이티브 데스크톱 단독 실행 앱(Standalone Desktop Executable) 전환 및 공식 배포에 이르는 **전체 개발 역사, 핵심 기술 아키텍처, 일자별 개발일지 요약, 그리고 보관된 80여 건의 전문 문서 색인(Index)**을 총망라한 종합 보고서입니다.

---

## 1. 프로젝트 개요 (Executive Summary)

* **프로젝트명**: Chord Studio (Guitar Chord Studio v2.0)
* **목표**: 
  1. 음원(MP3, WAV) 및 연주 영상(MP4)으로부터 **기타 트랙 분리 및 16박자 단위 정밀 기타 코드 악보 자동 추출**.
  2. 영상 분석을 통한 **기타 지판 4점 캘리브레이션 및 연주자의 손가락 골격(21 Keypoints) 프레임별 실시간 추적**.
  3. 사용자가 마우스 클릭으로 코드를 즉각 수정·편집하고 박자(BPM)와 첫박 오프셋을 조절할 수 있는 **직관적인 인터랙티브 스튜디오 워크스페이스**.
  4. 파이썬이나 별도 라이브러리 설치가 전혀 필요 없는 **100% 완전 무설치 단독 실행 데스크톱 애플리케이션(Standalone Windows App)** 완성.
* **최종 배포본**: `GuitarChordStudio_v2.0_Windows.zip` (405.11 MB, Python 3.10 내장, MediaPipe C++ DLL, ONNX Runtime, FFMpeg 번들)

---

## 2. 핵심 기술 아키텍처 (Core Technical Architecture)

### 2.1 음향 AI 및 화성 분석 엔진 (Audio & Harmony Engine)
* **음원 분리 (Stem Separation)**: `htdemucs_6s` (Demucs v4 6-stem) 딥러닝 모델을 활용하여 보컬, 드럼, 베이스 등 복잡한 믹스에서 기타 단독 트랙(`guitar.wav`)을 자동 추출, 코드 인식 노이즈를 획기적으로 개선.
* **기본음 및 활성도 추론**: Spotify의 `Basic Pitch (v0.4.0)` ONNX 모델을 기반으로 오디오의 프레임별 피치 활성도(Pitch Salience) 및 온셋(Onset) 확률 맵 추출.
* **화성 문맥 및 16박자 격자 (Adaptive Grid)**:
  * 0.2초 / 0.4초 적응형 분석 윈도우.
  * 오프라인 선확인(Look-Ahead Confirmation v2, `confirm_s = 0.25s`) 알고리즘을 도입하여 초단기 코드 깜빡임 36.7% 감소.
  * 동일 루트 확장음(`6`, `add9`, `sus2`, `sus4`, `maj7`) 샌드위치 통합 및 물리적 저음 전위(Bass Inversion) 분수코드(`D/F#` 등) 정밀 복원.
  * 카포(Capo 0~12) 설정에 따른 실음(Concert Pitch)과 운지음(Shape) 실시간 상호 변환.

### 2.2 컴퓨터 비전 및 지판 추적 엔진 (Computer Vision Engine)
* **사용자 주도 4점 지판 캘리브레이션**:
  * 1번 줄 너트 → 6번 줄 너트 → 6번 줄 브릿지 → 1번 줄 브릿지 4점을 사용자가 클릭하여 기타 지판의 원근 투영 변환(Perspective Homography) 행렬 도출.
  * 프렛 지오메트리 수식(Ln = L * (1 - 2^(-n/12)))을 적용한 가상 프렛 그리드 자동 분할.
* **MediaPipe C++ 손가락 스켈레톤 추적**:
  * 구글 `MediaPipe Hand Landmarker` C++ 바이너리(`libmediapipe.dll`, 68MB)를 연동하여 연주자의 왼손 21개 관절 좌표를 영상 전체 프레임에 걸쳐 백그라운드 추적.
  * 해부학적 유효성 검증(Hand Anatomical Validity) 및 저음현 근음 우선 가점(Low-String Root Prior) 적용.
* **실시간 상태 인디케이터**: 스튜디오 상단 툴바에 백그라운드 프레임 추적 진행률(`⏳ 지판 비전 분석 중 (0%~100%)`) 및 완료 상태(`✓ 지판 비전 활성`)를 시각화.

### 2.3 데스크톱 단독 실행 셸 및 영구 보존 구조 (Desktop Shell & Persistence)
* **Microsoft Edge WebView2 백엔드**: Windows 10/11의 하드웨어 가속을 활용하여 MP4 H.264/AAC 고화질 비디오를 부드럽게 재생.
* **무소음 백그라운드 프로세싱**: `ffprobe`, `ffmpeg` 호출 시 Windows 콘솔 창 깜빡임을 완전 차단(`CREATE_NO_WINDOW`, `SW_HIDE`).
* **영구 보관함 (History Archive)**:
  * 모든 분석 결과, 분리 음원, 수정된 코드, 비전 오버레이는 `_internal/chord_studio_v2/runs/<job_id>/`에 영구 기록.
  * 앱을 껐다 켜도 0.1초 만에 재분석 없이 이전 작업 즉시 복원.
  * 보관함 목록에 `✓ 음성 완료` / `✓ 비전 완료` 배지를 분리 제공하여 한눈에 작업 완료 상태 파악 가능.

---

## 3. 일자별 개발일지 종합 요약 (Chronological Devlog Summary)

### 📅 2026-11-03: 프로젝트 착수 및 지판·비전 가상화 기초 수립
* 가상 현-프렛 그리드(`virtual_string_grid.py`) 스키마 및 손가락 관절 분포(`hand_cell_distribution.py`) 정의.
* MediaPipe 손 인식 좌표계와 기타 지판 사이의 텍스처 정합 및 프로젝션 수식 구현.
* 오디오 모델 의존성 분리 및 음향-비전 융합 스키마(`CELL_AUDIO_FUSION_SCHEMA.md`) 수립.

### 📅 2026-11-04: 손 해부학 유효성 검증 및 바레(Barre) 코드 처리
* 연주자의 손가락 뒤틀림 방지를 위한 관절 각도 제약 및 해부학적 유효성 필터 도입.
* 6번 줄을 가로지르는 검지 바레 코드(F, Bm 등)의 스켈레톤 검출 개선.
* 프레임 간 손 추적 불안정 구간을 완화하는 중간 시간 보간(Temporal Smoothing) 필터 구축.

### 📅 2026-11-05: Basic Pitch 모델 통합, 화성 문맥 및 Chord Studio 웹앱 1차 구현
* Basic Pitch 0.4.0 ONNX 모델을 로컬 환경에 완벽 격리 연동.
* GuitarSet 180곡 벤치마크 및 EGDB 일렉기타 앰프 음색별(Fender Twins, Marshall, Mesa) 코드 인식 민감도 비교.
* 음향 모델의 피치 활성도와 비전 저음현 가점을 결합하여 214초 B6/G#m7 동점 처리 성공.
* Chord Studio 로컬 웹 서버(`server_v2.py`) 및 인터랙티브 웹 UI 1차 릴리즈.

### 📅 2026-11-06: 불필요한 크롬 확장 정리, Look-Ahead v2 알고리즘 및 UI 고도화
* 복잡도를 높이던 크롬 확장 프로그램 모듈을 전면 제거하고 로컬 독립 스튜디오 구조로 일원화.
* 326개 전체 단위 테스트 통과 및 Mela 실곡 검증.
* 오프라인 선확인(Look-Ahead v2)을 적용하여 코드 깜빡임 36.7% 제거 및 `D/F#` 등 분수코드 복원율 대폭 향상.
* 모바일 및 태블릿 반응형 뷰포트 최적화 설계.

### 📅 2026-11-07: 네이티브 단독 실행 앱(Standalone) 패키징, MediaPipe C++ 복원 및 최종 배포
* PyWebView + Edge WebView2 네이티브 데스크톱 단독 실행 바이너리(`GuitarChordStudio.exe`) 완성.
* MediaPipe C++ 라이브러리(`libmediapipe.dll`, 68MB) 및 누락된 비전 연산 9개 모듈 복구.
* 서브프로세스 콘솔 검은 창 깜빡임 전면 제거 및 중복 창 버그 해결.
* 1024x1024 고해상도 투명 아이콘 리마스터 및 바탕화면 바로가기 생성.
* 상단 실시간 지판 비전 인디케이터 및 분석 보관함 `✓ 음성 완료` / `✓ 비전 완료` 2종 배지 분리.
* 405MB 공식 무설치 배포 패키지(`GuitarChordStudio_v2.0_Windows.zip`) 및 고화질 설명서(`DOCX`) 최종 릴리즈.

---

## 4. 보관된 프로젝트 전체 문서 목록 및 색인 (Document Inventory)

모든 문서는 테마별로 5개 폴더에 정리되어 있습니다:

### 📁 01_개발일지_및_타임라인 (Devlogs & Timeline)
1. `DEVLOG_2026-11-03.md`: 가상 현 격자, 손 좌표계, 모델 파이프라인 착수 일지
2. `DEVLOG_2026-11-03_END_OF_DAY.md`: 11월 3일 작업 마감 및 기술적 결론
3. `WORK_START_2026-11-04.md`: 11월 4일 작업 시작 방향 및 검증 체크리스트
4. `DEVLOG_2026-11-05_END_OF_DAY.md`: 음향 벤치마크, 앰프 음색 비교, 웹앱 1차 릴리즈 마감 일지
5. `DEVLOG_2026-11-06.md`: 크롬 확장 제거, Look-Ahead v2 도입, 단위 테스트 326개 통과 일지
6. `DEVLOG_2026-11-07_FINAL_RELEASE.md`: 데스크톱 단독 앱 패키징, MediaPipe C++ 해결, 최종 배포 일지
7. `DEVELOPMENT_DIRECTIVE.md`: 프로젝트 기본 개발 지침 및 아키텍처 원칙
8. `NEXT_TASKS_2026-11-03.md`: 우선순위 백로그 및 로드맵
9. `AUDIO_WORK_PLAN.md`: 오디오 피치 추출 및 코드 판단 로드맵
10. `HARMONY_WORK_PLAN.md`: 화성학적 문맥 보정 및 7화음 처리 계획서
11. `VIRTUAL_STRING_GRID_WORK_PLAN.md`: 지판 4점 투영 및 프렛 분할 알고리즘 작업 계획서

### 📁 02_사용자설명서_및_가이드 (Manuals & Guides)
1. `ChordStudio_v2.0_사용자_매뉴얼.docx`: 실제 프로그램 스크린샷 4장이 수록된 공식 사용자 매뉴얼
2. `사용자_설명서.md`: 마크다운 형식의 상세 조작 및 배포 가이드
3. `README.md`: 프로젝트 소개 및 주요 기능 요약
4. `REPORTING_GUIDELINES.md`: 분석 리포트 및 지표 측정 작성 규칙
5. `REPOSITORY_SETUP.md`: 가상환경, C++ 의존성, FFMpeg 설치 및 빌드 가이드

### 📁 03_오디오_및_화성분석_연구 (Audio & Harmony Research - 32편)
* `AUDIO_SCHEMA.md`: 오디오 피치 및 온셋 데이터 구조 스키마
* `AUDIO_CELL_SCHEMA.md`: 프렛 셀과 오디오 피치클래스 매핑 정의
* `HARMONY_SCHEMA.md`: 코드 및 조표(Key) 사전 스키마
* `CELL_AUDIO_FUSION_SCHEMA.md`: 음향-비전 멀티모달 결합 가중치 공식
* `BASIC_PITCH_MODEL_REVIEW_2026-11-05.md`: Basic Pitch ONNX 추론 정확도 및 자원 소모 검증
* `AUDIO_SEPARATION_INSTALL_2026-11-03.md`: Demucs 기타 분리 환경 격리 구축 보고서
* `AUDIO_NOTE_CALIBRATION_TRAINING_2026-11-05.md`: 음후보 잔차 보정 모델 학습 및 평가
* `BANDCUT_VISION_WEIGHT_SWEEP_2026-11-05.md`: 주파수 대역 컷 및 비전 가중치 스윕 실험
* `CHANGE_AWARE_AUDIO_REVIEW_2026-11-05.md`: 코드 변화 경계 기반 적응형 시간창 실험
* `CHORD_DISPLAY_CLEANUP_2026-11-05.md`: 초단기 튐 현상 정리 및 v2 스무딩 필터 보고서
* `CHORD_PRESENTATION_2026-11-05.md`: 분수코드 분모 분리 및 안정적 표시 개선안
* `CUT_AUDIO_FEATURE_COMPARISON_2026-11-05.md`: D2~E6 파형 대역 제한에 따른 음 추출 비교
* `EGDB_TIMBRE_REVIEW_2026-11-05.md`: 일렉기타 앰프 음색별(Fender/Marshall/Mesa) 영향 평가
* `FINGERING_AUDIO_REVIEW_2026-11-03.md`: 운지법과 실제 소리의 불일치 보정 분석
* `GUITARSET_AUDIO_READY_2026-11-05.md`: GuitarSet 360개 오디오와 주석 연결 검증
* `GUITARSET_BASELINE_BENCHMARK_2026-11-05.md`: GuitarSet 180곡(1.52시간) 기준 성적표
* `GUITAR_STEM_ACCURACY_COMPARISON_2026-11-05.md`: 원음 대비 기타 단독 트랙 분리 시 코드 정확도 비교
* `HARMONIC_CONTEXT_2026-11-05.md`: 키 추정과 저음 지속 가점에 따른 화성 보정 보고서
* `HARMONIC_SEVENTH_EXPERIMENT_2026-11-05.md`: 배음 NNLS를 활용한 7화음(maj7, m7, dom7) 추출 실험
* `IDMT_CHORDS_SCORING_REVIEW_2026-11-05.md`: IDMT-SMT-Chords 7,398개 구간 벤치마크
* `LOOKAHEAD_CONFIRMATION_2026-11-06.md`: 오프라인 0.25초 선확인 v2 알고리즘 보고서
* `ONSET_TRANSITION_2026-11-05.md`: 온셋 확률 기반 코드 전환 타이밍 동기화 보고서
* `ORACLE_CHORD_DIAGNOSIS_2026-11-05.md`: 정답 피치 주입 시 코드 모델 한계 진단
* `REFERENCE_DATASET_AUDIT_2026-11-05.md`: 연구용 레퍼런스 데이터셋 무결성 감사 보고서
* `ROBUST_CANDIDATES_2026-11-03.md`: 노이즈 환경 코드 후보군 추출 내구성 분석
* `TEMPORAL_AUDIO_WINDOW_REVIEW_2026-11-05.md`: 0.1s ~ 0.8s 시간창 크기별 정밀도 비교
* `TUTORIAL_GROUND_TRUTH_COMPARISON_2026-11-05.md`: 튜토리얼 10초 영상 기준 정답 비교 검증

### 📁 04_컴퓨터비전_및_지판추적_연구 (Computer Vision & Fretboard Tracking - 25편)
* `FRETBOARD_SCHEMA_2026-11-03.md`: 4점 지판 모서리 및 프렛 지오메트리 스키마
* `FRETBOARD_SEMANTIC_SCHEMA_2026-11-03.md`: 현-프렛 셀의 의미적 좌표 매핑 규칙
* `FRETBOARD_HANDOFF_2026-11-03.md`: 지판 추적 좌표 전달 인터페이스
* `VIRTUAL_STRING_GRID_SCHEMA_2026-11-03.md`: 가상 6현 및 22프렛 격자 생성 수식
* `HAND_CELL_DISTRIBUTION_SCHEMA_2026-11-03.md`: 손가락 끝 위치의 프렛 셀 소속 확률 공식
* `HAND_CELL_DISTRIBUTION_REPORT_2026-11-03.md`: 지판 위 손가락 셀 분포 측정 리포트
* `HAND_DELIVERABLES_2026-11-03.md`: 비전 엔진 1단계 산출물 정의
* `HAND_REPORTING_AUTHORIZATION.md`: 손가락 추적 데이터 보고 권한 및 규약
* `HAND_ANATOMICAL_VALIDITY_SCHEMA_2026-11-04.md`: 손 관절 기하학적 유효성 판정식
* `HAND_ANATOMICAL_VALIDITY_REPORT_2026-11-04.md`: 비정상 손 뒤틀림 필터링 검증 결과
* `HAND_SKELETON_IMPROVEMENT_2026-11-04.md`: 손 스켈레톤 지터(Jitter) 감소 개선안
* `HAND_DIRECTION_BONUS_2026-11-04.md`: 손목-손가락 방향 벡터에 따른 지판 가점
* `BARRE_SKELETON_REVIEW_2026-11-04.md`: 검지 바레(Barre) 폼 인식률 개선 연구
* `GLOBAL_HAND_SELECTION_2026-11-04.md`: 복수 손 검출 시 왼손(Fretting Hand) 선별 규칙
* `NATIVE_FIRST_HAND_REVIEW_2026-11-04.md`: 네이티브 해상도 직접 추론 성능 평가
* `NUT_PRIOR_HAND_GROUPS_2026-11-04.md`: 너트 근처 포지션의 사전 확률 적용 분석
* `MIDDLE_TEMPORAL_REVIEW_2026-11-04.md`: 프레임 간 중간 시간축 연속성 검증
* `FRAME4823_NEIGHBORS_2026-11-04.md`: 특정 프레임(4823) 주변부 오인식 심층 진단
* `JOINT_FAILURE_DIAGNOSIS_2026-11-03.md`: 손 관절 결측 시 대체 보간 로직 진단
* `LOW_STRING_HAND_STABILITY_2026-11-05.md`: 6번/5번 저음현 손가락 접촉 안정화 리포트
* `LOW_STRING_ROOT_PRIOR_2026-11-05.md`: 저음현 운지 감지 시 근음 우선권 부여 규칙
* `VISUAL_ROOT_TIE_REVIEW_2026-11-05.md`: 음향 동점 발생 시 비전 근음으로 해결한 사례 분석
* `WEB_VISION_INTEGRATION_2026-11-05.md`: 웹 캔버스 위 가상 지판 및 손 실시간 오버레이 연동

### 📁 05_UI_UX_디자인_및_배포 (UI/UX & Deployment - 10편)
* `layout_proposals.md`: 듀얼 뷰 스튜디오 및 상단 컨트롤 바 반응형 레이아웃 제안서
* `lookahead_verification_report.md`: 실시간 파형 스크롤과 코드 싱크 검증 보고서
* `chord_diagram_horizontal_mockup.html`: 수평형 코드 다이어그램 UI 프로토타입
* `mobile_layout_proposal.html`: 모바일 세로/가로 모드 UI 프로토타입
* `mobile_top_fix_preview.html`: 모바일 상단 네비게이션 고정 뷰 프리뷰
* `live_deployment.html`: 로컬 서버 및 클라우드플레어 터널 원격 접속 가이드
* `audit_snapshot.json` / `CLEANUP_2026-11-04.json` / `file_inventory.csv`: 코드 및 에셋 감사 스냅샷

---

## 5. 결론 및 향후 유지보수 가이드

Chord Studio v2.0은 AI 음향 분석과 컴퓨터 비전 지판 추적, 직관적인 악보 에디터, 그리고 100% 독립 실행 데스크톱 바이너리 패키징까지 모두 성공적으로 결합되었습니다.

* **배포 파일 유지**: `dist/GuitarChordStudio_v2.0_Windows.zip` (405 MB) 하나로 모든 사용자 배포가 완결됩니다.
* **사용자 데이터 보존**: 프로그램 종료 및 재시작 시에도 `_internal/chord_studio_v2/runs/`에 모든 사용자 분석 및 수정 내역이 영구적으로 보존됩니다.
* **기술 문서 보존**: 본 압축 패키지(`ChordStudio_전체_개발문서_모음.zip`)는 프로젝트의 모든 알고리즘, 실험 데이터, 벤치마크, 설계 명세서를 완벽하게 보존하고 있으므로, 향후 기능 확장 및 연구 개발 시 참조 기준이 됩니다.
"""

    master_md_path.write_text(master_md_content, encoding='utf-8')
    (root / '00_프로젝트_개발일지_및_전체문서_총괄_마스터.md').write_text(master_md_content, encoding='utf-8')
    print("Master Markdown generated successfully!")

    # Generate 00 Master DOCX
    print("3. Generating Master DOCX Document...")
    master_docx_path = bundle_dir / '00_프로젝트_개발일지_및_전체문서_총괄_마스터.docx'
    
    doc = Document()
    for s in doc.sections:
        s.top_margin = Inches(0.8)
        s.bottom_margin = Inches(0.8)
        s.left_margin = Inches(0.9)
        s.right_margin = Inches(0.9)
        
    style_normal = doc.styles['Normal']
    style_normal.font.name = '맑은 고딕'
    style_normal.font.size = Pt(10)
    style_normal.font.color.rgb = RGBColor(30, 41, 59)
    style_normal.paragraph_format.line_spacing = 1.25
    style_normal.paragraph_format.space_after = Pt(4)
    
    # Title
    p_t = doc.add_paragraph()
    p_t.paragraph_format.space_before = Pt(10)
    p_t.paragraph_format.space_after = Pt(2)
    r_t = p_t.add_run("Chord Studio v2.0 개발일지 및 프로젝트 문서 총괄 보고서")
    r_t.bold = True
    r_t.font.size = Pt(20)
    r_t.font.color.rgb = RGBColor(15, 23, 42)
    
    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_after = Pt(12)
    r_sub = p_sub.add_run("AI 기반 음향 분석, 컴퓨터 비전 지판 추적, 데스크톱 단독 앱 패키징 및 전체 80여 건 문서 종합 색인")
    r_sub.font.size = Pt(11)
    r_sub.font.color.rgb = RGBColor(100, 116, 139)
    
    doc.add_paragraph("—" * 50).paragraph_format.space_after = Pt(10)
    
    def add_heading_styled(doc, text, level):
        h = doc.add_heading(text, level=level)
        h.paragraph_format.space_before = Pt(12)
        h.paragraph_format.space_after = Pt(4)
        for r in h.runs:
            r.font.name = '맑은 고딕'
            r.font.color.rgb = RGBColor(13, 148, 136) if level == 1 else RGBColor(30, 41, 59)
        return h

    add_heading_styled(doc, "1. 프로젝트 개요 (Executive Summary)", level=1)
    doc.add_paragraph(
        "• 프로젝트명: Chord Studio (Guitar Chord Studio v2.0)\n"
        "• 목표: AI 기타 트랙 분리 및 16박자 악보 추출, 4점 지판 캘리브레이션 및 3D 손가락 관절 추적, 마우스 클릭 코드 편집, 100% 완전 무설치 독립 실행형 데스크톱 앱 완성.\n"
        "• 최종 배포본: GuitarChordStudio_v2.0_Windows.zip (405.11 MB, Python 3.10, MediaPipe C++ DLL, ONNX Runtime, FFMpeg 번들)"
    )

    add_heading_styled(doc, "2. 핵심 기술 아키텍처", level=1)
    doc.add_paragraph(
        "1. 음향 AI & 화성 분석: htdemucs_6s 6-stem 분리 모델로 기타 단독 트랙 추출. Spotify Basic Pitch 0.4.0 ONNX 모델로 피치 활성도 추론. 오프라인 선확인(Look-Ahead v2)으로 초단기 코드 깜빡임 36.7% 제거 및 D/F# 등 분수코드 복원.\n"
        "2. 컴퓨터 비전 & 지판 추적: 사용자 4점 모서리 클릭으로 지판 원근 투영 변환(Homography) 및 프렛 그리드 생성. 구글 MediaPipe Hand Landmarker C++ 동적 라이브러리(libmediapipe.dll)로 왼손 21개 관절 전 프레임 백그라운드 추적.\n"
        "3. 데스크톱 단독 실행 셸: Microsoft Edge WebView2 엔진 기반 H.264 하드웨어 가속. 콘솔 깜빡임 없는 무소음 서브프로세스 구동. 디스크 영구 저장소 기반으로 앱 재시작 시 0.1초 만에 악보 및 비전 즉시 복원."
    )

    add_heading_styled(doc, "3. 일자별 개발일지 타임라인 (Nov 3 ~ Nov 7)", level=1)
    timeline_data = [
        ("2026-11-03", "프로젝트 착수, 가상 현-프렛 그리드(virtual_string_grid) 스키마 정의, MediaPipe 손 인식 텍스처 정합, 음향-비전 융합 스키마 수립"),
        ("2026-11-04", "손 해부학적 유효성(Anatomical Validity) 제약식 도입, 검지 바레(Barre) 코드 스켈레톤 인식률 개선, 프레임 보간 필터 구축"),
        ("2026-11-05", "Basic Pitch 0.4.0 ONNX 로컬 격리 연동, GuitarSet 180곡 벤치마크, 앰프 음색별(Fender/Marshall/Mesa) 영향 평가, 웹앱 1차 릴리즈"),
        ("2026-11-06", "크롬 확장 전면 제거 및 단일 로컬 스튜디오 일원화, Look-Ahead v2 도입으로 코드 깜빡임 36.7% 제거, 단위 테스트 326개 통과"),
        ("2026-11-07", "PyWebView 데스크톱 단독 앱 변환, MediaPipe C++ DLL 번들링 결함 해결, 비전 인디케이터 및 음성/비전 완료 배지 분리, 405MB 무설치 ZIP 및 DOCX 설명서 최종 배포")
    ]
    t = doc.add_table(rows=len(timeline_data) + 1, cols=2)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    
    # Header
    for c_i, h_t in enumerate(["일자", "주요 개발 및 마일스톤 내역"]):
        c = t.rows[0].cells[c_i]
        c.text = h_t
        c.width = Inches(1.5) if c_i == 0 else Inches(4.8)
        set_cell_background(c, "0F172A")
        set_cell_margins(c, top=80, bottom=80, left=100, right=100)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.bold = True
            r.font.size = Pt(9.5)
            r.font.color.rgb = RGBColor(255, 255, 255)
            
    for row_idx, (dt, desc) in enumerate(timeline_data, start=1):
        row = t.rows[row_idx]
        bg = "F8FAFC" if row_idx % 2 == 1 else "FFFFFF"
        for col_idx, text in enumerate([dt, desc]):
            c = row.cells[col_idx]
            c.text = text
            c.width = Inches(1.5) if col_idx == 0 else Inches(4.8)
            set_cell_background(c, bg)
            set_cell_margins(c, top=60, bottom=60, left=100, right=100)
            p = c.paragraphs[0]
            if col_idx == 0:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.runs[0].font.bold = True
                p.runs[0].font.size = Pt(9)
                p.runs[0].font.color.rgb = RGBColor(13, 148, 136)
            else:
                p.runs[0].font.size = Pt(8.5)
                p.runs[0].font.color.rgb = RGBColor(51, 65, 85)

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    add_heading_styled(doc, "4. 테마별 보관 문서 목록 (총 80여 건)", level=1)
    doc.add_paragraph(
        "• 01_개발일지_및_타임라인 (11건): 일자별 개발일지(11/3~11/7), 개발 지침서, 작업 계획서\n"
        "• 02_사용자설명서_및_가이드 (5건): 공식 DOCX 매뉴얼(스크린샷 4컷 수록), README, 설치 및 빌드 가이드\n"
        "• 03_오디오_및_화성분석_연구 (32건): Basic Pitch 모델 리뷰, Demucs 기타 분리 비교, GuitarSet 벤치마크, 앰프 음색 영향, 화성 스키마\n"
        "• 04_컴퓨터비전_및_지판추적_연구 (25건): 가상 지판 격자, MediaPipe 손가락 관절 추적, 바레 코드 분석, 저음현 근음 우선 가점\n"
        "• 05_UI_UX_디자인_및_배포 (10건): 듀얼 뷰 스튜디오 레이아웃 제안, 모바일 반응형 뷰, 감사 스냅샷"
    )

    doc.save(str(master_docx_path))
    doc.save(str(root / '00_프로젝트_개발일지_및_전체문서_총괄_마스터.docx'))
    print("Master DOCX generated successfully!")

    # 4. Create ZIP of the bundle
    print("4. Compressing bundle into ZIP...")
    zip_out = root / 'ChordStudio_전체_개발문서_모음.zip'
    if zip_out.exists():
        zip_out.unlink()

    with zipfile.ZipFile(zip_out, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for file_path in bundle_dir.rglob('*'):
            if file_path.is_file():
                arcname = file_path.relative_to(bundle_dir.parent)
                zf.write(file_path, arcname)

    print(f"5. Complete! Documentation Bundle ZIP created: {zip_out} ({zip_out.stat().st_size / (1024*1024):.2f} MB)")

if __name__ == "__main__":
    build_bundle()
