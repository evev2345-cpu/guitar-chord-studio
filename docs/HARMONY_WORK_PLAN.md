# 화성 해석 담당 작업계획서

작성일: 2026-11-02. 첫 마일스톤: 기타 코드(chord) 후보 분석기. 이후 TAB으로 확장한다.

## 착수 지시

기존 지판·손 담당의 완료를 기다리지 말고 독립 규칙 엔진부터 구현한다. 먼저 관련 파일을 읽고, 입력·출력 예시와 최소 실행 가능한 CLI를 만든 뒤 작은 검증 사례로 정확성을 확인한다. 현재 목표는 조성에 맞는 답을 추측하는 것이 아니라, 관측된 음·운지와 일치하는 코드 후보 및 불확실성을 제공하는 것이다.

프로젝트 루트: `C:\Users\evev2\Documents\antigravity\GUITAR`.

## 현재 자료와 제약

- 입력 영상: `sample video` 폴더의 튜토리얼 MP4. 현재 1개이며 약 266.9초, 1280×720, 24fps, AAC 44.1kHz 스테레오다. CLI는 영상 경로를 명시적으로 받는다.
- 화면에 TAB·코드명·다이어그램·Capo.1이 있다. 화면 표기는 평가 참조이며 시점별 접촉 정답은 아니다. 표시된 코드가 모양 이름인지 실음 이름인지 검수해야 한다.
- `README.md`, `docs/DEVELOPMENT_DIRECTIVE.md`, `dataset/chord_photo_validation/report.md`, `dataset/chord_video_review/cases.json`을 먼저 읽는다.
- 손 모듈은 위치 후보를 제공한다. 접촉·뮤트·개방·실제 발음은 확정되지 않았다. 영상 사례의 지판은 수동 근사 fixture이며 자동 검출 정확도의 증거가 아니다.
- 코너·현 담당의 파일과 JSON 형식이 개발 중이다. 입력 어댑터를 분리하고 기존 결과를 수정하지 않는다.

## 담당 범위와 소유 파일

신규 `harmony_engine.py`, `harmony_input_adapter.py`, `test_harmony_engine.py`, `docs/HARMONY_SCHEMA.md` 및 `dataset/harmony_analysis/`를 담당한다. 파일명이 이미 존재하면 읽고 충돌 여부를 확인한다.

지판·현 검출, MediaPipe, 오디오 특징 추출, 접촉 검출기는 구현하지 않는다. `two_stage_fret_pipeline.py`, `hand_fret_tracker.py`, `string_detector.py`, 공용 README를 다른 담당과 동시에 수정하지 않는다. 필요한 계약 변경은 자신의 스키마 문서와 보고서에 제안한다. API 호출·모델 학습·전역 환경 변경은 이 작업에 필요하지 않다.

## 단계 A: 음 계산 엔진

1. 현 번호는 6=Low E, 1=High E로 사용한다. 표준 튜닝의 MIDI 값은 6→1 순서 `[40,45,50,55,59,64]`다. 튜닝은 입력으로 받고, 미확인 표준 튜닝 가정은 메타데이터에 남긴다.
2. `physical_fret`는 원래 너트 기준, `relative_fret`는 카포 기준으로 구분한다. 카포가 c이면 상대 프렛 r의 실음은 `open_string_midi+c+r`, 물리 프렛 p의 실음은 `open_string_midi+p`다. 카포를 두 번 더하지 않는다.
3. 카포 기준 개방현은 상대 0·물리 c다. 카포 너머의 모호한 후보는 임의 보정하지 않는다. TAB의 X, 미연주, 음높이 불명은 정수 프렛 0으로 바꾸지 않는다.
4. 출력에 현, 두 프렛 기준, MIDI, pitch class, 음 이름, 튜닝·카포 출처를 남긴다. 이명동음은 내부 pitch class와 화면 표기를 분리한다.

## 단계 B: 코드 후보 엔진

최초 사전은 major, minor, 5, diminished, augmented, sus2, sus4, 6, m6, 7, maj7, m7, m7♭5, dim7, add9로 제한하고 정확한 음정 집합을 문서화한다. 9·11·13의 확장은 초기 사전·시험이 안정된 뒤 수행한다.

- 입력 음 집합과 후보의 일치음·누락음·추가음을 근거로 점수를 계산한다. 점수 구성과 가중치를 공개하고 0~1 수치를 보정된 확률로 부르지 않는다.
- 누락된 3도나 근음 때문에 여러 해석이 가능하면 모두 남긴다. 두 음·무음·잡음에 코드를 강제로 배정하지 않는다.
- 같은 음들의 옥타브 중복을 처리하되 베이스 옥타브 정보는 보존한다. 최저 검출음·가장 낮은 운지 가능음·확인된 베이스를 구분한다.
- 전위와 slash 표기는 확인 가능한 베이스가 있을 때 사용한다. 손에서 가능한 낮은 음을 실제로 울린 베이스로 확정하지 않는다.
- 상위 3개 후보와 근거·한계·unknown 이유를 출력한다. 코드 후보 순위에는 실제 관측과 음악적 사전 가정을 구분해서 기록한다.
- 조성·로마숫자·기능화성·진행 기반 보정은 다음 단계다. 단일 장면으로 조성을 확정하지 않는다.

## 단계 C: 불확실한 입력 연결

초기에는 수작업 음/MIDI 입력으로 독립 실행한다. 이후 오디오 담당 출력과 손 후보를 읽는 어댑터를 추가한다.

- 손끝 위치만으로 발음 음을 만들지 않는다. `possible_notes_from_fingering`과 `observed_audio_notes`를 별도 보존한다.
- 손의 위치 분포는 위치 가정에 따른 질량이며 접촉 확률이 아니다. 손가락마다 최고 후보를 독립 선택해 모두 합치는 방식은 피한다. 가능한 조합을 제한해 비교하고 사용한 탐색 한계를 기록한다.
- 오디오와 영상이 충돌하면 `evidence_conflict`로 남긴다. 화면 정답과 예상 코드에 맞추려고 관측을 수정하지 않는다.
- 현 상태 결합은 총괄 통합 단계의 책임이다. 이 담당은 후보 상태를 받아 화성 결과를 계산한다.

## 공통 교환 계약

스키마 제안 버전은 `guitar_evidence.v1`이다. 오디오 담당과 같은 키를 사용하고 자신의 어댑터에서 변환한다.

| 필드 | 의미 |
|---|---|
| `schema_version`, `run_id`, `source_id` | 버전·실행·원본 영상 SHA-256 식별자 |
| `start_s`, `end_s`, `timebase` | 원본 영상 재생 시간 기준 초, 구간 [start,end), timebase=`source_video_seconds` |
| `tuning`, `capo`, `assumptions` | 튜닝·카포·확인 여부와 가정 |
| `evidence`, `provenance` | 관측 경로, 원본 레코드, 알고리즘·설정 |
| `status`, `limitations` | ok/insufficient_evidence/ambiguous/evidence_conflict 등 |

화성 출력에는 `chord_candidates[]`를 추가한다. 각 후보는 `concert_symbol`, `shape_symbol`(확인 불가 시 null), `root_pc`, `quality`, `bass_midi`(미확인 null), `score`, `score_type`, `matched_pcs`, `missing_pcs`, `extra_pcs`, `evidence_ids`를 갖는다. shape 표기는 튜토리얼 모양 해석 규칙이 검수된 경우에만 계산한다. 참조 코드·TAB는 예측 입력 파일과 분리된 `references/`에 둔다.

## 실행·산출물

제안 CLI:

```powershell
python harmony_engine.py --input dataset/harmony_analysis/fixtures/input.json --output dataset/harmony_analysis/runs/demo
python -m unittest test_harmony_engine -v
```

아래를 제출한다.

1. 독립 실행 코드와 입출력 스키마·예시. 수작업 음 입력으로 실행 가능해야 한다.
2. 표준 튜닝/카포 0·1·2, 상대/물리 프렛, 음 중복, 전위, 모호한 음 집합, 무음·불명·뮤트 표시에 대한 의미 있는 시험.
3. `dataset/harmony_analysis/report.md`: 검증 명령, 통과/실패, 후보 예시, 오류와 미확정 상태.
4. 오디오 담당과 연결할 최소 fixture 및 기존 손 결과용 어댑터. 없는 상류 증거를 생성해 넣지 않는다.

## 완료 기준과 작업 순서

첫 제출은 단계 A·B다. 예를 들어 표준 튜닝 6번현 상대0·카포1의 음은 MIDI41(F2)이며, G 모양을 반음 이동한 실음 코드는 A♭이다. E–G–B–D는 Em7 후보를 포함하되 G6 같은 동일 음집합의 다른 해석도 근거에 따라 유지한다.

카포 중복 가산·프렛 0/X 혼동·불명 음의 강제 확정이 없어야 한다. 모든 예시는 코드명뿐 아니라 계산된 구성음과 점수 근거를 검토할 수 있어야 한다. 독립 촬영 성능이나 실연 코드 정확도는 아직 주장하지 않는다.

단계 C 통합은 오디오의 기본 출력과 지판·현·손 계약이 준비된 뒤 진행한다. 첫 공동 검증은 영상 약 3~12초를 대상으로 실제 연주 시점과 화면 참조를 검수한 후 수행한다. 이 구간에 충분한 전환이 없으면 추가 구간을 선택하고 선정 이유를 남긴다. 전체 영상의 진행 분석과 TAB 내보내기는 후속 작업이다.
