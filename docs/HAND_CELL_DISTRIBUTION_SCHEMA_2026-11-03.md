# B 손 위치 질량 → 가상 칸 계약

2026-11-03 Asia/Seoul. 구현 `hand_cell_distribution.py`, 재생 `run_hand_cell_distribution.py`. A의 grid를 생성/보정하지 않고 polygon을 받는다. 외부 API·신규 모델 추론 없이 기존 관측을 재생한다.

## 입력

A 실제 fixture: `dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/same_frame_fixture.json`의 `frames[].models[].grid_json`. 11프레임×6독립 가정, 모두 synthetic=false. `virtual_string_grid.assert_grid_compatible`로 결과와 source/frame/PTS/pixel/canvas/M/M_inv/grid ID/version을 검증한다. `(grid_id, cell_id)`가 결합키다.

원본 손 관측: `dataset/hand_analysis/runs/clip_003_012_20261103_v1/observations.jsonl`. 확대 근거등급/실제 medoid: `dataset/integration_review/runs/robust_candidates_20261103_v2/result.json`. 전체 화면과 확대는 별도 hypothesis/branch이며 서로 평균내거나 사람 점으로 이동하지 않는다. 확대 branch의 `selected_pixel`은 실제 관측 medoid이며 같은 모델의 상관된 관측이다.

가상 grid adapter는 원본/frame/PTS/pixel 불일치, 잘못된 transform/inverse, 비볼록/범위 밖/중복/겹친 셀을 거부한다. polygon은 A 계약의 공통 평탄 좌표이며 원본 손 좌표를 해당 grid의 M으로 새로 투영한다. 과거 다른 지판 M으로 만든 flat 좌표를 섞지 않는다.

## 위치 모델 및 적분

- 원본 중심 c에 isotropic Gaussian `sigma=radius95/sqrt(-2ln(.05))`를 둔다. 기본6원본px는 보정 완료값이 아니다.
- MC 표본을 **원본 Gaussian에서 생성한 뒤 호모그래피로 투영**한다. 평탄 Gaussian 근사로 질량을 대체하지 않는다. Gaussian 지지범위는 무한이며 그중95% 원 경계와 투영 타원/이차곡선을 시각화한다.
- 원시 표본 분모를 유지해 각 polygon에 적분한다. `assigned_mass + outside_board_mass + unresolved_geometry_mass + invalid_projection_mass = 1`. `unassigned_mass`는 뒤 세 항의 합이며 별도 독립 항으로 다시 더하지 않는다. 지판 안 재정규화 없음.
- `position_mass`, top1/2/3, 전체 cell 배열(0질량 포함), MC 표준오차를 저장한다. top 배열은 양수 질량만 포함하며 전부 밖이면 빈 배열이다.
- 실제 재생은 점8192/마디4096표본, seed20261103. 이산 꼬리는0이 될 수 있다. 같은 관측의 grid 민감도 비교에 같은 난수 표본을 사용한다.

## 출력 및 하류 사용

실제 hand-cell run: `dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/`.

- `manifest.json.records[]`: 실제 frame/grid/version/result_path, 각 branch의 top3/밖/미배정/보류 요약.
- `*_hand_cells.json.observations[]`: thumb/index/middle/ring/pinky별 original pixel, 근거등급, 기하 출처·anchor/간격/번호 가정, `cells[].position_mass`, top1/2/3, 질량 보존 항, `decision/reasons`.
- `score_type=conditional_spatial_mass_not_contact_probability`, `contact=unknown`, `sounding=unknown`, `confidence_calibrated=false`, `is_virtual=true`.
- top3 바깥의 다른 칸은 `other_cells_mass`로 별도 보존한다. `top3_total_mass+other_cells_mass+unassigned_mass=1`이며 outside/unresolved/invalid는 unassigned의 세부 항이므로 이중 합산하지 않는다.
- 높은 질량도 `abstain_crop_disagreement`, `abstain_full_crop_disagreement`, ROI-only 미확정 및 기하 보류를 제거하지 않는다. ROI-only는 별도 미확정 branch다.
- grid 간격/anchor 모델별 결과는 별도 JSON. `grid_uncertainty_propagated=false`이며 시나리오 민감도만 비교한다. 여러 grid에서 유리한 칸을 골라 한 운지로 합치거나 이 모델들을 독립 증거로 곱하지 않는다.
- D는 영상 V로 같은 `(grid_id,cell_id)`의 `position_mass`를 사용할 수 있지만 `decision/reasons`, 밖/미배정 질량을 함께 보존해야 한다. full/crop/마디를 서로 독립적인 영상 표로 중복 합산하지 않는다. 가중치·오디오 점수·최종 조합은 D/C 담당 소유다.

## 바레 마디 모델

`index_segment_hypotheses[]`는 검지5→6,6→7,7→8에 별도 `uniform_segment_with_isotropic_gaussian_tube` 모델을 쓴다. 한 실제 손 관측의 끝점들을 사용하며 손끝별 medoid를 이어 가상의 손을 만들지 않는다. 한 마디 위 균등 위치+원본 Gaussian 폭이라는 **위치 가정**이고 여러 가상 현 구역에 걸쳐도 누름/발음/복수 접촉 확률이 아니다. 손끝 질량과 더하지 않는다.

## Kim 평가와 실제 현 이전 결과

`kim_same_estimated_grid_evaluation.json`: Kim의 frame120 가시8점을 같은 추정 grid에 투영한 공간 칸 참조다. 손끝 분포 순위와 관절5/6/7의 공간 위치를 비교한다. 사람 점은 runtime 중심/가상선/간격 fitting에 사용하지 않았고 실제 현·프렛·접촉 정답이 아니다. 실제정답 없는 top1/2 정확도는 null이다.

`direct_string_comparison.json`: 실제 검출 선 수/물리 번호 미해결과 과거 프렛 중심 진단을 별도 보존한다. 가상6구역을 실제6현 관측 성공으로 세지 않는다.

합성4칸 adapter fixture는 `dataset/hand_cell_distribution/fixtures/synthetic_contract/`에 별도 synthetic=true로 저장한다. 실제66 grid에 합성 자료를 섞지 않는다.
