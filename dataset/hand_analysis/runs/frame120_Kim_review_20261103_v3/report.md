# Kim 가시8점 평가 — 2026-11-03 (Asia/Seoul)

상태: 주어진 사람 검수8점으로 평가 완료. 1장 개발 평가이며 전역 threshold 보정이나 접촉 정답을 주장하지 않는다. 외부 API/업로드/추가 MediaPipe 추론0회. 최초 raw 관측과 검수 파일은 읽기만 했다.

## 검수 범위와 손 대응

- 입력: reviewer Kim, model_blind 선언, frame120 실제 PTS5.041666667초, 가시8점+손목unknown1. 원본 영상/픽셀/PNG 해시와 PTS를 다시 검증했다. 입력 fretting_hand_index=null과 손목null은 그대로 보존했다.
- 평가용 다중 가시점 대응: full hand 0; 같은 랜드마크 번호8점의 중앙 원본 오차 8.485px, 반대 손 782.721px. 30px 이내8/8 대0/8, 중앙값 차 774.236px.
- 좌표 이동/정합 없이 동일 랜드마크 번호를 직접 대조했다. 최소4가시점, 중앙값≤50px, 30px 이내≥4점, runner-up 차≥50px라는 평가용 대응 규칙을 기록했다. 동률/증거 부족이면 미대응으로 남기며 원본 검수의 hand index를 덮어쓰지 않는다.
- ROI의 별도 hand0은 가시점 중앙오차17.526px, 30px 이내6/8로 공간상 같은 손 후보지만 한 후보뿐이고 손가락 위치는 틀릴 수 있다. 전체 화면 hand0과 ROI hand0이 숫자가 같다는 이유로 대응한 것은 아니다.

## 원본 위치 오차

| 점 | Full 오차 px | ROI 오차 px | 현재 끝점 gate |
|---|---:|---:|---|
| 4 thumb_tip | 9.085 | 51.033 | abstain |
| 5 index_MCP | 8.419 | 8.098 | 적용 대상 아님(관절) |
| 6 index_PIP | 8.551 | 4.713 | 적용 대상 아님(관절) |
| 7 index_DIP | 9.666 | 17.227 | 적용 대상 아님(관절) |
| 8 index_tip | 7.799 | 9.489 | abstain |
| 12 middle_tip | 2.985 | 17.826 | abstain |
| 16 ring_tip | 4.103 | 28.297 | abstain |
| 20 pinky_tip | 24.033 | 46.050 | abstain |

- Full 평균 9.330px / 중앙 8.485px / 최대 24.033px. ROI 평균 22.842px / 중앙 17.526px / 최대 51.033px.
- 검지 관절+끝4점의 개별 오차도 위 표에 포함했다. 오차는 Kim이 표시한 관절/말단 패드 중심과 모델 점 사이 거리다. 표시점의 반복 검수 오차는 아직 측정하지 않았으며 출력 소수점이 그만큼의 라벨 정밀도를 뜻하지 않는다.

## gate 과도 보류와 개발 비교

- 현재 끝점 gate5개는 통과0/보류5. 중지2.985px·약지4.103px는 현재6px 위치 기준 안이지만 각각 ROI 차20.10px·25.98px로 보류됐다. 위치 기준상 명확한 과도 보류2개: 허용오차 안 끝점2/2를 모두 잃었다. 접촉/프렛의 과도 보류 판정은 아니다.
- 엄지9.085px·검지끝7.799px·소지24.033px는6px 위치 기준 밖이었다. 현 gate가 이3점을 보류하는 것과 정확한 중심을 찾아내는 것은 별개다. 특히 ROI가 full보다 이 사진의5끝점에서 더 나쁘므로 ROI를 항상 확인 정답으로 쓰면 안 된다.
- frame120에 이전 선택 관측이 없어 속도 값은null이었다. 180px/s gate의 옳고 그름은 단일 검수 사진으로 평가할 수 없다. 원래3~12초 gate 측정은 보존하며 모델/threshold를 변경하지 않았다.
- 반경3/6/9/12px 내 실제 검수점 수는1/2/5/7 (각8점 중)이다. 6px의95% 포함 가정이 이 한 사진에서25%였다는 개발 결과이며, 이를 전체 검출기 calibration 정확도나 전역95% 반경으로 일반화하지 않는다.

| 개발 비교(배포 안 함) | 통과/5 | 보류/5 | 6px내 과도보류 | 통과했지만 오차>6px |
|---|---:|---:|---:|---:|
| current_ROI_6px | 0 | 5 | 2 | 0 |
| development_ROI_12px | 0 | 5 | 2 | 0 |
| development_ROI_24px | 2 | 3 | 1 | 1 |
| development_ROI_32px | 3 | 2 | 0 | 1 |
| development_without_ROI_gate | 5 | 0 | 0 | 3 |

- ROI gate 제거는 모든5점을 통과시켜 과도보류2개를 없애지만 오차>6px의3점도 통과시킨다. 단순 gate 완화나 ROI 제거를 개선 완료로 채택하지 않았다. 현재 운영 gate는 그대로다.

## 지판 의미 검수와 새 fixture

- 너트/카포/첫금속프렛=물리1 의미 확인은 별도 사람 참조로 보존했다. 생성형 표시 이미지의 의미 확인이며 원본 픽셀 끝점·나머지 프렛·현 정체성·접촉·독립 블라인드 좌표 검수로 승격하지 않았다.
- 새 지판 fixture 연결 상태: awaiting_upstream_frame120_semantic_numbering_fixture. frame120_geometry_link.json에 입력 경로/해시·기하 상태를 기록한다. 원래 full/ROI 중심을 사람 점에 맞춰 옮기지 않았다. 정확한 프렛/접촉은 계속null/unknown.

## 인계와 남은 작업

- evaluation.json: 원본8점 오차, 평가용 손 대응/모호성, gate/개발 ablation, 입력 해시. frame120_comparison_original.png·full_error_crop.png·roi_error_crop.png: 사람 초록십자, full 주황, ROI 자홍.
- 기존 검수 G 사진은 재요청하지 않는다. 이번8점의 평가에 추가 사람 입력은 필요하지 않았다. 바레/217초 오류2장은 여전히 미완료이며, 그 조건의 위치오차·ROI gate 성능까지 평가하려면 기존 검수 도구에서 보이는 검지끝8과 관절5/6/7부터만 추가하면 된다. 가린 점/손목은unknown 유지 가능하다. 이번 자동 작업을 그 입력 때문에 중단하지 않았다.
- 단1장8점, 가림/접촉 정답 없음. 전역 반경·속도/ROI threshold 보정 완료가 아니며 독립적인 다른 조건에서 재검증해야 한다. 기존 C#m7 회귀 fixture는 변경하지 않았다.

## 실행

```powershell
python evaluate_kim_hand_review.py
python report_kim_hand_review.py
python -m unittest test_kim_hand_review test_hand_frame_contract test_hand_quality -v
```
