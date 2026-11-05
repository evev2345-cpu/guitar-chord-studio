# 가상 현 × 프렛 구역 — 2026-11-03

원본 영상의 실제 11프레임(120,124,190,209~216)에 각6모델, 총66개의 조건부 grid를 생성했다. 외부 API/다운로드/설치0회. 원본·과거run·다른 담당 코드를 변경하지 않았다. v1은 초기 생성본으로 보존하고 최신은 이 v2다. 합성 검사는 별도이며 이 run은 실제 프레임이다.

## 의미와 가정

가상선은 마젠타, 실제 영상에서 추출한 **현 후보의 관측 지지 구간**은 노랑, 칸 경계는 파랑이다. 노란 후보도 테두리·반사일 수 있다. 가상6현을 관측6현 성공으로 세지 않는다. contact/sounding=unknown, physical_string_num=null, confidence_calibrated=false. 모든 exact geometry/contact는 보류한다. 위치 질량·접촉 확률·오디오 판단은 이 모듈에서 계산하지 않는다.

6번 현 쪽을 named low-E corner의 위쪽이라고 가정했다. baseline은 최상단 검출 후보를 anchor로 삼지만 실제6번 현 확인은 없다. 별도 margin_only_alternative은 관측 anchor 없이 너트/바디 위 여백을 각각 지판폭의10%로 둔다. 반대쪽 여백은 너트10%/바디14%라는 **검증되지 않은 설정값**이며 코드/TAB/손/오디오 정답에 맞추지 않았다. 이 값은 악기 치수 정답이 아니다.

각 끝점에서 `d=(지판폭-anchor쪽여백-반대쪽여백)/5`. 현 사이 간격은5개이며 전체 폭6등분을 하지 않는다. 너트와 바디의 d를 따로 계산해 x에 따라 보간한다. `y_k(x)=y_6(x)+(6-k)*d(x)`. 아래쪽6번 현 설정도 검사했다. 기준계는 연속 [0,W]×[0,H], x=0 너트·x=W 바디이며 원본 화면의 좌우와 분리한다.

가상 현 중간선을 구역 경계로 사용하고 최외곽은 지판 경계로 자른다. 프렛n 칸은 경계n-1~n으로만 생성한다. 누락·불명 번호는 건너뛰어 연결하지 않고 crossing 경계가 닿는 두 칸도 보류한다. 이 run은 프렛 후보0~6 범위만 제공하므로 바디 쪽 나머지 면적은 unassigned_board_area다. 원본 끝단이 마지막 실제 프렛이라는 확정도 없다. fret1의 기존 사용자 의미 확인은 boundary provenance에만 보존하며 가상 현·접촉 확인으로 승격하지 않는다. 미확인 카포 후보1은 상대 프렛에 가산하지 않는다.

## 실제 원본과 비교 사진

frame120, 실제PTS5.041667초. 원본 픽셀이며 생성형 편집/사람 정밀 좌표 GT가 아니다.

![frame120 원본](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000120.png)

frame120 baseline: 추정 가상선/칸과 관측 후보를 분리했다. 모든 칸 이름의 ?는 조건부 번호다.

![frame120 원본 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000120_candidate_anchor_raw.png)

![frame120 평탄 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000120_candidate_anchor_flat.png)

anchor±3 공통px, spacing±10%, 여백 대안의6개 모델 비교다. 수치는 baseline 대비 위치 변화이며 정답 오차나 확률구간이 아니다. 이 run 전체 최대 중심선 변위는 12.40 공통px다. 간격 오차는 독립 정답이 없어 미평가(null)다.

![frame120 민감도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/frame120_sensitivity_comparison.jpg)

## 프레임별 baseline

|frame|PTS|anchor nut/body|spacing nut/body|cells|
|---|---:|---|---|---:|
|120|5.041667|15.50/19.50|23.90/21.90|36|
|124|5.208333|14.50/19.50|24.10/21.90|36|
|190|7.958333|11.00/16.00|24.80/22.60|36|
|209|8.750000|11.50/15.50|24.70/22.70|36|
|210|8.791667|12.00/15.00|24.60/22.80|36|
|211|8.833333|11.00/16.00|24.80/22.60|36|
|212|8.875000|11.00/16.00|24.80/22.60|36|
|213|8.916667|11.00/16.00|24.80/22.60|36|
|214|8.958333|11.00/16.00|24.80/22.60|36|
|215|9.000000|11.00/16.00|24.80/22.60|36|
|216|9.041667|11.00/16.00|24.80/22.60|36|

## 실패·미확정 사례

frame124/190의 경계 후보 혼동,209~216의 가림과 공통 기하 오류 가능성을 해소하지 않았다. 동일 검출기의 설정·시간 일치는 독립적인 실제 현 증거가 아니다. 아래 사진은 가상 격자를 생성할 수 있어도 실제6번 현/접촉 성공을 뜻하지 않는 사례다.

frame124, 실제PTS5.208333: 관측 후보 노랑/가상 마젠타/기하 및 실제현 미확정.

![frame124 미확정 원본 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000124_candidate_anchor_raw.png)

![frame124 미확정 평탄 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000124_candidate_anchor_flat.png)

frame190, 실제PTS7.958333: 관측 후보 노랑/가상 마젠타/기하 및 실제현 미확정.

![frame190 미확정 원본 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000190_candidate_anchor_raw.png)

![frame190 미확정 평탄 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000190_candidate_anchor_flat.png)

frame215, 실제PTS9.000000: 관측 후보 노랑/가상 마젠타/기하 및 실제현 미확정.

![frame215 미확정 원본 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000215_candidate_anchor_raw.png)

![frame215 미확정 평탄 grid](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v2/clip003012_f000215_candidate_anchor_flat.png)

## 계약과 검증

`same_frame_fixture.json`에 원본 식별자·실제PTS·픽셀해시·원본PNG·upstream board JSON/hash·6개 grid ID/경로/그림을 제공했다. `grid_id`는 frame identity, M, fret provenance, assumptions, 버전의 해시이며 다른 민감도 모델은 다른ID다. cell_id는 grid 안에서만 유일하므로 결합키는 (grid_id,cell_id)다. observed_string_layer는 가상선과 별도 보존한다. assert_grid_compatible는 source/frame/PTS/pixels/canvas/M/M_inv/grid ID/version이 다르면 거부한다.

```powershell
python virtual_string_grid.py --output dataset/virtual_string_grid/runs/<새run>
python virtual_string_grid.py --validate-run dataset/virtual_string_grid/runs/clip_003_012_20261103_v2
python -m unittest test_virtual_string_grid test_fretboard_semantic_review test_fretboard_frame_identity test_string_detector test_fret_geometry test_baze_client -q
```

실제 검증: 11프레임/66모델 재구성 pass, 원본픽셀/상류JSON hash 및 overlay 존재 확인. 구역 면적 합과 프렛 띠 면적의 최대 차 4.37e-11 공통px². 구역 중복은 교차면적으로 검사하고 보드 외부는 포함하지 않는다. 이는 산술/계약 검증이며 지판 정밀도나 실제 현 정확도 평가가 아니다. 회귀 명령은 신규10개 포함42개 통과했다.

손 담당은 polygon에 위치 질량을 적분할 수 있으나 이 grid의 가정과 기하 보류를 함께 전달해야 한다. 각 민감도 모델을 별도로 평가하고 baseline만 확정값으로 사용하지 않는다. Kim8점 재검수 요청 없음. 다음 독립 자료가 부족한 항목은 실제 현 정체성·양끝 간격/여백·정밀 프렛 끝점이다. 완전6현 검출을 기다리지 않고 이 조건부 구역을 후속 실험에 제공한다.

총괄 직접 보고 전송은 자동 승인 검토에서 거절됐다(2026-11-03, Asia/Seoul). 이유: 해당 채팅으로 프로젝트 경로·구현·검증 정보를 전송할 직접 사용자 승인이 신뢰된 메시지에 없다는 판단. 구현 및 로컬 산출물은 완료했으며 전송 성공으로 기록하지 않는다.

총괄 전송 재검토도 거절됐다. read_thread에서 실제 userMessage 01a1a01b-8e4e-7510-954f-6dd43b88b252의 직접 보고 승인 원문을 확인했으나, 자동 검토는 도구 결과의 승인을 신뢰된 사용자 메시지로 인정하지 않았다. 전송은 완료되지 않았으며 추가 우회/재시도하지 않는다. 로컬 산출물은 완료됐고 현재 채팅의 사용자 직접 전송 승인이 필요하다.

이후 현재 담당 채팅에서 사용자가 '전송해'라고 직접 승인했고, 총괄 채팅으로 완료 보고 전송에 성공했다(2026-11-03, Asia/Seoul). 구현·42개 회귀·실제 fixture·사진·현재 한계를 전달했다.
