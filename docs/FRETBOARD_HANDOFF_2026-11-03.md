# 최신: 사용자 의미 확인 반영 v2 (2026-11-03, Asia/Seoul)

최신 handoff는 `dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic/same_frame_fixture.json` 및 `frame_index_manifest.json`이다. 상세 보고서는 해당 run의 `report.md`, 추가 계약은 `docs/FRETBOARD_SEMANTIC_SCHEMA_2026-11-03.md`.

frame120/PTS5.041667에서만 너트/카포/첫 금속선 객체 의미와 첫 금속선 번호1이 사용자 확인됐다. 생성형 라벨 이미지 확인이며 원본 픽셀 GT/정밀 좌표/독립 블라인드 검수 아님을 보존했다. 첫 선의 confirmed_physical_fret_num=1은 의미 번호에 한정된다. 정확 기하/contact gate는 여전히false다. 다른 프레임/다른 프렛/물리 현 번호는 확인되지 않았다.

원본 재디코딩/PTS/픽셀/파일해시와 이동 재계산217프레임 검증, 같은 프레임 현13개 제공. 기존 올바른 fret_num을 변경한 수는0이다. 후속 번호는 개별 원본 근거로 후보 유지하고 frame120의3번 후보는 가림/추정으로 기록했다. 카포1은 객체 확인과 구분한 기하적 추론이므로 capo.value=null·상대 프렛null을 유지한다.

아래는 v1 당시의 보존된 계약/보고다. 최신 의미 상태에는 위v2가 우선한다.

---

# 지판·프렛·현 → 손/총괄: 3~12초 계약 (완료)

산출물 run: `dataset/fretboard_review/runs/clip_003_012_20261103_v1/`.
원본 source_id: `283220036613f22a618aaaad2574df638085772dde16eec05c7e56caccd1da2f`.
외부 API 호출 없음. 기존 `dataset/chord_video_review` 결과는 수정하지 않는다.

- `ffprobe -show_frames` 기준 첫 video PTS=0.041667초. display-order index 71=PTS3.000000초, index287=PTS12.000000초. 3<=PTS<12를 본 구간으로 사용하고 12초는 경계 검수로 분리한다. index/fps의 41.667ms 차는 A/V 오차 보정치가 아니다.
- 기존 frame120/case_0005.00 수동 fixture의 너트는 x1114 부근, 카포 막대는 x1075 부근, 그 왼쪽에 실제 첫 금속 프렛 x1057이 보인다. 기존 frets에서 1은 숨김/2=x1057로 두었으나, 새 run에서는 x1057을 physical-fret **후보1**로 검수한다. 기존 2..7은 새 1..6 후보에 해당한다. 독립 사람 검수는 아직 없으므로 확정 번호로 승격하지 않는다.
- 카포는 너트와 별도 polygon으로 기록한다. 카포1 후보는 첫 프렛 칸 안의 clamp 위치를 본 에이전트 시각 근거다. 화면 코드/Capo 텍스트는 정답으로 사용하지 않는다. 확정 capo.value/relative_fret은 null 유지, relative_fret_candidate만 따로 제공한다.
- 새 `frames/*_board.json` 및 `*_strings.json`은 원본 MP4 SHA256 `source_id`, 별도 `case_id`, display-order `frame_index`, 실제 `frame_pts_s`, decoded-BGR `frame_pixel_sha256`, PNG `image_file_sha256`을 제공한다. 같은 프레임 PNG를 읽거나 픽셀 해시를 비교하고 결합할 것.
- 기하 상태는 ROI 정합(시각/영상 추적)과 정확한 프렛 결정 허용을 분리한다. 수동 근사 ROI에 정합했다고 접촉/정확 프렛을 확정하지 않는다. `contact_fret_decision_allowed=false`이면 손 원시 관측/후보만 보존한다.
- 문자열 부분선은 물리 현 번호 null로 유지한다. JSON의 screen_rank와 physical number는 별개다.

완료 산출물:
- `dataset/fretboard_review/runs/clip_003_012_20261103_v1/report.md`
- `same_frame_fixture.json`: 13개 대표 프레임의 같은 PNG/지판/현 경로.
- `frame_index_manifest.json`: 216개 본 구간+1개 경계 PNG/지판/식별자, 미실행 현204개 not_analyzed.
- `validation.json`: 실제217프레임/13현 JSON 해시·번호·보류 계약 검사 통과.
- `numbering_review.json`: 기존2..7→새 후보1..6, 카포/너트 분리 근거.
- `independent_reference_template.json`: 독립 사람이 아직 채우지 않은 원본-only 항목.

ROI 정합217개 valid지만 **정확 기하는217개 모두 suspect**, 접촉/정확 프렛 허용 false다. 실제 이동 최대약61.89px(PTS3.416667)을 포함한다. 현 후보5~6개, 물리 현 번호 확정0개. 독립 사람 검수0개. 결과를 이웃 프레임의 확정 운지로 전파하지 말 것.

`fretboard_frame_identity.py`의 `assert_same_frame/attach_frame_identity`와 `docs/FRETBOARD_SCHEMA_2026-11-03.md`를 계약으로 제공한다. legacy case_0005.00의 실제 PTS는5.041667초이며 사례명을 case_id로 보존한 변환 fixture가 있다.
