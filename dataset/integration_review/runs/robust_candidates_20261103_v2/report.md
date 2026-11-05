# 확대 손 후보·가장자리 현의 안정성 비교

## 관측과 추정 구분
확대 범위4개를 별도 추론하고 여유 영역6가지에서 현 후보를 조사했다. 원본 이미지와 기존 결과는 보존했다.
신뢰도는 보정되지 않은 근거 등급이며 접촉 확률이나 측정된 정확도가 아니다.

## 손 위치 사진 비교
흰×는Kim 수동점, 색점은 모델 관측이다. 오른쪽은 실제 관측 medoid이며 초록은 후보, 빨강은 보류다.
확대 추론은 같은 모델을 사용하므로 서로 일치해도 공통 오류가 있을 수 있다.

![frame120](frame_120_hand_reliability.png)

![frame215](frame_215_hand_reliability.png)

## 현 추적 사진 비교
위는 원본, 아래는 관측 경로다. 초록=반복 내부선, 주황=경계 모호, 빨강점선=일시 후보. 물리 현 번호는 미확정이다.

![frame124](frame_124_edge_tracking.png)

![frame190](frame_190_edge_tracking.png)

![frame215](frame_215_edge_tracking.png)

## frame120 개발 검수점 오차
|index|전체화면 오차px|확대medoid 오차px|판정|
|---|---:|---:|---|
|4|9.08|45.73|abstain_full_crop_disagreement|
|8|7.80|2.33|abstain_crop_disagreement|
|12|2.99|19.43|abstain_full_crop_disagreement|
|16|4.10|30.68|abstain_crop_disagreement|
|20|24.03|10.25|abstain_crop_disagreement|

단일 개발 프레임이며 독립 테스트가 아니다. 오차가 작은 설정을 골라 임계값을 보정하지 않았다.
55손끝의 근거등급과 프레임별 후보 수는summary.json, 전체 관측·경로·추적 이력은result.json에 있다.
8프레임 연속 구간의 내부후보5개는 동일track을 유지했다. 사라진 경우lost이며 보간 좌표를 관측으로 만들지 않는다.
경계의 추가 선을 실제 현으로 확정하거나6개가 나오는 설정을 정답으로 고르지 않는다.
