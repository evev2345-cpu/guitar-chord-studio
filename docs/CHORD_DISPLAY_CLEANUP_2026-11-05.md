# 실제 영상 코드 표시의 짧은 튐 정리 — 2026-11-05

실제 영상에서 괜찮던 코드 흐름을 유지하면서 표시만 보수적으로 정리했다. 모델·음 추출·코드 채점·0.2/0.4초 시간창은 변경하지 않았다. **큰 폭의 정확도 개선이 아니라 작은 표시 개선**이며, 지속적으로 잘못 붙는 텐션은 아직 남는다.

- [먼저10초 보기: 수정 전후3:28~3:38](../dataset/integration_review/runs/stable_video_review_20261105_v2/first_watch_208_218.mp4)
- [비교 재생 페이지: 구간·시간창·원음/기타음 선택](../dataset/integration_review/runs/stable_video_review_20261105_v2/review.html)

## 수정한 것

- 앞뒤가 같은 코드인1~2프레임의짧은튐은, 원래코드도현재상위3개후보에있고점수차가0.08이내일때만정리한다.
- 같은근음에잠깐추가음이붙었다가돌아오는경우는최대3프레임까지같은조건으로확인한다. 실제7화음을무조건장단화음으로단순화하지않는다.
- 앞뒤가같은코드인1~2프레임보류만연결한다. 해당순간에는‘현재근거는부족’이라고명시한다. 긴보류는채우지않는다.
- 최고점이동점이면직전후보가그동점집합안에있을때유지한다. 고유하게확정된정답처럼표시하지않는다.
- 일반적인새코드전환에는일괄대기시간을붙이지않는다. 미확인구간이나근거가다른강한후보를이전코드로임의덮어쓰지않는다.

원래추론값은그대로보관하고비교영상왼쪽에표시한다. 오른쪽은정리한표시다. 주변프레임을보는오프라인정리이며, 실시간시스템의무지연동작을주장하지않는다. 기본모델과중심시간창도미래오디오문맥을사용한다.

## 검증 결과

|구간·시간창|표시 변화 전→후|0.125초 이하 짧은 후보 구간 전→후|보류 프레임 전→후|검수 시점 정답 전→후|
|---|---:|---:|---:|---:|
|기존32초·0.2초|104→96|41→36|98→93|7/9→7/9|
|기존32초·0.4초|82→80|29→26|33→33|6/9→6/9|
|새16초·0.2초|69→63|35→32|127→124|1/4→1/4|
|새16초·0.4초|48→44|19→15|100→100|3/4→3/4|

표시변화는코드↔보류변화를포함한다. 짧은후보구간수는실제코드전환오류수와같지않다. 위점검은이미여러번본개발영상이며독립시험이아니다. 참조정답은정리함수에전달하지않았다.

처음 시도한 방식은 후보가약0.1초이상지속될때까지기다리는방식이었다. 표시전환은크게줄었지만기존0.2초검수정답이7/9→3/9로떨어졌다. 이를미채택하고결과를v1에보관했다. 지금재생자료는전환을일괄지연하지않는v2다. 속도를늦춰서보기좋게만드는방식을기본으로적용하지않았다.

## 실제 장면

![원본259.041667초/프레임6216 — 동점 표시 유지 전후](../dataset/integration_review/runs/stable_video_review_20261105_v2/new_250_266_preview.png)

이시점은원래C6와A7이같은PC집합으로동점이다. 직전A7도최고점후보이므로표시를유지했다. 화면운지G#7에카포1을반영한실음참조는A7이다. 참조는평가에만쓰고동점처리에넣지않았다.

![원본215.416667초/프레임5169 — 정리해도 음악적 오답이 남는 사례](../dataset/integration_review/runs/stable_video_review_20261105_v2/barre_194_226_preview.png)

이장면은짧게나타난Bb7표시를주변의Bbadd9로정리한예다. **Bbadd9가올바른코드라는주장은아니다.** 해당시각은별도정답미검수로표시했다. 이런지속적인확장코드오인은이번표시정리로해결되지않는다.

원본화면·손·TAB는그대로두고아래분석패널만바꿨다. ‘운지표기’는카포1환산값이며손추적추론이아니다. 영상은동일한원음또는동일한기타추정음으로비교하므로소리를바꿔개선된것처럼보이게하지않았다.

## 재생 자료와 검증

각32초·16초구간에0.2/0.4초비교영상과원음/기타음버전을만들었다. 총8개전체영상과10초요약영상이다. H.264/AAC로만들었고모든MP4를FFmpeg로끝까지디코딩해검사했다. 영상과음원길이가일치하며32초768프레임,16초384프레임,10초240프레임이다.

166개 회귀/신규 테스트 통과. 실제코드전환을지연하지않는조건, 근거없는후보를덮어쓰지않는조건, 같은코드사이의짧은보류연결, 동점유지, 음원경계초기화등을검사했다.

재현:

```powershell
python evaluate_chord_display_v2.py
python render_stable_video_review.py
python -m unittest test_chord_display_cleanup test_chord_display_stabilizer test_audio_change_pool test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료출력은덮어쓰지않는다. 새실행에는새OUT경로가필요하다. 설정·원래타임라인해시는config.json, 전후값과처리이유는각timeline.json, 정량비교는evaluation.json, 영상목록은video_manifest.json에보관했다. 기존판별과수정전영상도보존했다.

다음검수는재생화면에서불편함이줄었는지먼저확인한다. 지속적인7음누락·과한텐션오인은표시안정화와분리해서다뤄야하며이번수정으로모두해결됐다고보지않는다.
