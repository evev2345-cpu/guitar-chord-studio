# Audio-cell compatibility v1 — C 담당 계약 (2026-11-03)

구현: `audio_cell_compatibility.py`. 기존 오디오 분석·grid 생성·손 분포·최종 가중치 fusion과 분리된 후보 대조 모듈이다. 정답 코드/TAB/사람 평가 좌표를 입력으로 쓰지 않는다.

## 입력과 동일성

`compare(cells_record, audio, tuning=None, capo=None, tolerance_cents=50)`.

cells_record: source_id(MP4 SHA-256), start_s/end_s, timebase=source_video_seconds, grid_id/grid_version, cells[] 및 명시적인 tuning/capo 설정. 실제 grid 입력이면 frame_index/frame_pts_s/frame_pixel_sha256가 필요하며 프레임 시각이 선택 창 안에 있어야 한다. 현재 원본 format start=0으로 frame PTS와 원본 재생 초가 같다. 다른 원본의 비영 format start는 상류에서 재생시간 매핑을 확정해야 한다.

`adapt_grid(grid,start,end,tuning=...,capo=None)`는 A의 virtual_string_grid.v1, synthetic=false를 받아 원본 식별자·M/M_inv·canvas_size·기하/anchor/spacing/numbering 상태와 cell polygon을 보존한다. 가상 grid를 재검출하거나 번호를 보정하지 않는다. 실제 run은 A의 assert_grid_compatible(grid,cells/result)와 원본 decoded BGR 해시도 검증했다. source/frame/PTS/pixel/canvas/M/grid version이 다른 결과는 결합하지 않는다.

합성 cell은 data_origin=synthetic_cell_hypotheses를 명시하며 실제 프레임 hash를 꾸미지 않는다. 실제grid와 실제audio를 쓴 결과도 물리 현·접촉·정답 셀은 미확정이다. 결합키는(grid_id,cell_id)이고 서로 다른모델의 유리한 셀을 한 운지로 합치지 않는다.

## 예상 음: 명시 가정

튜닝 객체 예: {"midi_6_to_1":[40,45,50,55,59,64],"status":"assumed","source":"explicit_standard_assumption"}. null/미확인 튜닝에는 예상 MIDI가 없고 점수도null이다. assumed/confirmed를 명시해야 한다.

물리 프렛p는 open_string_midi+p이며 카포를 다시 더하지 않는다. 상대 프렛r만 있으면 카포c가 명시된 경우만 open_string_midi+c+r를 계산한다. 상대/물리 프렛이 함께 있고 카포를 알면 일치 여부를 검사한다. null 또는 fret=null인 unknown capo는 정상이다. 물리 프렛 후보의 주파수 비교는 가능하지만 카포의 실제 유효성은unknown이다. 명시된 카포 뒤쪽 프렛이나 상대/물리 모순은 거부한다. 표준튜닝은 현재 실제 클립의 확인된 튜닝이 아니라 실험 가정이며 440Hz A4/12TET를 사용한다.

## 별도 호환성 지표

모든 score는 0~1 휴리스틱이고 음·누름·발음 확률이 아니다.

1. exact_frequency_score: 선택창에 전체 지지가 포함된 spectral peak 중 같은 분석프레임에서 최대 `relative_peak_amplitude * max(0,1-abs(cents_error)/50)`를 취한 뒤 평가프레임에 대해 평균한다. 주파수 오차허용은 설정값이다. 프레임 분모는 chroma의 전체창 지지와 관측 peak 지지의 합집합이다. 분석 peak가 없는 프레임은 후보지지가 없는 것이지 실제 음이 없다는 정답이 아니다. 정확히 일치한 피크도 배음/피아노일 수 있다.
2. persistent_frequency_score: 주파수 허용내 track의 상대진폭×같은cents커널×해당창과 겹치는 비율 중최대값. track의 원래시간 지지/교집합/evidence_ids/harmonic_ambiguities를 보존한다. 겹친 창의 지속 피크이지 기본음·음표길이 정답이 아니다.
3. pitch_class_score: 같은 완전 지지 창의 원래12차원 salience에서 예상PC 성분의 평균이다. octave_alternatives에 옥타브 차이와 원래frequency/cents/MIDI차를 남긴다. 같은PC라도 exact로 승격하지 않는다.

기본 audio_compatibility_score는 **exact_frequency_score만** 사용한다. persistent/PC를 독립확률처럼 곱하거나 임의 가중합하지 않는다. PC-only 점수는 보조 근거이며 최종A로 몰래 바꾸지 않는다. 따라서0.6V+0.4A 실험의 A 의미는 명시적인 relative frequency compatibility다. 이 비율의 최적성이나 calibration은 C 담당이 주장하지 않는다.

배열 자체가 없으면 해당 score=null/availability=missing이다. 배열이 있으나 해당창에 후보가 없으면 present_empty/score0이며 이는 no_matching_candidate_evidence다. 입력은 있는데 다른옥타브/PC만 지지하면 pitch_class_only_support다. expected pitch가 미확인일 때도null이다. 검출 실패·약한음·실제무음·뮤트를 구분할 정답이 없으므로 contact/sounding/instrument_attribution은unknown을 유지한다.

frequency_matches에는 event_id/time support/frequency/cents/midi_delta/resolution/score_type/vocal-stem-near IDs를 보존한다. source_identity와 Demucs/user review provenance도 출력에 남는다. 반주는 사용자 확인된피아노포함 accompaniment이고 derived_from_separation=true/guitar_isolation_verified=false다.

## D adapter

`to_fusion_audio(result)`는 D의 fusion_cell.v1용 audio branch를 만든다. 최상위 동일성(source/grid/frame/pixel/canvas/M/start/end/timebase)을 보존하고 cells를cell_id dict로 변환한다. score_type=normalized_compatibility_0_1, cells[cid].score=exact-frequency 지표, evidence_ids=해당exact 피크ID, evaluation_status=C 상태다. null을0으로 채우지 않는다. PC-only/미검출의 평가된0도상태로명시한다.

quality_status=usable은 특징대조가 계산가능하다는 뜻이며 기타음/기하가 확인됐다는 뜻이 아니다. quality_scope에 이 의미를 남긴다. D는 grid.geometry_status=suspect와 접촉보류를 별도로 지켜야 한다. 다른모델의 같은cell_id를섞지않는다.

## 실제 산출물과 재현

- 실제 원음/stem 후보: dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5/
- 합성72cell×실제3창: dataset/audio_analysis/runs/audio_cell_compatibility_20261103_v1/
- 실제3대표프레임124/190/210×6모델×3stem: dataset/audio_analysis/runs/audio_cell_actual_grid_20261103_v3/bundle.json

bundle.frames[].models[].components.accompaniment의 result/small_fixture/fusion_audio에 정확한 절대경로가 있다. model_name별 grid_id를 보존한다. small fixture는 score를 보기 전 선택한물리프렛1 후보×6가상현이고 전체36cell은result에있다. 원음/보컬도같은형식이다. baseline/에원본+가상grid호환성그림이있다.

```powershell
python audio_cell_grid_demo.py --grids dataset/virtual_string_grid/runs/clip_003_012_20261103_v2 --audio-parent dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5 --output dataset/audio_analysis/runs/audio_cell_actual_grid_replay --all-models
python -m unittest test_audio_cell_compatibility test_audio_analysis -v
```

선정편향: 오디오창은기존고정3창이고안정정답이아니다. 대표프레임은해당창내124/190/210이며frame120/PTS5.041667은첫창5.05보다앞이라강제결합하지않았다. 전체11프레임·전체66grid를분석했다고주장하지않으며18grid/54오디오대조다. 셀미세간격은오디오만으로검증할수없고, 동일한현/프렛label이면anchor/spacing변화에도A는동일하다. 실제공간질량변화는B/D가다룬다.
