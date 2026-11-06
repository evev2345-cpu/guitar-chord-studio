# 확대 손 후보 신뢰도·가장자리 현 추적 개선 — 2026-11-03

최종 산출물: `dataset/integration_review/runs/robust_candidates_20261103_v2/`. 신규코드 `robust_candidate_review.py`, 검사 `test_robust_candidate_review.py`. 기존 production 선택·임계값·라벨·모델을 덮어쓰지 않고 별도의 진단/후보 계층으로 구현했다. 외부API·다운로드·학습0회.

## 1. 확대 손 후보의 근거등급

11개 프레임(120,124,190,209~216)에 미리 고정한 확대 범위 4가지를 적용해 로컬 MediaPipe를 44회 실행했다. 확대 범위는 같은 모델의 상관된 관측이며 독립 정답이 아니다. 한 범위에서 손이 정확히 1개일 때만 그 관측을 비교에 넣었다.

손끝별 유효 확대 관측이 3개 이상이면 실제 관측 중 medoid를 선택한다. 좌표를 평균내거나 사람 점에 맞추지 않는다. 확대 간 90백분위 편차가 6px를 넘으면 보류하고, 전체 화면 위치와 6px 이상 다르면 충돌로 보류한다. 전체 화면 관측이 없고 확대 결과들이 일치하면 ‘다중 확대가 지지하는 미확정 후보’만 출력한다. 확률·접촉·현 번호로 승격하지 않는다.

55개 손끝 진단 중 확대 불일치 45개, 전체 화면/확대 충돌 4개, 전체 화면+확대 지지 후보 1개, 확대끼리 지지하는 미확정 후보 5개다. 이는 새 기준의 분포이며 정확도·재현율이 아니다. 약지·소지는 가림·투영·모델 오차로 큰 변동이 남는다.

### 사람이 검수한 frame120 / PTS5.041667초

아래 왼쪽의 하늘색은 기존 전체 화면, 나머지 색점은 확대 관측이다. 오른쪽 흰×는 Kim 검수점이며 초록/빨강은 새 후보/보류다. 모델 좌표는 라벨에 맞춰 이동하지 않았다.

![검수점과 전체화면·확대 관측의 비교](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_120_hand_reliability.png)

|점|기존전체화면 오차px|확대medoid 오차px|결론|
|---|---:|---:|---|
|엄지끝4|9.08|45.73|확대들이비슷하게틀려도 전체화면충돌로보류|
|검지끝8|7.80|2.33|일부좋아졌지만 확대간흔들림으로보류|
|중지끝12|2.99|19.43|확대일치만으로신뢰하면잘못됨, 전체화면충돌보류|
|약지끝16|4.10|30.68|확대불일치보류|
|소지끝20|24.03|10.25|전체오차는여전히큼, 보류|

**실제 위치 정확도가 전반적으로 향상됐다고 주장하지 않는다.** 이번 개선은 확대 관측 하나를 무조건 채택하지 않고 공통 오류·범위 민감도·전체 화면 충돌을 드러낸 것이다. 단 1장의 검수점으로 임계값을 최적화하거나 전역 보정하지 않았다.

### 전체화면 검출 실패 frame210 / PTS8.791667초

![전체화면 손이 없을 때 다중확대의 별도 위치후보](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_210_hand_reliability.png)

검지·중지는 확대 편차가 약 4.6/5.1px여서 후보를 남겼지만 나머지는 보류했다. 이전의 단일 ROI와 달리 손끝별로 판단을 구분한다. frame212/PTS8.875초에서도 기본 ROI는 미검출이었지만 나머지 3범위가 손을 찾아 검지·중지의 미확정 후보를 추가했다. production 실패 상태를 성공으로 바꾸지 않았다.

### 원인 확인이 필요한 frame215 / PTS9초

![확대마다 흔들려 보류한 손끝 사례](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_215_hand_reliability.png)

색점들이 서로 다르게 치우쳐 모두 보류했다. 7/8프레임에서 ROI 검출이 있었다는 지난 결과가 좌표 정확도나 운지 복구 성공률은 아니라는 점을 사진으로 확인할 수 있다.

## 2. 가장자리 현 경로의 반복검출과 시간연결

원본에서 직접 평탄화하며 여유 12/20/28/36/44/52px의 6설정을 비교했다. 동일 선 후보는 양끝 오차 4공통px 이내의 완전 연결 군집으로 묶고, 서로 다른 여유 설정 3개 이상의 지지가 있으면 반복 후보로 표시한다. 같은 설정의 중복선은 투표를 늘리지 않으며 연쇄적으로 다른 선을 합치지 않는다.

인접 프레임은 최대 시간차 0.12초·양끝 거리 8공통px 이내에서 일대일 연결한다. 손실은 lost로 표시하고 이전 좌표를 새 관측으로 복사하지 않는다. 시간 간격이 크면 새 ID를 쓴다. 좌표가 같은 지판 기준이라는 조건부 추적이며 영구적인 물리 현 ID가 아니다.

### frame124 / PTS5.208333초

![원본과 반복·경계·일시 후보 구분](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_124_edge_tracking.png)

초록은 반복 내부 후보, 주황은 여러 번 검출됐으나 경계와 혼동되는 경로, 빨강점선은 일시 후보다. 지판 위 경계의 추가 선은 3설정에 나오더라도 실제 현으로 확정하지 않는다. ‘6개가 검출되는 설정’을 정답으로 고르지 않았다.

### frame190 / PTS7.958333초

![가장자리 후보의 불안정성을 분리한 결과](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_190_edge_tracking.png)

아래쪽 추가 선은 설정에 따라 위치가 달라 일시 후보로 분리됐다. 실제 고음 1번 현인지 지판 테두리인지 독립 정답은 없으므로 번호는 null이다.

### frame215 / PTS9초

![연속 구간의 경로 추적 예시](../dataset/integration_review/runs/robust_candidates_20261103_v2/frame_215_edge_tracking.png)

209~216의 8프레임에서 내부 5후보가 동일 track을 유지했다. 경계선은 그 추적과 분리했다. 관측 지지와 모델 연장을 실제 접촉으로 해석하지 않는다. 정확한 6현 대응·최외곽 현 확정은 아직 미완료다.

## 3. 검증·재현

```powershell
python robust_candidate_review.py --output dataset/integration_review/runs/robust_candidates_20261103_v1
python robust_candidate_review.py --replay-result dataset/integration_review/runs/robust_candidates_20261103_v1/result.json --output dataset/integration_review/runs/robust_candidates_20261103_v2
python -m unittest test_robust_candidate_review test_joint_failure_investigation test_joint_evidence_review test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -q
```

위 명령을 실행해 **103개 통과/실패0**을 확인했다. v1은 실제 추론, v2는 같은 관측을 재분석해 그림·경계 구분·보고서를 생성한 결과다. 재실행할 때는 새 output을 지정한다.

새 검사 6개는 단일 확대의 과신 방지·실관측 medoid·전체 화면 충돌·확대 흔들림·중복 투표 방지·연쇄 군집 방지·경로 손실/시간 단절 재시작을 검증했다. 사진 8개를 생성하고 실제 출력의 대표 사례를 열어 시각 점검했다.

## 4. 다음 단계

확대 합의만으로 접촉 판정을 추가하지 않는다. 다음은 손끝 가림·관절 구조·원본 영상의 움직임 근거와 결합하는 작업이며, 현 추적은 테두리와 금속 현의 국소 근거를 보강해야 한다. 이번 단계에서 추가 사용자 검수를 먼저 요청하지 않고 검수 사진의 오류를 회귀 근거로 보존했다.

앞으로 보고서는 [사진 첨부 규칙](REPORTING_GUIDELINES.md)에 따라 원본·오버레이·실패 사례 사진을 본문에 삽입한다.
