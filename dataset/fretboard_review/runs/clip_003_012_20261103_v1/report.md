# 3~12초 지판·프렛·현 검수 보고서

검수일: **2026-11-03, Asia/Seoul**. 외부 API 호출 **0회**. 기존 결과와 다른 담당 파일·공용 README는 수정하지 않았다.

## 결과와 제공 범위

- 원본 MP4 SHA-256을 다시 계산했으며 오디오 manifest의 원본과 일치한다: `283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f`.
- 실제 PTS **3.0 <= t < 12.0**의 216프레임에 원본 PNG·수동 근사/추적 지판·프렛 JSON·식별 정보를 제공했다. PTS12.0의 경계 검수 1프레임은 본 구간 집계와 분리했다.
- 초기·중간·끝·이동 피크를 포함한 대표 13프레임에는 현 후보 JSON과 원본/평탄 오버레이도 제공했다. 다른 204프레임은 `strings_status=not_analyzed`로 유지한다.
- 13장의 현 후보는 5~6개지만 물리 현 번호는 전부 null이다. 6개가 나왔다는 이유로 현 정체성을 확정하지 않았다.

## 원본 시간/픽셀 계약

- `source_id`: 원본 MP4 파일 SHA-256. 사례 이름은 별도 `case_id`다.
- `frame_index`: 디코딩 표시 순서의 0기반 인덱스. ffprobe의 실제 frame PTS 테이블을 사용한다.
- `frame_pts_s`: ffprobe `pts_time` 원문을 float로 읽은 값. 원래 `frame_pts` tick과 `frame_time_base=1/12288`도 보존한다. 소수 6자리와 tick 환산 간 최대 0.5μs 반올림을 허용하되 다른 프레임/픽셀은 거부한다.
- `frame_pixel_sha256`: decoded BGR uint8 C-order 배열의 SHA-256.
- `image_file_sha256`: 제공한 PNG 파일 바이트의 SHA-256. 픽셀 해시와 섞지 않는다. 다른 PNG 인코딩은 파일 해시가 달라도 같은 픽셀일 수 있다.
- 인덱스71=PTS3.000000, 인덱스120=PTS5.041667, 인덱스286=PTS11.958333, 인덱스287=PTS12.000000이다. `index/24`나 OpenCV POS_MSEC는 이 구간에서 41.667ms 낮다. 이것은 실제 A/V 지연을 측정한 결과가 아니다.
- FFmpeg 기본 BGR 변환과 OpenCV는 컬러 프레임의 픽셀 해시가 다르다. `scale=in_color_matrix=bt601:flags=bilinear`을 명시하면 인덱스0·71·81·120·179·286·287에서 OpenCV와 정확히 일치함을 직접 검증했다. 손 담당은 제공 PNG를 쓰거나 해당 픽셀 해시를 확인해야 한다. 원본 프레임 순서/PTS와 색 변환 차이를 혼동하지 않는다.
- `fretboard_frame_identity.attach_frame_identity`가 예전 source_id=사례명을 case_id로 보존해 변환한다. 실제 예전 case_0005.00 결과를 변환한 `legacy_case0005_identity_adapter.json`도 보존했다. 해당 옛 기하가 검증됐다는 뜻은 아니다.

## 너트·카포·프렛 번호 검수

원본 frame120의 `nut_capo_inspection.png`를 수작업 시각 검수했다. 화면의 Capo/코드 표시는 확인 근거로 사용하지 않았다.

- 원래 너트 후보는 기준 x1114 부근이다. 카포 막대는 x1075 부근으로 서로 다르다.
- x1057의 금속 와이어가 카포 왼쪽에 보이며, 원래 너트부터 센 첫 금속 프렛 **후보1**이다. 기존 fixture는 1을 카포 가림으로 두고 x1057을 2로 저장했으므로 기존2..7을 새 물리후보1..6으로 검수했다.
- 새 JSON은 원래 번호를 `legacy_fret_num`에 보존한다. `source=manual_estimate`, `numbering_status=agent_visual_provisional`, `confirmed_physical_fret_num=null`이다. 독립 사람이 확정한 번호가 아니다.
- 카포는 독립 polygon이며 `is_nut=false`, `is_metal_fret_wire=false`다. 첫 프렛 칸 안 clamp로부터 카포1 후보를 기록했지만 `capo.value=null/status=unknown`을 유지한다.
- 상대 프렛은 **확인된 물리 프렛 - 확인된 카포 프렛**이다. 둘이 미확인이므로 확정 `relative_fret`은 null이다. 후보1을 가정한 `relative_fret_candidate`만 별도로 제공한다. 카포 뒤쪽 너트0에 음수 상대 프렛을 붙이지 않는다.
- 지판 바디 끝 x430은 기존 수동 ROI 끝일 뿐 마지막 금속 프렛이 독립 검증된 위치가 아니다. 전체 지판 프렛 수나 마지막 물리 번호를 여기서 확정하지 않는다.

## 프레임별 기하 유효성

영상 텍스처는 기준 frame120의 지판 ROI에서 LK 왕복 일관성과 RANSAC similarity로 추적했다. 프레임별 원시 특징수·inlier·잔차·변환을 `motion_evidence.json`에 보존했다. 이는 독립 코너 정답 오차가 아니다.

최대 끝점 이동은 약 **61.89px**, PTS3.416667 부근이다. 고정 수동 기하를 그대로 쓰면 이 이동을 놓친다. ROI 정합은 217프레임 모두 조건을 만족했지만, 정확 기하 전체 상태는 **의심(suspect) 217개**다. 독립 수동 코너/첫 프렛 참조가 없고 원 fixture가 근사값이기 때문이다. 따라서 `contact_fret_decision_allowed=false`를 전부 유지한다. 판단 보류100%를 정확도 향상으로 보고하지 않는다.

| 인덱스 | 실제 PTS(s) | 최대 끝점 이동(px) | 현 후보 수 | ROI 정합 / 정확 기하 |
|---:|---:|---:|---:|---|
| 71 | 3.000000 | 12.48 | 5 | valid / suspect |
| 81 | 3.416667 | 61.89 | 5 | valid / suspect |
| 83 | 3.500000 | 49.71 | 6 | valid / suspect |
| 94 | 3.958333 | 19.91 | 6 | valid / suspect |
| 107 | 4.500000 | 9.78 | 5 | valid / suspect |
| 108 | 4.541667 | 9.84 | 5 | valid / suspect |
| 120 | 5.041667 | 0.00 | 5 | valid / suspect |
| 143 | 6.000000 | 6.43 | 6 | valid / suspect |
| 179 | 7.500000 | 5.73 | 5 | valid / suspect |
| 215 | 9.000000 | 7.16 | 6 | valid / suspect |
| 251 | 10.500000 | 3.54 | 5 | valid / suspect |
| 286 | 11.958333 | 5.36 | 5 | valid / suspect |
| 287 | 12.000000 | 4.52 | 5 | valid / suspect |

## 독립 참조 상태와 실패 사례

독립 사람 정답은 **0개**다. 예측을 봤던 에이전트가 원본 확대 strip에서 새로 기록한 4프레임×4선=16개의 근사 참조를 `agent_string_references.json`에 저장했다. 참조 불확실성 약±1.5px, 사후 검수이므로 독립/blind 정답으로 부르지 않는다. 물리 현 번호도 모두 null이다.

원본3px 일대일 매칭 기준으로 16개 중15개가 대응됐다. 대응된 부분 평균 오차는 **1.56px**지만, 이 값은 미검출·정체성·나머지 현의 정확도를 나타내지 않는다. 초기 frame71에서는 참조1개를 놓쳤고 불명/배경 후보도 남았다. 후보/누락을 숨기거나 6개를 만들지 않았다.

- 실패/보류 예: `frames/clip003012_f000071_overlay.png`와 `agent_reference_comparison.json`.
- 큰 이동 예: `frames/clip003012_f000081_overlay.png`.
- 독립 사람 검수용 원본-only 빈 양식: `independent_reference_template.json`. 모델·에이전트 좌표를 복사해 정답으로 채우지 않았다.
- 필요한 최소 독립 입력: 초기71·이동81·중간179·끝286에서 원래 너트 양끝, 첫 금속 프렛 양끝/물리 번호, 관측 가능한 카포 위치/정지 프렛, 노출된 현 일부의 원본 좌표. 가림은 hidden/unknown으로 남기면 된다.

## 손/총괄에 전달하는 파일 계약

1. `same_frame_fixture.json`: 13개 대표 프레임의 원본 PNG·지판·현 JSON·상태 경로.
2. `frame_index_manifest.json`: 본 구간216+경계1의 모든 같은 프레임 PNG/지판 JSON과 식별자. 현 미실행204개는 not_analyzed.
3. `frames/*_board.json`: 수동/추적 기하, 원래 너트/별도 카포, 번호 수정 후보, 확정값null, 유효성 gate.
4. `frames/*_strings.json`: 같은 프레임 후보선, 공통/검출/원본 행렬·크기·해시, 물리 번호null, observed support와 model continuation 분리.
5. `numbering_review.json`, `decode_identity_check.json`, `validation.json`: 번호·색/PTS·실제 fixture 검증 근거.
6. `fretboard_frame_identity.assert_same_frame`: 다른 원본/인덱스/PTS/픽셀을 결합하지 않는다. 이미지 파일 해시는 아티팩트 무결성으로 별도 검증한다.

## 변경 파일과 실행 검증

- 구현: `fretboard_frame_identity.py`, `review_fretboard_clip.py`, `publish_fretboard_handoff.py`, `validate_fretboard_handoff.py`, 선택적 `frame_identity`를 적용하는 `string_geometry.py`.
- 검사: `test_fretboard_frame_identity.py`와 기존 지판/현/API mock 회귀.

```powershell
python -m unittest test_fretboard_frame_identity test_string_detector test_fret_geometry test_baze_client -v
python review_fretboard_clip.py
python publish_fretboard_handoff.py
python validate_fretboard_handoff.py
```

Python **26개 통과**. 실제 fixture 검증은 **217개 PNG/지판 및13개 현 JSON**에서 원본·픽셀·파일 해시 충돌0, 행렬 왕복 검사 통과, 다른 원본 결합 거부, 카포/상대 프렛 unknown 유지, 물리 현 번호 강제0을 확인했다. 기존 run 보호를 위해 같은 manifest가 있으면 추출기는 중단한다. 새 검수는 `--output 새경로`와 publisher/validator의 `--run 새경로`로 실행한다.

이 제출은 P1 1~5의 검수·계약·후보 산출물 완료다. 독립 정답/정확 운지/현별 접촉/발음/코드명 판정의 완료를 의미하지 않는다. 다른 담당의 파일과 공용 README는 변경하지 않았다.

### 하류용 계약 문서

- `docs/FRETBOARD_HANDOFF_2026-11-03.md` (완료 상태 갱신)
- `docs/FRETBOARD_SCHEMA_2026-11-03.md`
- 기존 자기 보고서 `dataset/string_review/report.md`에 2026-11-03 후속 검수 요약을 추가했다. 이전 평가 내용은 보존했다.


### 총괄 직접 보고

2026-11-03(Asia/Seoul), 원 사용자의 총괄 채팅 직접 보고 승인을 원문 채팅에서 확인한 뒤 「프로젝트 개발 방향 지시」(01a19c25-9b62-71c2-b30c-3dc5c15966de)에 send_message_to_thread로 완료·한계·경로를 전송했다. 도구 전송은 성공했으며 수신자의 읽음/후속 통합 완료를 뜻하지 않는다.
