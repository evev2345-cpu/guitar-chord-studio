# 손 담당 제출 — 2026-11-03 (Asia/Seoul)

최신 상태: Kim의 frame120 가시8점 평가 완료. 손목unknown·hand index null을 보존하고 다중 가시점으로 평가용 대응을 검증했다. 추가 G 사진 검수는 요청하지 않는다. 외부 API 호출0회, 원본 관측·검수점 이동0회.

## Kim 검수 평가 추가 제출

- 새 보고서: `dataset/hand_analysis/runs/frame120_Kim_review_20261103_v3/report.md`, 수치 `evaluation.json`, 비교 `frame120_comparison_original.png`, `frame120_full_error_crop.png`, `frame120_roi_error_crop.png`.
- 신규 코드: `evaluate_kim_hand_review.py`, `report_kim_hand_review.py`, `test_kim_hand_review.py`. 다른 담당 코드/공용 README 변경 없음. v2 초기 비교도 보존했다.
- 원본8점 다중 대응: full hand0 중앙오차8.485px, hand1 782.721px; 30px 이내8/8 대0/8. 임의 손목 추정이나 좌표 정합 없이 같은 관절 번호를 대조했다. 대응은 별도 derived_hand_index이고 원본 fretting_hand_index=null은 불변이다.
- Full 평균9.330px, 중앙8.485px, 최대24.033px. ROI 평균22.842px, 중앙17.526px, 최대51.033px. 점별·손가락별 원본 오차를 JSON/표에 기록했다.
- 기존 끝점 gate는 통과0/보류5. 사람 점과6px 이내인 중지2.985px·약지4.103px도 ROI 불일치로 보류: 위치 기준상 과도 보류2개. 프렛·접촉 정답은 아니므로 정확한 프렛/접촉 보류 자체를 오판으로 취급하지 않는다.
- 개발 ablation은 운영 gate와 분리했다. ROI gate 제거는 허용범위 내2점을 살리지만 오차>6px의3점도 통과한다. 단1장8점으로6px·180px/s·ROI 기준을 보정 완료로 선언하거나 변경하지 않았다. 해당 프레임 속도는null이어서180px/s 성능은 미평가다.
- 사람의 너트·카포·물리1번 의미 확인은 별도 출처로만 기록했다. 생성형 표시 이미지 위 확인을 원본 픽셀/끝점/접촉/다른 번호의 독립 정답으로 승격하지 않았다.
- `frame120_geometry_link.json`은 새 지판 semantic run에서 동일 프레임 board fixture가 생기면 source/index/PTS/pixel을 검증해 연결한다. 현재 fixture 대기일 경우 그 상태를 명시하며 정확 프렛·접촉은 계속 보류다.
- 검증: `python -m unittest test_kim_hand_review test_hand_frame_contract test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector test_audio_analysis test_harmony_engine -q` → 실제91개 통과, 실패0.
- 이미 검수한 G 사진을 재요청하지 않는다. 현재 평가에는 추가 사람 입력이 필요 없다. 미완료 바레/217초 오류2장의 별도 조건 성능을 평가하려면 기존 도구의 보이는 검지끝8 및 관절5/6/7부터만 추가하면 되며, 가림/손목은unknown 유지 가능하다.
- 위 Kim 평가 결과와 fixture 대기 상태는 사용자 승인에 따라 총괄 채팅 `01a19c25-9b62-71c2-b30c-3dc5c15966de`에 직접 전송했고 성공 응답을 확인했다.

아래는 Kim 검수 도착 전 3~12초 실행 당시의 이력이다. 당시 독립 점0이라는 기록은 과거 상태이며 현재는 사람이 표시한 가시8점을 위와 같이 평가했다.

## 새 run 및 보고서

- `dataset/hand_analysis/runs/clip_003_012_20261103_v1/report.md`
- `joined_observations.jsonl`: 최신 동일 프레임 상류 기하 반영 216프레임 관측/후보/보류. 최초 `observations.jsonl`은 그대로 보존.
- `upstream_join/manifest.json`: 지판 담당의 216개 기하 fixture 연결. 모두 `suspect`, `contact_fret_decision_allowed=false`. 손 관측과 후보는 유지하고 정확한 프렛·접촉은 보류한다.
- 216개 중 12개는 현 담당의 같은 프레임 현 결과도 있으며 원본/평탄 통합 오버레이 저장. 나머지 204개의 현 증거는 `not_provided`; 새 현 검출기로 채우지 않았다.
- `frame_contract.json`, `geometry_request.json`: 영상 SHA-256, 정수 PTS/시간기준, 실제 PTS초, 프레임 인덱스, decoded BGR 픽셀 해시, 저장 PNG 파일 해시를 분리.

## 실행 관측

- MP4 SHA-256 `283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f`는 오디오 원본과 일치.
- 실제 PTS [3,12): index71~286의 216프레임, 3.000000~11.958333초. `/24` 대신 ffprobe 정수 PTS × 1/12288 사용. 컨테이너 시작 차를 A/V 동기 오차로 판정하지 않는다.
- 상태: selected150, no_hand_near_board57, no_hands9. 이전 좌표를 새 관측으로 재사용하지 않았다.
- 선택된 손의 엄지 제외 600끝점 관측: 고정6px/180px/s/ROI gate 보류464=77.3%. 원인 중복 집계는 ROI 없음84, 급격한 변화135, ROI/전체 위치 차353.
- 명확해 보이는 G 구간 4.5~5.5초(agent 시각 참조)에서87/88=98.9% 보류. 과도한 보류 후보를 공개한다. 독립 점 정답이 없어 실제 오보류율은 null이다. gate 기준을 개선됐다고 주장하거나 임의 완화하지 않았다.
- `gate_evaluation.json`에 radius3/6/9/12 × speed90/180/360 민감도 제공.
- 기존217초 C#m7 회귀 파일을 수정하지 않았고 새 manifest에 SHA-256 기록. 실제 source PTS는217.250000초이며 기존 표시를 덮어쓰지 않고 `legacy_time_mapping.json`에 정정 정보 저장.

## 최소 사람 입력

`minimum_independent_review.html`: 기존 예측 숨김 HTML을 재사용. 오픈·바레·오류3장에 손목0, 엄지끝4, 검지5/6/7/8, 중지끝12, 약지끝16, 소지끝20, 최대27항목만 요청한다. 보이는 점만 클릭하며 가림/불명은 null 좌표로 유지한다. 바레/오류 장면은 공통 구간 밖의 회귀 참조로 명시했다.

현재 독립 사람 점0, 기존 에이전트 시각 참조4점. 사람은 HTML에서 위 점 또는 가림을 표시하고 검수자 식별자를 넣어 JSON을 내려받으면 된다. `import_minimum_hand_review.py`가 source/PTS/pixel/file 해시 및 hidden/null 규칙을 검증한다. 사람이 작성하지 않은 점을 정답으로 승격하지 않는다.

## 변경 파일

- 신규: `hand_frame_contract.py`, `run_hand_common_clip.py`, `join_hand_upstream_geometry.py`, `review_hand_common_clip.py`, `import_minimum_hand_review.py`, `test_hand_frame_contract.py`, 본 제출서.
- 수정: `hand_fret_tracker.py`의 수치 경계 검사만 변경. 상류 float32 왕복으로 생긴 약1e-4px 범위 이탈을 이동/클램프 없이 허용하도록 수치 허용1e-3px를 두었다. 실질 이탈은 계속 거부하며 새 회귀검사 추가.
- 기존 실험·회귀·보고서는 그대로 보존했다. 새 run의 보고서는 상류 반영 뒤 갱신했다.

## 검증

```powershell
python run_hand_common_clip.py
python join_hand_upstream_geometry.py
python review_hand_common_clip.py
python -m unittest test_hand_frame_contract test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector test_audio_analysis test_harmony_engine -q
```

실제 결과: 78개 통과, 실패0. 최초 run은 덮어쓰기 방지; 새 추론은 다른 `--output`을 지정한다. 동일 관측을 상류 기하에 재투영한 것은 새 시간 관측 생성이나 앞 프레임 재사용이 아니다.

## 남은 한계 및 인계

독립 사람 검수와 지판의 정확한 번호/접촉 허용 증거가 없어 실연 정확도·반경 보정 승격·정확한 프렛 접촉은 보류다. 기하가 suspect인 것은 상류 출처 상태이며 손 담당이 valid로 바꾸지 않았다. 영구 ID·복잡한 평활화는 추가하지 않았다.

총괄/하류는 `joined_observations.jsonl`, `upstream_join/manifest.json`, `frame_contract.json`을 사용한다. 오디오와는 `source_id`+`frame_pts_s`로 맞추며 화면 코드/TAB는 별도 참조로 유지한다.

## 총괄 보고

2026-11-03 사용자 승인에 따라 「프로젝트 개발 방향 지시」(threadId `01a19c25-9b62-71c2-b30c-3dc5c15966de`, hostId `local`)에 완료/부분 차단 보고를 직접 전송했고 도구 성공 응답을 확인했다. 독립 검수 입력 필요, 보류율과 과도한 보류, 상류/하류 절대 경로를 함께 보고했다. 새 run의 `verification.json`에 전송 및 최종 검증을 기록했다.
