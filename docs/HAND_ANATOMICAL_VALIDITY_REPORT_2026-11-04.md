# 손 담당 P0 보고 — 2026-11-04

frame210/PTS8.791666667의 검수된 baseline ROI에서 중지·약지·소지 체인을 운지 근거로 제외하는 sidecar와 실제 fixture를 완성했다. 오류 차단은 완료했으며 해부학적으로 올바른 손 복구는 미완료다. API·새 추론·설치·다운로드는0회다.

## 실제 관측과 실패

![원본 frame210, PTS8.791667](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/original.png)

![같은 원본 위 실제 전체21점 손 4개 비교](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/whole_hand_comparison.png)

초록은 저장된 원시 EDGES 연결선만이다. 왼쪽위 crop0=검수된 baseline, 오른쪽위 crop1, 왼쪽아래 crop2, 오른쪽아래 crop3다. 모든 패널은 같은 원본 영역·확대율이다. 점/분포/격자/손가락별 medoid 혼합은 없다. 다른crop은 별도 미검수이며 올바른 복구로 선정하지 않았다. 사진만으로 숨은 소지의 정확한21점 대응을 자동 검증할 수 없어 복구 성공을 주장하지 않는다.

## 계보·차단 결과

원시 observations.jsonl의 baseline ROI21점과 robust crop0 전체21점이 완전히 같다. 5손끝의 실제 medoid는 모두 crop0에서 왔다. 검수이미지 SHA 및 source/index/PTS/pixel을 확인했다. 중지12·약지16·소지20의 6시나리오 분포18개를 invalid로 차단했다. 엄지·검지12개는 정성검수를 정밀정답으로 확대하지 않고 unknown으로 유지했다. 검지3마디×6시나리오도 unknown이다. 원시 좌표·top1/2/3·모든 위치질량·기존 보류사유를 유지했다. 큰 질량1.0도 차단 해제하지 않는 회귀를 포함한다.

D 인덱스: [downstream_fixtures.json](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/downstream_fixtures.json). 전체6frame fixture와 review_binding.json·medoid_lineage.json은 같은 폴더다. 계약은 [HAND_ANATOMICAL_VALIDITY_SCHEMA_2026-11-04.md](C:/Users/evev2/Documents/antigravity/GUITAR/docs/HAND_ANATOMICAL_VALIDITY_SCHEMA_2026-11-04.md).

변경 소스는 hand_anatomical_validity.py, replay_hand_anatomical_validity.py, test_hand_anatomical_validity.py다. 다른 담당코드·README·기존run·사람검수는 변경하지 않았다. v1은 기존 raw 이미지 경로가 빈 문자열이라 사진 생성 전 중단된 초안으로 보존했다. 최종run은v2다.

## 실제 검증

`python -m unittest test_hand_anatomical_validity test_hand_cell_distribution test_virtual_string_grid test_kim_hand_review test_hand_frame_contract test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector test_audio_analysis test_harmony_engine -q`

124개, 실패0·오류0. 새9개 회귀에는 검수그룹/정성검수한계/다른crop·프레임·source 격리/스켈레톤 해시/필터후 medoid 인덱스/질량1.0 차단/실제6grid 재생/원시 ROI동일 검사가 있다. 저장된 주요 입력4개 SHA도 동일하다. 테스트 통과는 손 복구나 접촉 정확도 개선을 의미하지 않는다.

남은 범위는 D가 신규 sidecar의 invalid/unknown을 결합 전 hard gate로 소비하는 통합검증이다. B는 위치가설을 보존해 제공하며 오디오로 손가락 정체를 복원하지 않는다. 총괄 직접보고는 기존 사용자 상시승인으로 진행한다.

총괄 전달 완료: 기존 사용자 직접 상시승인에 따라 local/01a19c25-9b62-71c2-b30c-3dc5c15966de로 fixture·계약·실제검증·사진·복구미완료를 보고했다. 최종 export 코드 변경 후 신규9개도 재검증 통과했다.
