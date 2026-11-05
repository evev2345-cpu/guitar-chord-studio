# 현·손·프렛 통합 및 연속 구간 검수

API 호출 0회. 기존 string_detector.py / string_geometry.py를 사용했고 현 검출기는 새로 구현하지 않았다.

## 최신 현 출력 연결

- 최신 현 결과는 가변 개수의 영상 지지 선 후보와 string_num=null, line_id, screen_rank, observed_intervals, unresolved, 번호 추정 출처를 보존한다. C1 등 화면 순위와 물리 현 번호를 혼동하지 않는다.
- G/F#/전환 장면은 현 담당 dataset/string_review/*_high.json을 그대로 연결했다. decoded BGR 픽셀 SHA-256, 원본 크기, M/M_inv, 공통 캔버스를 검증했다. 경로가 같다는 이유만으로 새 형식을 통과시키지 않는다.
- C#m7의 현 결과와 연속 구간 예시 프레임은 기존 현 담당 함수를 동일 프레임에서 로컬 실행했다. 고해상도 검출 좌표는 현 담당 변환을 거쳐 800×150 공통 좌표로 전달된다.
- 원본/평탄 이미지에 손 골격·프렛·현을 함께 표시했다. 노란 실선은 현 결과의 지지 구간이며 지지 없는 연장 구간은 점선이다. 지지 구간은 x축 블록 증거이고 손 아래의 직접 관측이나 접촉을 뜻하지 않는다.

| 장면 | 통합 결과 |
|---|---|
| case_0005.00 | 선 후보 5개 / 미해결 현 번호 6개. [원본+평탄](case_0005.00_review.png), [JSON](case_0005.00_integrated.json) |
| case_0194.86 | 선 후보 5개 / 미해결 현 번호 6개. [원본+평탄](case_0194.86_review.png), [JSON](case_0194.86_integrated.json) |
| case_0206.03 | 선 후보 5개 / 미해결 현 번호 6개. [원본+평탄](case_0206.03_review.png), [JSON](case_0206.03_integrated.json) |
| case_0217.20 | 선 후보 5개 / 미해결 현 번호 6개. [원본+평탄](case_0217.20_review.png), [JSON](case_0217.20_integrated.json) |

## 판단 보류와 고정 회귀

- C#m7 217.208초의 기존 잘못된 중심·임시 시각 라벨을 dataset/regression/csharp_m7_wrong_center.json으로 동결했다. 회귀 테스트는 위치 오차 >23px와 판단 보류를 확인한다. 높은 단일 프렛 질량이 이 조건을 덮어쓰지 못한다.
- 모델 전체 화면/확대 ROI를 각각 새로 추론해 비교한다. ROI 미검출·다중 손, 끝점 차이 >6px, 빠른 위치 변화 >180px/s, 손목의 큰 불연속은 abstain. 차이가 작아도 candidate_only이며 접촉은 unknown이다. 임계값은 초기 휴리스틱이고 검증된 신뢰도 기준이 아니다.
- C#m7 확대 ROI에서 손 검출이 실패했다. 이에 secondary_view_missing으로 보류하며, 검수 라벨 오차 >6px도 reviewed_center_disagreement로 별도 기록한다. 검수 라벨을 런타임 위치 보정값으로 몰래 사용하지 않는다.
- ROI 실패는 가림/검출 실패의 신호일 뿐 실제 가림 정답이 아니다. 검출 간 일치도 정확도의 증명은 아니다. 로컬 ROI는 이 1280×720 영상 전용 설정이다.

## 2초 연속 구간

- 216.208~218.208초, 원본 24fps의 49개 연속 프레임. 상태: {'selected': 40, 'no_hands': 3, 'no_hand_near_board': 4, 'ambiguous_hand_selection': 2}.
- 검지 보류 원인 집계(중복 가능): {'manual_reference_not_revalidated_per_frame': 40, 'anchor_motion_unavailable': 1, 'cross_view_disagreement': 1, 'rapid_landmark_change': 15, 'secondary_view_missing': 24, 'hand_identity_discontinuity': 3}.
- 각 프레임은 IMAGE 모드의 독립 MediaPipe 추론이다. 이전 좌표를 검출 결과로 복사하지 않는다. 이전 관측은 속도/불연속 진단용으로만 사용하며 선택 실패 시 초기화한다. 영구 손 ID나 평활화는 구현하지 않았다.
- 근접한 수동 지판 fixture를 참고했으나 프레임마다 지판을 재검증하지 않았다. 따라서 전체 구간의 프렛 판단은 모두 보류한다. 손이 선택된 40프레임을 프렛 분석 성공률로 집계하지 않는다.
- 지판의 가리지 않은 부분에서 광류 앵커 움직임도 기록했다. 작은 앵커 움직임만으로 지판 좌표가 정확하다고 판정하지 않는다. 속도는 실제 손 이동과 모델 흔들림이 섞인 값으로 순수 지터 지표가 아니다.
- [연속 구간 수치](sequence_summary.json), [실패 프레임 목록](failure_frames.json), [시간별 그래프](sequence_metrics.png). 실패 유형별 첫 사례도 원본/평탄 오버레이로 저장했다.

## 수동·자동 출처 및 독립 검수

- 신규 통합/연속 결과는 geometry_source_kind=manual_approximation, 검증 상태와 원본 수동 fixture 경로를 기록한다. 이 영상에 대한 자동 지판 검출 성능으로 보고하지 않는다. 기존 자동 검출 결과는 그대로 보존했다.
- 독립 사람 검수점은 아직 0개다. 기존 4개 에이전트 시각 점을 독립 정답으로 재분류하거나 늘렸다고 주장하지 않는다. 모델 예측을 표시하지 않는 [검수 도구](independent_review.html)에 6장×21점=126개 검수 항목을 준비했다. 가린 점은 hidden/unknown으로 기록하고 빈 좌표로 유지한다.
- 검수 도구는 원본을 내장한 로컬 HTML이며 외부 요청을 하지 않는다. 사용자가 손목부터 직접 찍고 검수자 식별자를 입력해 JSON을 내보낸다. 손 인덱스는 독립 손목 라벨에 가장 가까운 현재 검출 손과 연결하며 대응 손이 없으면 null이다. 이 JSON을 사람이 완료하기 전에는 보정 반경과 정확도 승격을 보류한다.

## 재실행

```powershell
python validate_chord_sequence.py --sequence
python summarize_chord_sequence.py
python build_blind_hand_review.py
python -m unittest test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector -v
```
- no_hands: [frame 5210](frame_5210_review.png)
- no_hand_near_board: [frame 5214](frame_5214_review.png)
- ambiguous_hand_selection: [frame 5222](frame_5222_review.png)
