# 손가락 해부학적 유효성 계약 — 2026-11-04

`hand_anatomical_validity.py`는 원시 좌표를 수정하지 않는 sidecar/adapter다. `resolve_medoid`는 단일손 view만 필터링한 medoid index를 실제 view_id·bounds·hand_index·전체21점 SHA256으로 연결하고 선택 좌표와 일치하는지 확인한다.

`hand_anatomical_validity.v1`의 status는 `invalid` 또는 `unknown`이다. 이번 정성검수에서 valid는 생성하지 않는다. source_id/frame_index/PTS(1e-6초 허용)/pixel hash 및 view_id/bounds/hand_index/skeleton SHA가 모두 맞아야 검수를 적용한다. 검수 바인딩은 원시 ROI21점과 robust crop0의 완전동일, 검수사진 SHA를 확인해 생성했다. 다른crop/프레임/출처/좌표는 invalid를 상속하지 않는다.

검수된 baseline의 9~20번 점은 invalid다. 엄지·검지는 정성적으로 대체로 정상이라는 검수이지 정밀 위치·접촉 정답이 아니므로 unknown이다. 다른crop도 unknown이다. 누락 소지 좌표 생성과 체인이름 재지정은 금지한다.

하류는 `anatomical_fingering_evidence_allowed=false`를 hard gate로 적용한다. invalid는 알려진 대응오류, unknown은 미검증이며 낮은 점수/입력결측과 다르다. 위치질량·오디오 가중치로 이 필드를 true로 바꾸지 않는다. 원래 cells[].position_mass와 top1/2/3·미배정질량은 진단용으로 보존한다. 각 cell에도 anatomical_validity_status와 허용false를 전달한다. confirmed_cell=null, contact/sounding=unknown이다. `anatomical_recovery=not_completed`는 오류차단 성공과 복구 미완료를 구분한다.

실제 D 전달 인덱스:
`C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/downstream_fixtures.json`

30개 단일분포(6grid×5손끝)의 exact path/grid_id/observation_id/status를 제공한다. 각 파일은 기존 hand_cell_distribution.v1과 호환되는 위치질량+새 sidecar다. 전체 프레임 fixture6개에는 검지 마디3개씩도 보존한다. 기존run은 변경하지 않았다. v1은 이미지경로 빈 문자열로 사진 생성 전 중단된 초안이며 최종 전달 대상은 v2뿐이다.
