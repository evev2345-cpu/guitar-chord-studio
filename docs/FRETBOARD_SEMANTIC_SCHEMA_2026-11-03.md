# 지판 의미 검수 v2 계약 — 2026-11-03, Asia/Seoul

최신 run: `dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic/`.
기존 프레임 식별자·PTS·해시·M/M_inv 계약은 유지한다. 원본 PNG는 검증된 v1 파일을 참조한다.

## 새 의미 확인 필드

- `semantic_review.applies_directly_to_this_frame`: frame120에만 true.
- `semantic_review.displayed_image_method`: 생성형 이미지의 라벨 확인임을 보존.
- `semantic_review.independent_pixel_ground_truth=false`: 독립/원본 픽셀 정답이 아니다.
- `objects.*.semantic_identity_status`: frame120 너트/카포/첫 금속선은 user_confirmed_on_generated_annotation. 타 프레임은 참조 후보 또는unknown.
- 첫 선의 `confirmed_physical_fret_num=1`: **의미적 번호만** 확인. `confirmation_scope`, `coordinate_human_verified=false`, `source=manual_estimate`를 반드시 함께 읽는다.
- 다른 프렛/다른 프레임의 confirmed 번호는null. 각 선의 `numbering_evidence`가 관측 구간·가림·노출frame71 대응을 개별 기록한다.

## 변하지 않는 보류

`geometry_validity.status=suspect`, `exact_geometry_verified=false`, `contact_fret_decision_allowed=false`. 카포의 객체 의미 확인과 정지 프렛 번호는 별개여서 `capo.value=null`, `user_confirmed_stop_fret=false`, 후보1만 기하적 추론으로 기록한다. 확정 상대 프렛은null이고 카포1 조건부 후보를 별도로 둔다. 물리 현 번호는 전부null이다.

현재 일부 옛 파일은 x1057을 이미1로 저장하고 v1의 historical alias만2를 유지한다. 숫자 전체에-1을 적용하지 않는다. 새 run에서 기존 실제 fret_num의 변경은0개다. 위치 대응과 출처를 따라 결합한다.

타 프레임은 재디코딩 원본/BGR/PNG/PTS와 재계산 이동을 검증한 경우에만 참조 후보를 전달한다. 사용자 직접 확인을 복제하지 않는다. 신원 또는 이동 검증이 없으면 unknown이다.
