# 지판·프렛·현 프레임 계약 — 2026-11-03 (Asia/Seoul)

새 fixture: `dataset/fretboard_review/runs/clip_003_012_20261103_v1/`.

| 필드 | 의미 |
|---|---|
| source_id | 원본 MP4 파일 SHA-256, 사례 이름 아님 |
| case_id | 사례 이름. 시간/원본 결합 키가 아님 |
| frame_index | 표시순서 0기반 인덱스 |
| frame_pts_s | ffprobe 원본 stream PTS, 소수6자리 읽기 |
| frame_pts / frame_time_base | 원래 integer PTS tick / rational timebase |
| frame_pixel_sha256 | decoded BGR uint8 C-order 바이트 SHA-256 |
| image_file_sha256 | 저장된 PNG 파일 SHA-256; 픽셀 해시와 다름 |
| image_file | 해시로 검증할 원본 PNG 절대 경로 |
| canvas_size / M / M_inv | 공통 800x150 좌표와 원본 간 호모그래피 |
| source / geometry_validity | 수동 근사 출처, ROI 정합과 정확 결정 허용 여부 |

`assert_same_frame(a,b)`는 source_id/index/pixel hash를 정확 비교하고 PTS는 표현 반올림 0.5μs만 허용한다. 이 허용치는 실제 A/V 오차 허용이 아니다. encoded file hash는 각 아티팩트 무결성으로 별도 확인한다. `attach_frame_identity`는 옛 사례 source_id를 case_id로 보존하며 다른 원본·픽셀은 거부한다.

## 지판/프렛

ROI 정합 valid는 정확한 물리 프렛/접촉 valid를 뜻하지 않는다. 현재 수동 기하는 모두 `geometry_validity.status=suspect`, `exact_geometry_verified=false`, `contact_fret_decision_allowed=false`다. 추적 residual은 GT 코너 오차가 아니다.

`fret_num`은 물리 프렛 **후보**이며 `physical_fret_candidate`와 같다. `numbering_status=agent_visual_provisional`, `confirmed_physical_fret_num=null`, `source=manual_estimate`를 함께 읽어야 한다. 기존 fixture의 2..7은 새 후보1..6에 대응하며 `legacy_fret_num`으로 보존한다. 새 좌표가 임의로 번호를 자동 보정한 것이 아니라 원본 너트부터 첫 금속선을 세어 검수한 후보이다. 독립 사람 검수는 없다.

카포는 `capo.original_polygon`의 독립 물체다. 너트/금속 프렛으로 삽입하지 않는다. 첫 칸 clamp 근거로 `physical_fret_candidate=1`을 기록하되 `capo.value=null/status=unknown`이다. `relative_fret`은 확인된 physical-capo이고 현재 null; 별도 `relative_fret_candidate`는 후보카포1 조건부 값이다. 이 후보로 음높이/발음/코드를 확정하지 않는다.

## 현

`strings`는 실제 영상에서 지지된 후보 선으로, 위치는 공통 좌표의 `y=m*x+b`다. `screen_rank`와 `string_num`은 별개다. 부분 또는 미검증6선 모두 물리 번호null을 유지한다. `observed_intervals`는 영상 지지 구간, 그 밖은 모델 연장이다. 본 run에 검증된 reference 추정선은 입력하지 않았다. 미확정 현 정체성은 `unresolved`로 보존한다.

13개 대표 프레임만 현을 검출했다. dense index의 다른204개 프레임은 `strings_json=null`, `strings_status=not_analyzed`다. 현 결과를 이웃 프레임에 복사해 관측처럼 표시하지 않는다.

## 시간/픽셀

본 구간은 3<=원본 PTS<12초:216프레임(index71..286). index287=PTS12초는 별도 경계검수다. frame_index/24는 video 첫 PTS0.041667초를 반영하지 못한다. audio sample time에 이 값을 무조건 더하거나 빼면 안 된다.

OpenCV와 FFmpeg 기본색 변환은 픽셀이 다를 수 있다. FFmpeg `scale=in_color_matrix=bt601:flags=bilinear`에서 인덱스0/71/81/120/179/286/287의 BGR 해시가 OpenCV와 모두 일치했다. 동일구간 결합에는 제공 PNG 또는 검증된 디코딩 경로를 사용한다.
