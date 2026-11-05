# 사용자 의미 검수 반영 — frame120 지판·프렛·현 v2

날짜: **2026-11-03, Asia/Seoul**. 외부 유료 API/업로드 **0회**. v1·원본 파일·다른 담당 코드·공용 README를 보존하고 새 run에 기록했다.

## 완료 내용과 확인 범위

- 사용자의 “다 맞아” 확인은 frame120/PTS5.041667에서 원래 너트·카포·첫 금속선의 **의미적 구분** 및 첫 금속선의 **물리 번호1**에만 반영했다.
- 확인 이미지는 생성형 이미지 위 라벨이다. **원본 픽셀 정답, 독립 블라인드 검수, 정밀 끝점**으로 승격하지 않는다.
- frame120의 첫 선에만 `confirmed_physical_fret_num=1`, `confirmation_scope=semantic only`를 기록했다. 좌표는 `source=manual_estimate`, `coordinate_human_verified=false`다.
- 다른 프레임의 번호·정밀 기하·물리 현 번호·접촉·튜닝은 확인되지 않았다. 현 번호는 모든 결과에서 null이고, 정확 기하/접촉 허용은 전부 false다.

## 숫자 전체 -1을 적용하지 않은 이유

현재 snapshot에는 같은 x≈1057 선이 이미 `fret_num=1`로 저장된 파일과, v1에서 `legacy_fret_num=2`를 별도 보존한 기록이 함께 있다. 현재 올바른 1을 0으로 바꾸면 새 오류가 된다. `mixed_version_numbering_evidence.json`에 파일별 해시와 실제 번호/좌표를 남겼다.

이번 버전은 숫자 연산 대신 **원본 선 위치 대응**으로 결합했다. 부모217프레임의 기존 `fret_num` 값은 한 개도 바꾸지 않았다. 역사적 legacy2↔물리1 대응만 출처를 붙여 설명하며 다른 legacy 기록을 조용히 일괄 재번호하지 않았다.

## 각 선의 원본 검토

frame120 원본의 번호 검토 확대본과 손이 비켜간 frame71의 원본 확대본을 사용했다. 노출 frame71에서 금속 수직선의 가로 high-pass/세로 집계 피크를 확인하고, 기존 원본 좌표와 각각 대응시켰다. 인레이 피크와 금속선 피크를 구분하는 임계값은 이 장면용 검수 휴리스틱이며 일반 정확도/확률이 아니다.

| 선 식별자 | 물리 번호 상태 | frame120 가시성 | frame71 대응 피크x | 근거 |
|---|---|---|---:|---|
| metal_x1057 | 사용자 의미 번호1 확인·원본 좌표 대응은 에이전트 | visible | 1060 | user first-metal semantic confirmation + original visible metal segment |
| metal_x1004 | 에이전트 개별 후보2 | partial | 1009 | visible upper segment in frame120; next exposed metal after anchored first wire in frame71 |
| metal_x954 | 에이전트 개별 후보3 | occluded | 961 | not visible in frame120; exposed third line in frame71 only, transfer remains estimate |
| metal_x908 | 에이전트 개별 후보4 | visible | 916 | separate visible line frame120 + exposed sequence in frame71 |
| metal_x865 | 에이전트 개별 후보5 | visible | 873 | visible line and nearby single-inlay cell; exposed sequence in frame71 |
| metal_x824 | 에이전트 개별 후보6 | visible | 833 | visible line and adjacent inlay cell; exposed sequence in frame71 |

- 첫 선: 기존 원본 x≈1057 위치에서 실제 국소 금속선 신호가 지지된다. 카포 x≈1075와 검색 구간이 구분된다. 사용자 확인은 여전히 정밀 좌표의 확인이 아니다.
- 2번 후보: frame120의 위쪽 짧은 노출 구간만 원본 지지로 기록했다. 나머지 끝점은 추정이다.
- **3번 후보: frame120에서 손에 가려져 있다.** 해당 프레임의 `frame120_support.points=[]`, `source=estimated`다. frame71의 노출선은 정체성 후보를 지지하지만 frame120의 숨은 좌표를 관측으로 바꾸지 않는다.
- 4·5·6번 후보는 frame120에서 각각 보이는 선과 노출 순서/인레이 주변 관계를 검토했다. 사용자 번호 확인은 없으므로 confirmed 값은 null이다.
- `transfer_evidence`는 frame71→120 변환 행렬, 투영한 노출 구간, 부모 수작업 선과의 차이를 보존한다. 좌표를 그 차이에 맞춰 정답처럼 보정하지 않았다.

## 너트/카포/상대 프렛

원래 너트와 카포 객체의 의미는 frame120에서 사용자 확인 상태다. 카포의 정지 프렛 번호는 직접 질문·확인된 값이 아니다. 원래 너트 x1114와 첫 금속선 x1057 사이에 카포 x1075가 있다는 관계에서 **카포1 후보를 기하적으로 추론**했다. 첫 칸 안의 상대 위치는 약0.684이다.

`capo.semantic_identity_status=user_confirmed_on_generated_annotation`과 `capo.value=null`, `user_confirmed_stop_fret=false`를 함께 기록한다. 상대 프렛은 확인된 physical-capo이므로 확정값은 null이다. `relative_fret_candidate`는 “카포1이라고 가정하면”의 조건부 값일 뿐이다. 이 값으로 음높이·발음·접촉을 만들어내지 않았다.

## 타 프레임 전파 범위

3<=PTS<12의216프레임 및 경계12초1프레임을 원본 MP4에서 다시 디코딩했다. 모든217프레임에서 원본/PNG/decoded-BGR 해시와 fresh ffprobe PTS를 검증했고, 기준 frame120→대상 ROI 이동을 다시 계산해 부모 변환과 대조했다.217개 모두 재계산 정합 조건을 만족했다.

따라서 다른 프레임에는 **참조에서 전달된 후보**와 그 변환 근거만 기록했다. `semantic_review.applies_directly_to_this_frame=false`, `confirmed_physical_fret_num=null`이다. 번호 확인이 타 프레임 직접 사용자 확인으로 복제되지 않는다. 정확 기하는217개 모두 suspect이며 contact 허용0이다.

## 실제 검증

```powershell
python apply_fretboard_semantics.py
python validate_fretboard_semantics.py
python -m unittest test_fretboard_semantic_review test_fretboard_frame_identity test_string_detector test_fret_geometry test_baze_client -q
```

- 회귀 **32개 통과**.
- 실제 fixture:217개 지판/13개 현 JSON. 직접 사용자 의미 검수 프레임1개, 의미적 첫 프렛 번호 확인1개.
- 다른 프레임 확정0, 다른 프렛 사용자 번호 확인0, 정밀 기하 valid0, 접촉 허용0, 확정 카포0, 물리 현 번호 확정0.
- 원본·PTS·픽셀 충돌0. 기존 올바른 물리 인덱스 재번호0. 부모 manifest/fixture/frame120 지판 파일의 해시 보존을 확인했다.
- 생성형 표시 이미지에 대한 의미 확인을 독립 픽셀 GT로 잘못 승격하는 회귀를 차단했다.

## 손 담당/총괄용 산출물

- `same_frame_fixture.json`: 대표13개의 새 board/string 경로.
- `frame_index_manifest.json`:216개+경계1개의 식별자·새 지판 경로·보류 상태.
- `frames/clip003012_f000120_board.json`: 이번 사용자 확인의 정확한 적용 범위.
- `frames/clip003012_f000120_strings.json`: 같은 프레임의 현/프렛/식별자와 의미 검수 범위.
- `per_wire_original_review.json`, `exposed_sequence_frame071.json`: 각 선의 개별 근거와 실제 영상 지지.
- `semantic_review_input_snapshot.json`, `mixed_version_numbering_evidence.json`, `scope_validation.json`, `parent_preservation_check.json`: 사용자 입력·혼합 버전·범위·보존 검사.

원본 PNG는 부모 run의 검증된 lossless 파일을 참조한다. source_id/인덱스/실제PTS/BGR픽셀 해시는 동일하며 image_file_sha256은 별도로 유지한다. 이미 검수한 frame120 의미 확인을 다시 요청할 필요는 없다. 다음으로 부족한 것은 원본 픽셀의 정밀 끝점·가림 사례의 원본 근거·현 정체성 검수이며, 이는 이번 사용자 확인으로 채워지지 않았다. 손의8점 검수와 오디오 혼합 확인은 다른 담당의 증거로 분리하고 이 모듈에서 지판 좌표 정답으로 사용하지 않았다.

## 변경 파일

- `fretboard_semantic_review.py`: 범위 제한 적용/개별 선 지지/번호 유지.
- `apply_fretboard_semantics.py`: 새 버전 생성·원본 재디코딩·PTS/이동 검증·같은 프레임 산출물.
- `validate_fretboard_semantics.py`, `test_fretboard_semantic_review.py`: 실제 fixture·승격 금지·기존 번호 유지 검증.
- 담당 보고서와 계약 문서만 갱신했다. 다른 담당 소유 코드와 공용 README는 수정하지 않았다.
총괄 채팅 직접 완료 보고 전송 성공(2026-11-03, Asia/Seoul). 회귀32개 및 실제217지판/13현 검증 결과와 보류 범위를 전달했다.
