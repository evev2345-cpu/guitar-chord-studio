# Virtual string grid v1 — A 담당 계약

구현: `virtual_string_grid.py`. 실제 fixture: `dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/same_frame_fixture.json`. 전체 사진·검증: 같은 run `report.md`. 기존 지판/검출 모듈·손/오디오 파일을 변경하지 않는 추가 계층이다.

## 런타임 사용

```python
from virtual_string_grid import build_grid, assert_grid_compatible
grid = build_grid(board, config, observed=None)
# 다른 grid 기반 칸 질량과 결합 전 검사. other는 아래 필드를 모두 보존한다.
assert_grid_compatible(grid, other)
```

`board`는 기존 지판 JSON의 frame_identity, 동일한 최상위 source_id/frame_index/frame_pts_s/frame_pixel_sha256, image_size/canvas_size, corners/M/M_inv, frets를 제공한다. 코너 순서는 nut_top, body_top, body_bottom, nut_bottom이다. 명명된 top=실제6번 현 쪽이라는 해석은 독립 검증되지 않았으며 config의 가정이다. M은 원본→공통, M_inv는 역변환이다. 좌우 반전 원본도 M에 의해 처리한다. common 좌표는 연속 `[0,W]×[0,H]`; x=0 너트, x=W 바디. 픽셀 마지막 인덱스 W-1/H-1과 연속 유효 경계 W/H를 혼동하지 않는다.

입력 config 예:

```json
{
  "model_name": "margin_only_alternative",
  "six_side": "top",
  "anchor_y": [15, 15],
  "anchor_status": "assumed_margin_not_observed",
  "opposite_margin": [15, 21],
  "spacing_scale": 1,
  "spacing_not_inferred_from_one_line": true,
  "fit_to_hand_or_audio": false
}
```

너트/바디 각각 anchor-side 여백(위쪽이면 anchor_y, 아래쪽이면 H-anchor_y)과 반대쪽 여백을 지판폭에서 빼고 **5**로 나눈다. anchor 한 선만으로 간격을 추론하지 않는다. d의 양끝을 선형 보간하며 string k는 `y6+(6-k)*d`(위쪽6번 가정)다. 아래쪽6번은 부호가 반대다. 중심선이 지판 밖이거나 양끝 간격이 0 이하이면 입력 거부한다. 현재 실제 baseline의 반대 여백 비율10%/14%는 검증되지 않은 가정이다.

## 출력

|필드|의미|
|---|---|
|grid_version / grid_id|버전 및 원본 식별자·변환·프렛 출처·가정의 SHA256. 다른 모델은 다른 ID|
|frame_identity 및 최상위 식별자|원본 MP4 SHA, display-order index, 원본 ffprobe PTS, 디코딩 BGR 픽셀 SHA. index/fps 시간으로 바꾸지 않음|
|image_size / canvas_size / M / M_inv|원본/공통 크기와 변환|
|geometry_source / geometry_status / upstream_geometry_validity|상류 후보 지판의 출처·보류 사유 원본 보존|
|anchor_status / assumptions|관측 후보 가정 또는 순수 여백 가정. 실제6번 현 확인 아님|
|spacing_source / endpoint_spacing / endpoint_outer_margins|간격 및 실제 적용 후 양끝 여백. 단위 공통px|
|virtual_lines|virtual_string_num, physical_string_num=null, y_nut/y_body, y=m*x+b, estimated/is_virtual|
|string_regions|인접 중심선 중간 경계로 나눈6개 polygon. 바깥은 보드 경계로 제한|
|cells|grid 안에서 유일한 cell_id, virtual_string_num, physical_fret_candidate, polygon/area, boundary_sources 및 boundary_number_confirmations|
|unresolved_fret_boundaries|번호 없음/누락된 이전 경계/교차 경계/무효 경계를 포함한 띠의 보류|
|unassigned_board_area|번호가 연결된 프렛 띠 밖의 면적. 보드 밖은 별개이며 포함되지 않음|
|covered_fret_area / partition_area|생성 가능 프렛 띠 면적 / 모든 칸 면적 합. 이 둘의 일치는 산술 검증|
|observed_string_layer|원본 검출 후보를 별도 보존. virtual_lines에 섞지 않음|
|spacing_error_px=null|간격 정답 미확보로 미평가|
|synthetic|실제 fixture false, 합성 테스트 true|

결합키는 `(grid_id,cell_id)`다. 셀 polygon은 공통 좌표 convex polygon으로 꼭짓점 수가4보다 많거나 적을 수 있다. 프렛선은 `x(y)=xt+(xb-xt)*y/H`, 가상 현/중간 경계는 `y(x)=m*x+b`다. 셀에는 전체 좌우 프렛 boundary_sources를 보존한다. 행렬·캔버스와 polygon을 함께 전달한다.

물리 프렛 n의 공간은 경계n-1과n 사이이며 배열순서로 재번호하지 않는다. 기존 fret1 의미 확인은 경계별 근거로만 보존하고 셀 전체 confirmed_physical_fret_num은 null이다. 정확 기하/contact는 false다. relative_fret은 capo.value가 정수이며 user_confirmed_stop_fret 또는 independently_verified가 true인 경우만 적용한다. 미확인 카포1 후보를 더하거나 빼지 않는다.

`contact=unknown`, `sounding=unknown`, `estimated=true`, `is_virtual=true`, `confidence_calibrated=false`. 가상6현은 실제6현 검출 성공이 아니다. 이 모듈은 손 위치 질량·누름 확률·발음 확률·코드명을 출력하지 않는다.

## 실제 fixture와 민감도

11개 프레임120/124/190/209~216 ×6모델=66개 실제 grid다. 모든 모델의 frame identity는 동일 원본으로 검증됐다. fixture의 original은 보존된 원본 PNG 경로, board_json 및 board_json_sha256은 상류 JSON 경로/불변 검사다. 모델별 grid_json/raw_overlay/flat_overlay를 제공한다.

baseline은 화면 topmost 관측 후보를 hypothetical string6 anchor로 사용한다. boundary/reflection 가능성을 해소하지 않는다. `margin_only_alternative`은 관측 후보와 무관한 대안이다. 두 대안에 확률 가중치를 주지 않는다.

- anchor_minus3/plus3: 양끝 anchor를 ±3공통px 바꾸되 반대쪽 여백은 고정해 간격도 재계산한다. 전체6현의 단순 평행 이동이 아니다.
- spacing_minus10pct/plus10pct: anchor 고정, 양끝 d를0.9/1.1배로 조절한다. 반대쪽 최종 여백은 이에 따라 달라진다.
- 시나리오 편차는 정답 오차·통계적 신뢰구간이 아니다. calibration이나 손 위치 오차와 혼동하지 않는다.

`assert_grid_compatible`는 source/frame/PTS/pixel/canvas/grid version/ID/M/M_inv 불일치를 거부한다. 상류가 없으면 합성fixture를 사용할 수 있지만 synthetic=true를 보존해야 한다. 현재 실제 run에는 합성 입력이 없다.
