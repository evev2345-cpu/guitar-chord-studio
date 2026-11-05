# 코드 변화 후보로 시간창을 제한한 오디오 실험 — 2026-11-05

**기능 구현·검증과 새 영상 구간 확인을 완료했다.** 코드 전환 후보를 감지해0.2/0.4초 음 수집 창이 그 후보를 넘지 않게 했다.0.4초고정창대비잘못붙인확장코드는202→143건으로줄었지만전체정확도는42.80→41.88%로소폭하락했다. **변화 감지의 오탐이 많아 기본 경로로 승격하지 않았다.** 기존 고정창 경로는 보존했다.

## 구현한 방법

Basic Pitch 원음 입력·출력D2~E6·음활성문턱0.3·기존코드채점은고정했다. 활성음의PC분포를시점앞뒤각0.2초에서평균하고코사인거리의봉우리를변화후보로잡았다. 최소후보간격0.2초, prominence0.08, 양쪽활성합0.3 조건이다. 변화후보의양쪽을다른구간으로간주해기존max0.2/0.4초창만줄였다. 강제로코드를고르거나보류시키지는않았다.

추론 함수는 오디오 모델의 활성값·시각만 받는다. 정답 코드 경계는 평가에만 사용하며, 지판·손·화면 코드가 감지나 창 선택에 들어가지 않는다. 모델 자체가 보는 약2초문맥은 그대로라 시간창 제한으로 모든 전환 혼합이 사라지는 것은 아니다. 오프라인 중심창이므로 미래오디오도 사용한다.

첫버전(v1)은약한배경활성까지분포에합쳐서실제GuitarSet전환1,960개중3개만찾았다. 그결과를숨기지않고보존했다. v2는기존0.3음활성문턱미만을제외한뒤변화를계산했다. 감지높이만고정된7개값에서 **기존검증용BN3/Funk3곡23파일의전환F1**로선택했고0.4가선택됐다. 새영상과IDMT성적으로문턱을고르지않았다. 추가신경망학습은없었다.

## 같은 시점·같은 채점 비교

GuitarSet178파일의같은4,850시점,IDMT기타6음색1,638시점을사용했다. 순간/고정창은이전결과와파일별집계가정확히일치했다. 아래7화음은7·maj7·m7·m7b5묶음이다. ‘잘못붙인확장코드’는참조가장/단화음일때근음은같지만사전에있는7·maj7·m7·m7b5·dim7·add9·6·m6등으로불필요한PC를추가한경우다. 모든종류의오답이나9/11/13전체의정밀도를뜻하지않는다.

|방식|상세 코드 top1|7화음 top1|잘못 붙인 확장코드|보류|기존9곳|새4곳|
|---|---:|---:|---:|---:|---:|---:|
|Instant|26.72%|26.87%|20|2682|5/9|0/4|
|Fixed0.2s|37.59%|44.89%|104|1540|7/9|1/4|
|Fixed0.4s|42.80%|56.14%|202|898|6/9|3/4|
|Clipped0.2s|36.91%|43.17%|78|1661|7/9|1/4|
|Clipped0.4s|41.88%|52.01%|143|1116|7/9|3/4|

![같은 시점 비교와 새 구간 결과](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/comparison.png)

검증문턱조절에사용하지않은Jazz3/Rock3/SS3패턴36파일만분리한상세코드성적도보관했다. 이곡들은과거개발에서이미보았고기본Basic Pitch의GuitarSet학습이력도있으므로완전독립평가라고부르지않는다.

|방식|36파일 상세 top1|
|---|---:|
|instant|38.12%|
|fixed02|49.60%|
|fixed04|54.99%|
|clipped02|49.00%|
|clipped04|55.29%|

## 전환 후보 감지 성적

참조의근음/PC집합이바뀌는시각과예측후보를±0.2초안에서1:1대응시켰다. 같은코드의반복기호나같은음집합의베이스표기차이만으로전환을늘리지않았다. 아래오차는맞게대응된후보에한정한중앙절대오차이며실제코드출력의지연시간이나전체전환오차를뜻하지않는다.

- 실제GuitarSet: 정밀도30.64%, 재현율60.46%, 대응된후보중앙오차62.9ms. TP1185, FP2682, FN775.
- IDMT합성기타: 정밀도99.63%, 재현율99.14%, 대응된후보중앙오차22.1ms.

IDMT의분명한블록전환은잘찾지만실제연주의스트로크·아르페지오에따른음구성변화도경계로오인한다. 경계를너무많이만들면모아야할음을잘라보류가늘어날수있다. 이런상충이전체정확도하락과맞물리지만각오류의청음원인까지전수확정한것은아니다.

## 새 구간 선정과 참조 검수

**처음모델결과와원본프레임을보기전에250~266초,251/253/255/257/259/261/263/265초를고정했다.** 이후원본과앞뒤약0.208초를보고251·255초는전환중,263·265초는지속표시코드와다른끝부분멜로디/잔향이라제외했다. 제외를포함한계획·참조해시를첫새구간추론전에저장했다. 유효참조는4곳뿐이다. 좋은결과를얻으려고다른시점으로교체하지않았다.

새원음은같은영상에서샘플정합으로추출하고캐시된Demucs6소스모델로기타추정음을분리했다. 새분리음은아직사용자의별도청음검수를받지않았고다른악기누출가능성이있다. 참조는화면코드/TAB/다이어그램·보이는운지를대조한분석자판독이며표준튜닝과Capo.1을가정했다. 실제현접촉정답이나독립청음전사정답은아니다.

v1결과를본뒤검증곡으로v2문턱을보정했으므로 **새4곳은v1에는새평가였지만v2에는완전한블라인드테스트가아니다.** v2설정을그4곳의점수로선택하지는않았다. 세곳이Dm7인작고편중된표본이라는한계도있다.

|영상초|화면 운지 → 실음 참조|순간|고정0.2|고정0.4|경계0.2|경계0.4|
|---|---|---|---|---|---|---|
|253.0|C#m7 → Dm7|Dm|Dm|Dm|Dm|Dm|
|257.0|C#m7 → Dm7|보류|Dm|Dm7|Dm|Dm7|
|259.0|G#7 → A7|C6|A7|A7|A7|A7|
|261.0|C#m7 → Dm7|보류|F|Dm7|F|Dm7|

![미리 선정한 새8시점의 원본 — 제외점도 포함](../dataset/integration_review/runs/change_aware_audio_20261105_v1/new_interval_contact.png)

![새 구간 앞뒤 검수 —253초 포함](../dataset/integration_review/runs/change_aware_audio_20261105_v1/new_stability_0.png)

![259·261초 앞뒤 검수](../dataset/integration_review/runs/change_aware_audio_20261105_v1/new_stability_2.png)

## 원본과 실제 처리 창

![원음 파형과 실제 사용 창](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/supports.png)

회색은0.4초고정창,초록은실제경계제한창,빨간점선은 **검출한오디오변화후보**다. 정답코드경계선이아니다. 기존211초는Amaj7오류가A로개선됐지만223초Bbadd9오류는남았다. 새253초Dm7은모든방식이Dm으로판정해7음누락이해결되지않았다.

![새 원음·기타 추정음 파형과 스펙트럼](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/new_audio.png)

새252~256초원음: ![혼합 원음](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/Mixture_252_256.wav)

같은구간기타추정음: ![기타 추정음](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/Guitar_estimate_252_256.wav)

257초중심원음: ![257초 원음](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/new_pts_257_original.wav)

253초중심원음: ![253초 원음](../dataset/integration_review/runs/change_aware_audio_20261105_v2/report/new_pts_253_original.wav)

새사진·음원은실제파일에서추출했으며생성형이미지나합성음으로검증근거를대체하지않았다.

## 연결·검증·결정

`export_temporal_audio.py --clip-at-changes --change-detector-config ...`로선택실행가능하게연결했다. 새250~266초의evidence.json/harmony.json을`dataset/audio_analysis/runs/new_250_266_change_pool_20261105_v2`에실제로생성했다. 원본영상source_id·250초오프셋·입력해시를유지했다. 원래개별음의지속시간을늘리거나confirmed음/현접촉을만들지않았다.

157개테스트통과. 변화검출·같은코드반복무변화·약한배경활성제외·반대코드차단·경계없을때기존max와동일·오디오/화성기존회귀를검사했다. 모델가중치와손·지판·기본채점은그대로다.

**고정0.2/0.4초를유지하고경계제한은선택적인비교경로로둔다.** 다음우선과제는추가모델학습보다스트로크/개별음변화와코드변화를구분해경계후보정밀도를높이는것이다. 고정창보다정확도와보류율까지함께좋아지기전에는기본으로적용하지않는다. 이미본새4곳을재튜닝용독립시험처럼반복해서쓰지않는다.

```powershell
python calibrate_audio_changes.py
python evaluate_change_aware_audio_v2.py
python report_change_aware_audio.py
python -m unittest test_audio_change_pool test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

기존완료결과는덮어쓰지않으며재실행은새출력경로가필요하다. v1/v2둘다보존했다. 검증곡문턱탐색은detector_calibration.json,시점별후보/실제창/평가는records, 새구간선정과제외는frozen_review_plan.json/new_references.json, 원본사진은v1/reference_frames에있다.
