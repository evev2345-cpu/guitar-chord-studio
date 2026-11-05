# 기타 추정 트랙 분리 후 같은 안정구간9개 평가

후속 실험: [D2~E6 컷과 비전:오디오1:9~9:1 전수 비교](BANDCUT_VISION_WEIGHT_SWEEP_2026-11-05.md).

후속 청음 검수(2026-11-05): 사용자가 제시된 기타198~202초 재생에 대해 “기타만 잘됐어”라고 확인했다. 해당 발췌의 분리 품질은 사용자 청음 승인으로 기록했다. 전체32초 청음이나 정량적 누출/음높이 검증으로 확대하지 않는다. 파일SHA256과 원문은 `dataset/audio_analysis/references/user_guitar_listening_review_20261105.json`에 저장했다. 아래 미청음 표기는 실험 실행 당시 상태다.

**기타 추정 트랙은 근음 일치8/9→9/9, 상위3개 정답 포함6/9→7/9로 일부 개선됐다. 정확한 코드1위는2/9 그대로이며 손 정보를 합쳐도2/9다.**

## 실행

현재 설치된 Demucs 환경을 유지하고, 공식 `adefossez/HTDemucs-6s`의 `htdemucs_6s` 모델을 프로젝트 캐시에 추가했다. 모델 가중치는54,885,744바이트이며 파일/SHA256/리비전 경로는 `docs/guitar-separation-model-manifest.json`에 기록했다. 기존4소스 모델 캐시는 유지했다. 모델 확보 후 추론은 오프라인으로 실행했다. [Demucs 공식 모델 설명](https://github.com/facebookresearch/demucs/blob/main/README.md).

동일 원본의194~226초/32초 스테레오를 사용했다. 기존4소스 보컬제거 반주에 연쇄 분리를 적용하지 않고 원음에서6소스 모델의 guitar 추정값을 직접 출력했다. 따라서 비교는4소스 반주 대6소스 기타 추정이며, 모델과 출력 대상이 함께 달라진다. 개선을 피아노 제거 하나의 인과효과로 단정할 수 없다.

명령: `python run_local_separation.py --input dataset/audio_analysis/runs/barre_194_226_mix_20261104_v1/original.wav --output dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1 --model htdemucs_6s --stem guitar`. 기존기본값은 여전히 htdemucs/vocals다. 새 기타 요청에4소스 모델을 사용하면 오류로 거부한다.

## 같은 조건 비교

이전 화면 코드·TAB·운지 대조 참조정답9개를 그대로 사용했다. 카포1을 반영하고 표준튜닝을 가정했다. 구간/중지제외/가상현/손 점수/오디오0.8·시각0.2는 바꾸지 않았다. 새 손 검출을 다시 하지 않고 저장된 시각질량을 그대로 재사용했다. 구간별±0.2초 안에 분석창 전체가 들어가는22개 STFT 프레임의 코드별 점수를 평균했다. 이전 반주를 같은 함수로 재계산해 전체180개 후보의 순서와 점수가 저장된 기준 결과와 정확히 일치하는지도 확인했다.

| 지표 | 기존 반주 | 기존 반주+손 | 기타 추정 | 기타 추정+손 |
|---|---:|---:|---:|---:|
|정확한 코드1위|2/9,22.2%|2/9,22.2%|2/9,22.2%|2/9,22.2%|
|상위3개 안에 정확한 코드|6/9,66.7%|6/9,66.7%|7/9,77.8%|7/9,77.8%|
|1위의 근음만 일치|8/9,88.9%|8/9,88.9%|9/9,100%|9/9,100%|

9/9는 이 작은 개발 표본의 관측값이며 일반 정확도100%라는 뜻이 아니다. 기타/시각 통합은 여전히 탐색 실험이고 운영의 미확정 해부학/기하 차단은 변경하지 않았다. 참조는 에이전트가 화면과 손을 대조한 것이며 독립적인 사람 전사나 기타 단독 녹음 정답은 아니다.

|PTS초|실음 참조정답|반주1위|기타1위|기타+손1위|
|---|---|---|---|---|
|195|G|Cadd9|Gmaj7|Gmaj7|
|197|F#m|F#m7|F#m7|F#m7|
|199|G|Gmaj7|Gmaj7|Gmaj7|
|207|G|Gmaj7|Gmaj7|Gmaj7|
|209|F#7|F#add9|F#add9|F#add9|
|211|A|Amaj7|Amaj7|Amaj7|
|221|A7|A7|A7|A7|
|223|Bb|Bbmaj7|Bbmaj7|Bbmaj7|
|225|A7|A7|A7|A7|

195초의 근음 오판이 C→G로 고쳐졌다.197초에서는 정답F#m의 순위가4위→3위로 올라 상위3개 포함 수가 증가했다. 그러나1위F#m7를F#m으로 고치지는 못했다.199초G,211초A,223초Bb에서도 maj7 오판이 계속된다. 오디오/손 가중치를 이번 정답에 맞춰 튜닝하지 않았다.

![같은 원본 화면/참조정답과 반주·기타·통합 후보](../dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/chord_comparison.png)

## 분리 소리와 물리적 검증

출력은 원음과 같은44,100Hz,1,411,200샘플,2채널이고 유한수/길이 검사를 통과했다. 원음RMS0.10846, 기존반주0.10207, 기타추정0.09421이다. 기타+나머지 추정을 원음과 비교한 재구성오차RMS는0.00911로0이 아니며, 손실 없는 분해가 아니다. 수치 정합은 음질/악기 귀속을 보증하지 않는다. 사람이 새 기타 트랙을 청음 검수한 기록은 아직 없고 기타만 완전히 남았다고 주장하지 않는다.

아래는198~202초 원음/반주/기타추정의 파형·스펙트럼이다. 볼륨정규화 없이 같은축/같은dB색척도로 비교했다. 그림만으로 어떤 악기가 제거됐는지 확정하지 않는다.

![원음·반주·기타추정 파형과 스펙트럼](../dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/audio_comparison.png)

원음198~202초:

![원음 재생](../dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/mixture_198_202.wav)

기존반주198~202초:

![기존반주 재생](../dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/accompaniment_198_202.wav)

기타추정198~202초:

![기타추정 재생](../dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1/guitar_198_202.wav)

32초 전체 기타추정 파일은 `dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav`에 있다.

## 결론과 다음 우선순위

이 표본에서 기타 분리는 후보의 근음/상위3개에 일부 도움이 됐지만 정확한 코드종류 판별을 해결하지 못했다. 악기 혼합만이 원인이라고 보기 어렵고, 코드 점수가 배음/추가음으로 maj7/add9를 선호하는 문제를 다음으로 검증해야 한다. 기타 트랙의 누출/누락도 여전히 가능하다. 모델기본값을 기타분리로 교체하거나 화성 가중치를 높이는 변경은 하지 않았다.

재현: `python audio_analysis.py --manifest dataset/audio_analysis/runs/barre_194_226_guitar_analysis_20261105_v1/manifest.json`, 이어 `python compare_guitar_stem_accuracy.py`. 최종 비교 결과가 있으면 덮어쓰지 않는다. 결과/metric/분리QA/입력SHA256/모델manifest/후보 전체180개/정답동일성/재생샘플은 `dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1`에 저장했다.

검증: `python -m unittest test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q` —85개 통과. 새 검사는 분리출력의 샘플정합, 동일참조/동일시각질량/동일가중치, 이전반주 정확재현, metric재계산, 오디오후보부재 시 보류 동작을 포함한다.
