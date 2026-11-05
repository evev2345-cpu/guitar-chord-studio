# 가상 칸·오디오 결합 — 2026-11-03 (Asia/Seoul)

## 2026-11-04 P0 최종 — 실제30개 의미 유효성 연결 완료

총괄전송상태 갱신(2026-11-04 Asia/Seoul): 사용자가 본인채팅에서
“총괄 채팅에 직접 보고하는 거 승인할게. 방금 완료한 결과 전달해줘.”라고
직접승인했다. 이에 send_message_to_thread로 총괄채팅
01a19c25-9b62-71c2-b30c-3dc5c15966de(local)에 변경파일·78개검사결과·
실제30개재생·정확한입출력경로·사진·한계를 전송성공했다.
아래 전송거부기록은 이 직접승인 전의 이력이다.

상태: 오류체인의 하류사용차단 완료, 해부학적손복구 미완료.
오늘최종입력은 B의 anatomical_validity_20261104_v2/downstream_fixtures.json이다.
B v1 중단초안은사용하지않았다. 아래중간대기는해소됐고 총괄전송거부는남아있다.

변경: cell_audio_fusion.py, harmony_input_adapter.py, test_cell_audio_fusion.py,
신규 cell_fusion_semantic_review.py, docs/CELL_AUDIO_FUSION_SCHEMA.md 및자기보고서.
원본/기존run/타담당코드보존, API/새추론/모델다운로드/설치0.

실제6grid×5손끝=30개를재생했다. 18invalid(중지/약지/소지),
12unknown(엄지/검지)이며 모든가중치60:40/80:20/40:60/단일모달에서
그손가락의 rankable cell0 / 운지조합0 / 확정cell null / 접촉·발음unknown이다.
엄지·검지정성정상을정밀위치·발음valid로바꾸지않았다.

검증한계보: source/index/원시PTS/grid/픽셀/행렬, 원본sidecar이전파일SHA,
원관측·질량불변, 사용자review JSON/검수사진SHA, baseline ROI원시21점,
robust crop0전체21점동일, 손가락별medoid view_id/bounds/hand_index/전체손SHA.
B의resolve_medoid/anatomical_validity 공개API로정책을재계산해상류상태와대조했다.
다른crop/시점에invalid를전파하지않고 누락·계보불일치는unknown/명시거부다.
분포와cell의 allowed=false는독립hard gate로소비한다.

| 항목 | 원래자료 | 오늘하류처리 |
|---|---|---|
| 관측좌표·cell질량 | 원본그대로 | 해시·배열검사로불변확인, 진단보존 |
| 소지최고칸질량 예시 | .982055664 | invalid, 점수null, 배정0 |
| 중지/약지/소지 | 잘못된원시체인 | 18invalid, 손가락이름교환/좌표복원0 |
| 엄지/검지 | 정성적대체로정상 | 12unknown, 정밀/발음허용false |
| 이전실제D 18건 | 이미기하보류로조합0 | 오늘은frame210의별도30개, 의미게이트를추가검증 |

어제D의18건은frame124/190/215여서 frame210전후정확도비교대상이아니다.
동일frame210의sidecar전 B원본과오늘자료는 좌표·질량이같고 의미상태만추가됐다.
기하보류가없고 V=.99/A=1인합성통제에서도 invalid/unknown을차단하므로,
실제자료의기하보류때문에우연히0이된회귀가아니다.

![실제frame210 원본, PTS8.791667](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/original.png)

![사용자가검수한baseline ROI 원시21점실패](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_skeleton_only/runs/frame210_20261103_v1/baseline_roi_hand_zoom.png)

원본픽셀에기존21점을연결한사진이다. 사용자는이branch의중지혼합·약지/소지
대응오류를확인했다. 정밀좌표·다른crop·접촉정답으로확대하지않았다.

![실제30개중한grid의원질량과의미게이트](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_semantic_frame210_20261104_v5/actual_semantic_gate.png)

왼쪽회색은unknown, 빨강은invalid인원질량이다. 오른쪽은배정가능칸수0이다.
원점수나위치질량을0으로덮어쓰지않고 별도유효성을적용한결과다.

![동일frame의원시단일손대안, 다른crop은미검수](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/whole_hand_comparison.png)

초록선은각view의원시21점연결이며 정답색이아니다. 좌상baseline만검수됐고
나머지3개crop을모두invalid로판정하지않았다. 손가락별좋은점을합성하지않았다.

![합성 고질량·고음향점수 스트레스회귀](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/semantic_gate_20261104_v4/semantic_gate_comparison.png)

```powershell
python cell_fusion_semantic_review.py --output dataset/cell_audio_fusion/runs/semantic_gate_20261104_v4
python cell_fusion_semantic_review.py --hand-root dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2 --output dataset/cell_audio_fusion/runs/actual_semantic_frame210_20261104_v5
python -m unittest test_cell_audio_fusion test_hand_anatomical_validity test_hand_cell_distribution test_harmony_engine test_audio_cell_compatibility -q
```

최종선택검사78개통과/실패0, Fusion19개. 실제30개전체재생을고정회귀에포함했다.
invalid/unknown/점수0/음향결측null구분, 높은질량/오디오/모든가중치비복구,
분포·cell허용false, 좌표·pixel·rawview계보변조거부, 다른crop정책비전파,
오류손가락의MIDI/코드조합제외를검사했다. 4개변경Python py_compile도성공했다.
초기30개어댑터실행은단일분포wrapper의추가provenance2필드때문에중단됐다.
모든실측필드동일은유지하고그2개추가필드만허용한뒤새run에서재실행했다.
실패한중간run과기존run은삭제·덮어쓰기하지않았다.

정확한입력인덱스:
`C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/anatomical_validity_20261104_v2/downstream_fixtures.json`.
정확한출력root:
`C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_semantic_frame210_20261104_v5/`.
summary.json은6grid별상태/원질량/원본불변해시,
single_fixture_replay.json은30개정확입출력경로·상태·배정0,
각grid하위input.json/result.json과 crop_medoid_*_result.json은전체근거다.

업무구현차단없음. 실제정확도/체인복원/누락소지복구는미검수다.
총괄직접전송은자동승인검토가명시승인부족으로거부해재시도하지않았다.
이보고서와본인채팅에서완료결과를제공하며 전송실패는코드검증과별개다.

## 2026-11-04 P0 의미 유효성 게이트 — 중간 기록

총괄전송상태: send_message_to_thread 호출이 자동승인검토에서 거부됐다.
사유는 기존총괄채팅으로의 명시적 전송승인이 부족하다는 판정이다.
전달된사용자승인문구를 근거로 시도했으나 재시도/우회하지 않았다.
전송실패는실행차단과별개이며 본파일과본인채팅으로산출물을보고한다.

상태: 합성계약 구현·독립회귀 완료, 손담당의 정확한 raw21 계보 sidecar
도착 전 실제정책연결은대기. 검수사진/manifest를읽고 해시를확인했으나,
그것만으로 crop medoid나같은프레임전체를오류판정하지않았다.
새 semantic_state 게이트는 invalid/unknown/누락을 점수0/음향결측과구분한다.
다섯가중치 모두 오류체인의칸·MIDI·운지조합진입을차단하고 원점수는보존한다.

합성 raw V=.99/A=1 스트레스입력 결과는
`runs/semantic_gate_20261104_v1/`에3종입출력/summary와사진으로저장했다.
Fusion16개회귀통과. 이전35/116개등과합산하지않는다. 실제 raw hand
sidecar가도착하면 source/index/PTS/pixel/관측ID/branch/whole-hand hash를
대조하여연결할준비가됐다. 다른crop에는정책을일괄전파하지않는검사도통과했다.

![합성 semantic 유효성 게이트, 실제 frame210 점수아님](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/semantic_gate_20261104_v1/semantic_gate_comparison.png)

![사용자검수원본 baseline ROI 스켈레톤, frame210 PTS8.791667](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_skeleton_only/runs/frame210_20261103_v1/baseline_roi_hand_zoom.png)

위스켈레톤은기존실제21점의연결이며중지/약지/소지의의미대응실패가검수됐다.
합성게이트그림과정확도/좌표정답으로연결하지않았다. raw21복구·체인복원은미수행.

## 최신 실제 A v2 / B / C API 연결 — 대기 해소 후 검증

상태: 독립 구현과 실제18건 연결·검증 완료. 아래 초기 상류대기 기록은
과거시점이다. A v2 3프레임×6모델과 실제 B 자료가 도착해 연결했다.
C의 기존 공개 compare API를 실제 Demucs v5 반주에 호출하여 해당grid의
오디오칸점수를 계산했다. C 코드는 수정하지 않았다. C가 먼저 제공한
synthetic_frequency_hypotheses_72cells 결과는 실제grid와 ID가 달라
결합을 거부하는 회귀로 보존했다.

새 cell_audio_fusion_replay.py와 harmony_input_adapter의 owner adapter를
추가했다. 실제 B의 full_observation만 선택하며 crop_medoid/엄지/마디를
독립손가락으로 합치지 않는다. B 원본 전체를 별도보존한다. B의
unassigned_mass가 outside/unresolved를 포함하므로 중복질량을 빼고
배타적잔여로 변환하며 원래값도 유지한다. A v1→v2는 grid ID/칸/행렬
동일, geometry_status/upstream_geometry_validity만 다르다는 것을 검증해
메타데이터개정 provenance를 기록했다. polygon이 바뀌면 거부한다.

C 비교의 표준튜닝은 **명시적인실험가정**이며 확인값이 아니다.
capo=null 유지, 물리프렛후보로만 계산한다. 정확기하·현정체성·발음은
확정하지 않는다. exact_frequency_score 하나만 A로 사용하고 PC/지속
피크점수나 반주코드점수를 추가가산하지 않는다. 반주화성은 별도진단필드다.

```powershell
python cell_audio_fusion_replay.py --output dataset/cell_audio_fusion/runs/actual_abc_20261103_v4
python -m unittest test_cell_audio_fusion test_harmony_engine test_audio_analysis test_virtual_string_grid test_hand_cell_distribution test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector -q
```

실제18/18 재생오류0. 현재 전체116개통과/실패0, Fusion12개.
실제owner bridge, A메타데이터개정, polygon변경거부, 합성C격자결합거부를
추가회귀로 검사했다. 원본/타담당파일/기존run 수정0, API/다운로드0.

| 실제프레임/PTS | 60:40 | 80:20 | 40:60 | 영상단독 | 음향단독 |
|---|---|---|---|---|---|
| 124 / 5.208333 | 기하보류 | 기하보류 | 기하보류 | 기하보류 | 기하보류 |
| 190 / 7.958333 | 기하보류 | 기하보류 | 기하보류 | 기하보류 | 기하보류 |
| 215 / 9.000000 | 기하보류 | 기하보류 | 기하보류 | 기하보류 | 기하보류 |

각프레임6모델 모두 geometry=suspect, 입력손 판단도보류이므로 가중치로
이를해제하지 않았다. 실제결합순위/조합0이며 최적비율·정확도개선은 미평가다.
가중치에 따른 순위변화 검증은 아래 명확히 표시한 합성fixture에서만 한다.

실제원시진단(결합결정 아님): frame124 약지의 공간top칸은 spacing+10%에서
s1_f4→s2_f4로 바뀐다. frame190 중지는 candidate_anchor의s3_f3에서
anchor+3/spacing+10%/margin-only의s4_f3로 바뀐다. 모델마다 따로 계산하고
유리한 칸만모아 한운지로 합치지 않았다. frame215는 선택한 full branch가
없어 영상질량을 만들어채우지 않았다. 0질량의 임의top칸은null로 표시한다.
오디오의 raw top칸은 각각 s1_f4 / s2_f1 / s1_f4이며, 피아노/배음도
설명가능하므로 기타운지정답이 아니다.

![실제frame124 원시 영상질량과 음향호환성, 결합판단보류](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/clip003012_f000124_candidate_anchor/raw_modalities.png)

세로6→1은 가상현, 가로는 물리프렛후보다. 왼쪽색은 full손가락들의
원질량최댓값, 오른쪽은 명시튜닝가정하의 오디오호환성이다. 색척도의
의미가다르고 누름확률이아니다. 원본과가상grid사진은 아래 본문을참조한다.

![실제frame190 원시 칸점수 진단](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/clip003012_f000190_candidate_anchor/raw_modalities.png)

![frame215 full손부재·기하보류 실패사례](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/clip003012_f000215_candidate_anchor/raw_modalities.png)

아래 frame215 / PTS9.000000의 원본픽셀 기반 기존손후보 오버레이는
상류실패의 맥락이다. 색점은 같은모델의 crop관측, 보류표시를 접촉으로
승격하지 않았다. 이번fusion이 그 중심점을 이동하거나 복구한 것이 아니다.

![실제frame215 crop불일치 원본사진](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/integration_review/runs/robust_candidates_20261103_v2/frame_215_hand_reliability.png)

![실제5가중치결합은보류로빈열지도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/clip003012_f000124_candidate_anchor/heatmap.png)

정확한실제산출물:
`dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/summary.json`,
그 아래 `clip003012_f000124_candidate_anchor/input.json` 및 `result.json` 등
총18개모델별입출력이다. 각파일에 A/B원본경로·해시·C구현해시·오디오fixture
해시·원시점수·기하/crop등급·반주화성을보존한다. 다른모델민감도도summary에 있다.
이번담당범위차단은없고, 실연순위의유효성검증에는 기하/현/접촉등의상류
근거가여전히부족하다. Kim8점재요청0, 사람평가좌표를런타임입력으로사용0.

상태: D 독립 구현·합성 계약 검증 완료. 실제 A grid 연결은 정상 보류로
재생했으며 B 영상질량/C 실제칸점수 산출물은 현재 탐색 시 아직 없어
실제 결합 검증은 부분 대기다. 없는 실제 점수는 만들지 않았다.

신규 cell_audio_fusion.py, test_cell_audio_fusion.py,
docs/CELL_AUDIO_FUSION_SCHEMA.md 및 harmony_input_adapter.py의
fusion_pending_from_grid를 작성했다. 공용README/타담당코드/원본/기존run
수정0, API/모델다운로드/설치0. 결과는 모두 새run이다.

## 가중치 비교 — 합성 계약임

V는 지판 내부로 재정규화하지 않은 위치 질량, A는 [0,1] 휴리스틱 호환성이다.
범위만 같고 확률의 의미는 다르다. 누름·발음 확률이나 최적 가중치가 아니다.

| 실험 | 검지 칸 top1 | 중지 칸 top1 | 상충·중복제약 후 top1 조합 | 조합점수 |
|---|---|---|---|---:|
| 60:40 | s5f2 .480 | s4f3 .510 | 검지s6f1 + 중지s4f3 | .455 |
| 80:20 | s6f1 .500 | s6f2 .460 | 검지s6f1 + 중지s4f3 | .440 |
| 40:60 | s5f2 .620 | s4f3 .640 | 검지s6f1 + 중지s4f3 | .470 |
| 영상단독 | s6f1 .600 | s6f2 .550 | 검지s6f1 + 중지s4f3 | .425 |
| 음향단독 | 여러칸 .900 동률 | 여러칸 .900 동률 | 손가락배정 없음 | — |

개별top1과 조합top1은 다르다. s6f1/s6f2는 같은 가상현의 상충 프렛이라
동시배정을 거부한다. s5f2/s4f3의 동일 shared_peak는 두 번 더하지 않는다.
조합점수는 입력손가락수로 나눈 가중합이며, 최상위 칸을 단순 합친 것이 아니다.
누락·보류 점수는null이며 별도 단일모달 결과만 보여준다. 한 grid variant의
칸만 조합한다. 후보수가 작은 beam search이고 바레·한현의복수손가락은
추론하지 않는 보수적 제약이다. 정확도 향상이나 적중률을 주장하지 않는다.

![합성 계약 가중치별 칸 열지도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/contract_20261103_v2/heatmap.png)

위는 합성 grid/점수이며 실제 영상 오버레이가 아니다. 세로6→1은 가상현,
가로는 물리프렛후보다. 색은 손가락별 점수 중 최댓값, 흰색은 결측이다.

## 실제 frame124 — 원본과 추정 grid, 현재 보류 사례

원본 frame124 / 실제PTS5.208333. 아래 원본은 실제디코딩픽셀이다.
화면TAB·코드표기는 점수입력으로 사용하지 않았다.

![원본 frame124 PTS5.208333](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/fretboard_review/runs/clip_003_012_20261103_v1/frames/clip003012_f000124.png)

아래는 A담당이 코드로 만든 추정grid다. 자홍색 가상모델과 노란 실제선
후보는 확정현/누름이 아니다. grid의 geometry_status=unverified를 그대로
보존하며, anchor·간격·번호 출처도 확인되지 않은 가정으로 유지했다.

![A의 실제픽셀 위 가상grid 후보](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/virtual_string_grid/runs/clip_003_012_20261103_v1/clip003012_f000124_candidate_anchor_raw.png)

실제 grid만 연결한 입력 `fixtures/actual_grid124_pending.json`은 B/C 점수가
빈 상태다. 따라서5가중치 모두 geometry_withheld, 조합0이다. 손8점검수나
프렛의미확인만으로 음·접촉을 만들지 않았고, 합성 점수를 여기에 붙이지 않았다.

![실제 grid 미검증·상류점수부재로 비어있는 열지도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_grid124_pending_20261103/heatmap.png)

## 실패 회귀와 검증

![합성 기하보류 실패회귀](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/geometry_withheld_20261103_v2/heatmap.png)

기하보류는 음향 점수가 높아도 복구하지 않는다. 위 그림은 합성 실패입력으로
기하보류 게이트를 재현한 것이며, 실제 검출 실패율을 뜻하지 않는다.

```powershell
python -m unittest test_cell_audio_fusion test_harmony_engine test_audio_analysis test_virtual_string_grid -q
python cell_audio_fusion.py --input dataset/cell_audio_fusion/fixtures/synthetic_contract.json --output dataset/cell_audio_fusion/runs/contract_20261103_v2
python cell_audio_fusion.py --input dataset/cell_audio_fusion/fixtures/actual_grid124_pending.json --output dataset/cell_audio_fusion/runs/actual_grid124_pending_20261103
```

위 unittest 현재66개통과/실패0. Fusion10개: 원본/시간/grid/행렬불일치 거부,
질량범위·소실보존, 결측비충전, 양모달불량/기하보류, 같은현충돌/손가락중복,
같은오디오중복가산, 반주코드재가산방지, 실제grid빈점수, 보류손복구금지 검사.
세 CLI 성공. 그림파일 실제존재 확인, 합성열지도와 실제grid원본오버레이를
직접 열어 시각검수했다. 기존 초기run도 보존했고 레이아웃수정은v2로 저장했다.

산출물: runs/contract_20261103_v2/result.json,
runs/geometry_withheld_20261103_v2/result.json,
runs/actual_grid124_pending_20261103/result.json과 각각heatmap.png.
상류경계는 docs/CELL_AUDIO_FUSION_SCHEMA.md에 명시했다. B는 cell별원질량과
crop/기하등급, C는 같은source/PTS/grid/frame/canvas/M의 정규화호환성·evidence IDs가
필요하다. C의 exact/persistent/PC진단을 각각 더하지 않고 정해진A 하나만 사용한다.
실제B/C도착 후 자기어댑터에서 엄격검증하여 연결한다. 현재 실연코드·현별발음은
미확정이며 반주화성/운지가설/확정기타필드는 분리돼 있다.
