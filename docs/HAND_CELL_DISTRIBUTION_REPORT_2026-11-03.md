# 손 위치 분포 × 가상 현/프렛 칸 — 2026-11-03 (Asia/Seoul)

B 담당 구현 완료. A 실제 v2 grid 11프레임×6모델을 읽었고 기존 손/확대 관측을 재생했다. 외부API·새 모델추론·다운로드·설치0회. 기존 run·사람점·타담당 코드/README는 보존했다.

## 실제 연결 및 적분

- 실제 grid66개, 손끝/엄지 분포420개, 별도 검지 마디 가설252개. 합성 fixture는 별도 폴더만 사용하며 실제 run에 섞이지 않았다.
- A same_frame_fixture.json의 frames[].models[].grid_json을 사용하고 assert_grid_compatible로 source/index/PTS/pixel/canvas/M/M_inv/grid ID/version 일치를 확인했다. 결합키는(grid_id,cell_id)다.
- 원본 중심의 isotropic Gaussian을 원본에서 표본화한 뒤 M으로 투영해 각 polygon에 적분했다. 6원본px95%반경은 미보정 가정이며 위치 질량은 누름/발음 확률이 아니다.
- 점8192표본/마디4096표본, seed20261103. assigned+outside+unresolved+invalid 및 top3+other_cells+unassigned의 최대 보존 오차는0. 작은 꼬리는 유한표본에서0일 수 있다. 지판 안으로 재정규화하지 않는다.
- 최상위 칸 질량>0.9인 분포147개도 기존 보류를 유지했다. 최종 상태 {'abstain': 420}. crop/full 충돌·기하 미검증·ROI-only를 높은 질량으로 지우지 않았다.

## frame120 / 실제 PTS5.041667 / 원본·관측·추정·사람점

원본 PNG(수정 없음), 아래 분석은 같은 픽셀의 코드 시각화다. 주황=full관측, 자홍=실제 crop medoid, 흰×=Kim의 평가용 점. 청록 마디와 점선 가상 중심선/어두운 cell 테두리는 위치 가정이며 노란 선은 별도 관측 후보의 지지 구간이다.

![frame120 원본](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/frame_120_source.png)

![frame120 원본 오버레이](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000120_candidate_anchor_original.png)

![frame120 평탄 오버레이와 index 칸 질량](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000120_candidate_anchor_flat.png)

![frame120 index 위치 질량 열지도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000120_candidate_anchor_heatmap.png)

열지도는 full index 분포를 사용하며 공통 색상범위0~1이다. V는가상 현 구역, F?는물리프렛 후보 번호다. 빨간칸이 실제 누른칸이라는 뜻은 아니다.

## 바레 마디 별도 모델

검지5→6·6→7·7→8을 균등선분+Gaussian tube의 별도 가설로 표본화했다. 한 실제 손 관측의21점을 사용하며 손끝 medoid들을 섞어 새로운 손을 만들지 않는다. 여러 현 구역에 걸친 질량은 마디 위치 분포이며 실제 복수 누름이 아니다. 손끝 질량과 합치지 않는다. G 장면의 이 표현은 바레 검출 성공 사례가 아니다.

![검지 마디의 별도 칸 질량](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/frame120_segment_heatmap.png)

## ROI-only 미확정 / frame210 실제PTS8.791667

전체화면 손 관측이 없어도 확대의 실제 medoid를 별도 branch로 남겼다. 검지·중지의 multi-crop 지지는 같은 모델의 상관된 관측이며 실제 위치·접촉 확인이 아니다. 기하 보류와ROI-only를 유지한다.

![frame210 원본](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/frame_210_source.png)

![frame210 ROI-only 미확정 위치와 가상칸](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000210_candidate_anchor_original.png)

![frame210 평탄 위치 가설](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000210_candidate_anchor_flat.png)

## 실패/충돌 / frame215 실제PTS9.000000

crop마다 흔들려 보류했던 점들의 질량도 계산하되 실패 상태는 유지한다. 잘못된 중심이 좁은칸에 몰릴 수 있으므로 가상칸은 중심 오류의 해결책이 아니다.

![frame215 원본](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/frame_215_source.png)

![frame215 원본 충돌·미확정 오버레이](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000215_candidate_anchor_original.png)

![frame215 평탄 열지도](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/hand_cell_distribution/runs/virtual_cells_20261103_v4/clip003012_f000215_candidate_anchor_heatmap.png)

## anchor/간격 민감도(다른 grid를 결합하지 않음)

- 관측분기70개 중22개는6가정에서 최상위 가상 주소가 바뀌었다. 이 수는 정확도·정답오차가 아니라 시나리오별순위변화다. 각 모델은 다른grid_id를 가지며 유리한cell을 골라 한 운지에 합치지 않았다.
- anchor±3px·간격±10%·margin_only는 각기 별도 계산했다. grid_uncertainty_propagated=false이며 모델 간 분산을 보정된 통계 신뢰구간/확률로 평균하지 않았다.

| 관측 | baseline | anchor-3 | anchor+3 | spacing-10% | spacing+10% | margin only |
|---|---|---|---|---|---|---|
| (120, 'full_index') | s6_f3 | s6_f3 | s6_f3 | s6_f3 | s6_f3 | s6_f3 |
| (120, 'crop_medoid_index') | s6_f3 | s5_f3 | s6_f3 | s6_f3 | s6_f3 | s6_f3 |
| (210, 'crop_medoid_index') | s5_f3 | s5_f3 | s5_f3 | s5_f3 | s5_f3 | s5_f3 |
| (215, 'crop_medoid_pinky') | s1_f4 | s1_f4 | s1_f4 | s1_f4 | s1_f4 | s1_f4 |

## Kim 8점: 같은 추정 grid의 공간 비교만

이미 받은8점을 그대로 사용했고 재검수를 요청하지 않았다. 6개grid마다 사람 좌표의 공간 칸을 계산했다. 손끝은 분포 순위와, 검지5/6/7은 모델관절 위치 칸과 비교했다. 실제 현/접촉 프렛 정답이 아니므로 top1/top2 정확도는 만들지 않는다. Kim 좌표는 runtime 중심/가상선/간격 fitting에 사용하지 않았다.

| 점 | 사람 좌표 공간칸(baseline) | 모델 branch 최상위/위치칸 |
|---|---|---|
| 4 | 밖/미배정 | full_thumb:s6_f3; crop_medoid_thumb:s4_f3 |
| 5 | 밖/미배정 | full_joint_5:밖/미배정 |
| 6 | s2_f3 | full_joint_6:s2_f3 |
| 7 | s5_f3 | full_joint_7:s4_f3 |
| 8 | s5_f3 | full_index:s6_f3; crop_medoid_index:s6_f3 |
| 12 | s6_f4 | full_middle:s6_f4; crop_medoid_middle:s5_f4 |
| 16 | s1_f4 | full_ring:s1_f4; crop_medoid_ring:s2_f4 |
| 20 | 밖/미배정 | full_pinky:밖/미배정; crop_medoid_pinky:밖/미배정 |

## 실제 현 기반 이전 결과와 구분

- direct_string_comparison.json에 기존 실제선 검출 수·번호미해결·과거 중심 프렛 진단을 별도 보존했다. frame120/124/190의관측선5개,209~216은6후보이나 물리현번호확정은모두0이다. 이는6현정답 검출률이 아니다.
- 가상grid는 각프렛에6영역을 제공하므로 실제선 미해결과 무관하게 공간질량은 계산된다. 그6영역은 관측현이나 접촉을 대체하지 않는다. 셀 밖 프렛0~6의 나머지지판은 unresolved_geometry_mass, 지판밖은outside_board_mass로 나눈다.

## 제출·검증·한계

- manifest.json.records[].result_path: 실제 프레임/모델별 cell fixture. cells[].position_mass와 decision/reasons를 함께 넘긴다. segment 모델은 별도이고 중복독립증거로 합산하지 않는다.
- synthetic 계약: ../../fixtures/synthetic_contract/ 아래 synthetic_grid.json, observation.json, result.json. 실제 run은synthetic=false, 합성은true다.
- 단일6px분포·손 중심 오류·grid anchor/간격·번호/기하·접촉·발음은 미확정이다. 오디오60:40 등 결합은 D소유이며 이 모듈은 가중치나 오디오 점수를 구현하지 않았다.
- 재실행은 새 --output을 지정한다. 보고서 그림은 원본 PNG와 코드로 재현한 오버레이이며 생성형 편집사진이 아니다.

```powershell
python run_hand_cell_distribution.py
python summarize_hand_cell_distribution.py
python -m unittest test_hand_cell_distribution -v
```

## 실제 검사 결과

115개 통과/실패0. 상류 source/frame/PTS/pixel/canvas/M/grid 계약66개 재검증. API·모델추론·다운로드0회. verification.json에 입력 해시와 회귀 해시를 기록했다.

```powershell
python -m unittest test_hand_cell_distribution test_virtual_string_grid test_kim_hand_review test_hand_frame_contract test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector test_audio_analysis test_harmony_engine -q
```

## 총괄 전송 상태

완료 보고 전송을 시도했으나 자동 승인 검토가 거절했다. 이유는 수신 threadId `01a19c25-9b62-71c2-b30c-3dc5c15966de`로 후속 메시지를 보낼 직접 사용자 승인 근거를 이 발신 채팅의 trusted user messages에서 확인하지 못했다는 것이다. 전송 성공으로 기록하지 않았고 우회·재시도하지 않았다. 구현·검증·사진 산출물은 완료됐으며 총괄은 본 보고서와 `downstream_fixtures.json`을 직접 확인할 수 있다. `verification.json`에 coordinator_report_sent=false 및 거절 사유를 기록했다.

### 총괄 전송 완료 — 2026-11-03

이 발신 채팅에서 사용자가 직접 “보고해”라고 승인한 뒤 총괄 채팅 `01a19c25-9b62-71c2-b30c-3dc5c15966de`에 완료 결과·115개 검사·실제 fixture·사진 경로·현재 한계를 전송했고 성공 응답을 확인했다. 이전 거절은 이력으로 보존하며 현재 전송 상태는 완료다.
