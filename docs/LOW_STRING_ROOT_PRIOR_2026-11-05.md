# 저음 현 가중치를 유지한 근음 동점 비교 — 2026-11-05

사용자가 제안한 방향으로 **현·프렛 정보를 유지하는 저음 현 근음 가점**을 구현했다. 동일 구성음·동일 오디오 점수의 후보에만 적용하며, 일반 코드의 음집합이나 점수를 바꾸지 않는다. 실제214초사례에서는위치근거가약하고중지검출포함여부에민감해 **두후보를계속유지했다.**

## 구현

- 실제화면의위/아래가아닌가상현번호를사용한다.6번1.0,5번0.8,4번0.35,3번0.15,2번0.05,1번0.025로가점을준다.
- 손끝의확률적위치가해당현·프렛칸을얼마나지지하는지계산한뒤그칸의실음PC와후보근음을비교한다. 단지그위치에근음이존재한다는이유로가점하지않는다.
- 같은칸을여러손가락이중복지지하면최댓값만써서손가락오인중복으로점수가부풀지않게했다.
- 기존정책대로중지를제외한경우와, 불안정한중지를0.25가중치로포함한민감도검사를둘다보관했다. 후자는확정근거가아니다.
- 저음현근거·점수차·비전검증상태가부족하면자동순위변경하지않는다. 기준은고정했고사용자정답에맞춰탐색하지않았다.

저음이항상근음은아니므로, 이값은전위코드를제외하는규칙이아닌약한선호다. 개방현·뮤트·실제접촉을손끝부재로추론하지않았다. 튜닝은미확인표준EADGBE이며물리프렛에카포가이미포함돼실음근음C/A로비교하고화면표기B/G#로환산한다.

## 실제214초 위치 근거

![214초 원본과 저음 현 근음 후보 칸](../dataset/integration_review/runs/low_string_root_20261105_v1/low_root_cells.png)

노란영역은A(화면G#)근음이가능한6번현물리5프렛칸, 청록영역은C(화면B)근음이가능한5번현물리3프렛칸이다. **가상칸이며실제로눌렀다는표시가아니다.** 점은현재손모델의원본랜드마크, 원은기존12픽셀위치불확실성범위다. 주황중지점은해부학적의미가미검증이다. 점을정답위치로수동수정하지않았다.

기존‘PC전체합산’에서사라지던현번호와프렛위치는이번계산에서유지된다. 다만핵심근음위치가불안정한중지주변에있어서, 모델이저음현을명확히누르고있다고보장할수는없다.

|원본초|중지 처리|B6 근음 지표|G#m7 근음 지표|B6의6·5번현근거|G#m7의6·5번현근거|결정|
|---|---|---:|---:|---:|---:|---|
|213.791667|middle_excluded|0.11404|0.00748|0.00000|0.00000|보류|
|213.791667|middle_downweighted_0_25|0.11404|0.00748|0.00000|0.00000|보류|
|214.000000|middle_excluded|0.03973|0.01053|0.00000|0.00000|보류|
|214.000000|middle_downweighted_0_25|0.03973|0.04611|0.00000|0.03558|보류|
|214.208333|middle_excluded|0.00000|0.41260|0.00000|0.41260|보류|
|214.208333|middle_downweighted_0_25|0.00001|0.41260|0.00000|0.41260|보류|

![주변 프레임과 중지 포함 민감도](../dataset/integration_review/runs/low_string_root_20261105_v1/root_support.png)

214초에중지를제외하면두후보모두6·5번현근거가0이다. 중지를낮게포함하면G#m7쪽근음가점이0.04611로B6의0.03973보다약간높지만차이는0.00638뿐이고6·5번현근거도0.03558로작다. 주변213.792초는G#m7쪽근거가높지않고214.208초는이미손이이동하는시점이므로, 뒤프레임의강한지지를앞시점의정답확정에빌려쓰지않았다.

**이방향이틀렸다는결론은아니다.** 계산이이제현·프렛별근음위치를볼수있게됐지만현재손검출과가상현의정확도가판단근거를제한하고있다. 가중치만높여불안정한점을확정근음으로만들지는않았다.

## 현재 적용 상태

`low_string_root_prior.py`에가점기능과동점한정결정경계를추가했다. 검증된저음현근거가충분하면동점후보순서를바꿀수있고구성음/원오디오점수/대안후보는그대로남긴다. 실제214초는자동변경하지않아기존B6·G#m7동시표시를유지한다.

[현재6초지점비교영상](../dataset/integration_review/runs/visual_root_tie_20261105_v1/root_ambiguity_208_218.mp4)

175개 회귀/신규 테스트 통과. 저음현가중치, 중지불확실성, 중복칸중복가산방지, 고음현만으로베이스확정금지, 미검증비전강제선택금지, 검증된근거의동점한정정렬을검사했다. 모델학습·음원주파수범위·기존코드채점·손좌표는변경하지않았다.

```powershell
python evaluate_low_string_roots.py
python report_low_string_roots.py
python -m unittest test_low_string_root_prior test_visual_root_tiebreak test_chord_display_cleanup test_chord_display_stabilizer test_audio_change_pool test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

설정·입력해시·조건별실제칸기여값은result.json에보관했다. 다음에는근음후보가실제로놓이는6·5번현주변의손가락/바레관측을검증하는것이우선이다. 전역음PC가중치를더높이는것만으로해결하려고하지않는다.
