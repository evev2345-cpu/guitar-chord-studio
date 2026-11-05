# Offline string review

API calls: **0**. Cached board geometries reused. No chord-name module implemented.

## Manual reference limitations

Points were manually selected by the coding agent from unoverlaid original-image inspection strips. They are provisional visual references (approximately +/-1.5 original px), not independent user-verified ground truth. Four clear lines per frame were labeled; two thin/border-adjacent lines were excluded. Metrics are for these 12 labeled lines only, not six-string accuracy.

| Frame | Mode | Candidates | Matched / labeled | Mean original px | Missed references | Unmatched candidates |
|---|---|---:|---:|---:|---:|---:|
| case_0005.00 | 800x150 | 5 | 4/4 | 0.521 | 0 | 1 |
| case_0005.00 | high | 5 | 4/4 | 0.460 | 0 | 1 |
| case_0194.86 | 800x150 | 4 | 4/4 | 0.830 | 0 | 0 |
| case_0194.86 | high | 5 | 4/4 | 0.663 | 0 | 1 |
| case_0206.03 | 800x150 | 5 | 4/4 | 0.786 | 0 | 1 |
| case_0206.03 | high | 5 | 4/4 | 0.658 | 0 | 1 |

## Resolution

The tutorial source is 1280x720. Its cached board spans roughly 684 original pixels in length and 67-82 pixels across the neck. Thus 800x150 already upsamples these dimensions; it does not discard native vertical samples in these cases. The high-resolution branch warps directly from the original image and avoids chaining through 800x150; it cannot create information missing in the video. Changes in matched counts are algorithm/resampling effects, not proof of restored physical detail.

## Failure cases

See failure_photo_raw.png and failure_photo.json. Variable candidates and unresolved physical identities are retained. Candidates can include board edges or reflections; unmatched candidates are NOT automatically false positives because only four clear reference lines were labeled.

## Coordinates and identity

JSON contains source/video/frame identifiers, hashes, image/canvas sizes, detection-to-common scale, M/M_inv/M_detection, preserved fret numbers/sources, per-line model and visible intervals, screen rank and separate physical string_num/number_source. A partial line set is not assigned physical numbers. Six-line numbering, when plausible, is explicitly inferred from physical corner sides and is not a direct observation of identity. No missing line is synthesized to reach six.

## Artifacts

- resolution_comparison.jpg: actual detected lines; yellow evidence-supported intervals, dashed magenta model continuation outside support intervals; no explicit reference estimates supplied in this run.
- *_high_raw.png and *_800x150_raw.png: original-frame overlays.
- manual_string_references.json: editable original-pixel manual reference points.
- *_manual_reference.png: reference-only green segments.
- evaluation.json: detailed assignment and per-point errors.

## 2026-11-03 담당 후속 검수 (Asia/Seoul)

3~12초 공동 구간의 새 run을 `dataset/fretboard_review/runs/clip_003_012_20261103_v1/`에 보존했다. 이전 결과/수치는 지우지 않았다. 상세 보고서는 새 run의 `report.md`, 통합 계약은 `docs/FRETBOARD_HANDOFF_2026-11-03.md`, `docs/FRETBOARD_SCHEMA_2026-11-03.md`다.

- 외부 API0회. 원본 PTS 기준216프레임+12초 경계1프레임에 같은 PNG·지판·프렛·원본/픽셀/파일 해시를 제공했다. 13대표 프레임에는 부분 현 후보도 제공했다.
- 기존 영상 수동 fixture의 x1057 금속선이 너트에서 첫 프렛 후보로 보여, 기존2..7→새 후보1..6을 검수했다. 카포 막대는 x1075부근이고 원 너트 x1114와 다르다. 확정카포/물리번호/상대번호는 아직 unknown/null이며 수동 후보만 별도 저장했다.
- 원본 PTS와 index/24는 이 구간에서41.667ms 차이가 있다. 실제 A/V 지연의 확정값이 아니다. 색 변환을 맞춘 FFmpeg와 OpenCV의7개 프레임 BGR 해시가 정확히 일치했다.
- 약3.42초 지판 끝 이동61.89px를 검출했다. ROI 정합이 되어도 독립 기하 정답은 없으므로 정확기하217개 suspect, 접촉/정확프렛 결정보류를 유지한다.
- 추가32개 원본 점(4프레임×4선×2점)은 에이전트 사후 시각 참조다. 16선 중15선이 원본3px 매칭에 대응했으나 독립 성능 평가가 아니다. 기존 본문0.59px도 독립정답 또는6현 정확도로 승격하지 않는다.
- 독립 사람 검수0개. 원본-only `independent_reference_template.json`은 비워 둔다.

회귀26개와 실제217프레임/13현JSON 계약검사가 통과했다. 공용 README와 다른 담당 소유 파일은 변경하지 않았다.

총괄 직접 완료 보고 전송 성공(2026-11-03, Asia/Seoul). 상세 경로·남은 독립 검수 요구를 전달했다.


## 2026-11-03 사용자 의미 검수 후속 v2

새 run: `dataset/fretboard_review/runs/clip_003_012_20261103_v2_semantic/`. 사용자 확인3개 객체/첫 금속선 번호1은 frame120에만 적용했다. 생성형 표시 이미지의 의미 확인이므로 원본 정밀 좌표/독립GT는0개다. 기존 번호 전체-1을 적용하지 않았고 이미1인 번호는 유지했다. 각 후속선은 개별 원본/노출 프레임 근거를 보존하며 frame120의3번 후보는 가림/추정이다.

217프레임 원본 재디코딩·PTS/픽셀/PNG 해시·이동 재계산 검증과13개 동일프레임 현 JSON을 제공했다. 정확 기하/contact false, 카포/상대 프렛 확정null, 물리 현 번호null 유지. 회귀32개 통과. 외부 유료 API/업로드0회. 상세 변화/한계는 새 run `report.md`와 `docs/FRETBOARD_SEMANTIC_SCHEMA_2026-11-03.md`에 기록했다. 손 검수8점 및 오디오 혼합 확인은 다른 모듈 증거로 분리했다.
