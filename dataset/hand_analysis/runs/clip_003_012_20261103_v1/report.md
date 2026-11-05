# 손 담당 3~12초 공통 구간 보고 — 2026-11-03

지시서 P1 손 담당 1~6 실행. 기존 결과/회귀 fixture 보존, 새 run 저장, 외부 API 호출 0회. 공용 README와 다른 담당 소유 파일은 수정하지 않았다.

## 식별·실제 PTS

- source_id=283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f. 오디오 clip_003_012_v2의 MP4 SHA-256과 일치.
- 실제 원본 frame PTS 기준 [3,12)초: 216프레임, index 71~286, PTS 3.000000~11.958333초.
- ffprobe 정수 PTS × stream time_base=1/12288을 사용한다. OpenCV 디코딩 순서를 ffprobe 표시 순서에 매핑했다. frame_index/fps를 시간 정답으로 사용하지 않는다. 시작 PTS 차를 실제 A/V 지연으로 해석하지 않는다.
- frame_contract.json에 영상 해시·frame_index·정수 PTS·PTS초·decoded BGR 해시·저장 PNG 파일 해시를 분리했다. 저장하지 않은 프레임의 image_file_sha256은 null이며 픽셀 해시는 보존된다.
- 과거 G index120의 실제 PTS는 5.041667초다. 기존 case_0005.00의 5초 표기를 덮어쓰지 않고 legacy_time_mapping.json에 정정 정보를 기록했다. 194/217초 회귀도 같은 방식으로 매핑했다.

## 지판 계약과 원시 증거

- 최신 지판 담당 결과 216개 동일 프레임을 연결했다. 상태 {'suspect': 216}. 최신 결과는 upstream_join/manifest.json과 joined_observations.jsonl이다. ROI alignment valid와 contact_fret_decision_allowed=false는 별도이며 후자를 보류에 반영했다.
- hand_frame_contract.adapt_geometry는 동일 source_id/frame_index/PTS/pixel hash의 상류 geometry_validity(valid/suspect/unknown/invalid)를 사용한다. 누락은 unknown, 프레임 불일치는 거부한다. geometry_request.json은 상류 제출용 최소 계약이다.
- 현재 결합된 유효 상류 기하가 없어 216/216프레임의 정확한 프렛·접촉은 보류다. 기존 5초 수동 fixture는 손 근접 선택의 참조로만 사용하며 source_kind=manual_approximation/validity=unknown으로 분리했다.
- 관측21점, ROI 원시 검출, 선택 상태, gate 전후 상태를 observations.jsonl에 저장했다. 이전 좌표는 속도 진단에만 사용하며 선택 실패 후 초기화한다. 영구ID/평활화/새 관측으로 좌표 재사용 없음. 비접촉 손가락을 코드 음으로 변환하지 않는다.
- 선택 상태: {'no_hand_near_board': 57, 'no_hands': 9, 'selected': 150}. selected는 정확도나 접촉 성공률이 아니다.

## 보류율·과도한 보류

- 엄지 제외 선택된 손 끝점 600관측 중 기본 gate 보류 464 (77.3%). 기하 보류와 구분한 수치다.
- 중복 가능한 원인: {'secondary_view_missing': 84, 'rapid_landmark_change': 135, 'cross_view_disagreement': 353}. ROI 재검출 실패는 실제 가림 정답이 아니라 검출 경로 불일치다.
- 시각적으로 명확한 G 장면 4.5~5.5초(agent 참조)에서 보류 87/88 (98.9%). 과도한 보류 후보이며 실제 오보류율은 독립 정답 부재로 null이다.
- 특히 기존 G index120 검지는 전체/ROI 차 약13.79px여서 6px gate가 보류한다. 전체 화면 위치가 타당해 보이더라도 어느 관측이 옳은지는 사람 점 검수가 필요하다. 모든 보류가 개선이라는 주장을 하지 않는다.
- gate_evaluation.json에 radius 3/6/9/12px × speed 90/180/360px/s의 전체 보류율을 제공한다. 기존 6px/180px/s 기준을 측정 없이 완화하지 않았다.

## 최소 독립 검수·217초 회귀

- 예측을 숨긴 기존 HTML을 재사용해 minimum_independent_review.html을 만들었다. 126점 대신 오픈·바레·오류 3장 각 최대9점(손목0, 엄지끝4, 검지5·6·7·8, 중지12, 약지16, 소지20)만 요청한다. hidden/unknown은 좌표를 비운다.
- 오픈은 공통 구간의 기존 G, 바레와 오류는 각각 과거 F#/C#m7 회귀 장면이다. 3~12초에 확실한 전체 바레가 있다는 정답을 만들어내지 않았다. 화면 코드 참조는 검수 레이어이며 접촉 정답이 아니다.
- 사람이 작성한 독립 점은 현재0개다. 기존 에이전트4점은 그대로 에이전트 참조이며 독립 정확도/보정 완료에 사용하지 않는다. 사람은 HTML에서 위 가시 점을 찍거나 가림을 표시하고 식별자를 입력해 JSON을 내려받으면 된다.
- dataset/regression/csharp_m7_wrong_center.json과 기존 회귀 검사를 유지했다. 새 run은 과거 회귀 fixture의 파일 해시도 manifest에 보존한다.

## 상류/하류 제출

- 상류: frame_contract.json, geometry_request.json. 동일 프레임 기하 유효성/현 결과를 이 계약으로 연결 가능.
- 하류: observations.jsonl, summary.json, gate_evaluation.json, review_queue.json, legacy_time_mapping.json, 대표 frame_*_overlay.png. 모든 미확인 접촉/정확한 프렛은 null/unknown.

## 실행

```powershell
python run_hand_common_clip.py
python review_hand_common_clip.py
python -m unittest test_hand_frame_contract test_hand_quality -v
```
