# IDMT 코드 데이터 검증과 채점 개선 비교 — 2026-11-05

IDMT-SMT-Chords 다운로드·검증·전체 7,398구간 평가를 완료했다. 새 정규화는 실제 GuitarSet에서 개선됐지만 IDMT 기타에서 퇴보했다. 운영 기본 채점은 변경하지 않았고 새 방식은 평가 전용이다. 지금은 작은 모델 학습보다 배음과 실제 구성음을 분리하는 특징 개선을 먼저 할 근거가 확보됐다.

## 데이터와 재현

공식 [Zenodo 자료](https://zenodo.org/records/7544213)의 ZIP 1,306,388,518바이트, MD5 `af2239fcc468ce653c9d9350ceaa3eb5` 일치, CRC 24개 항목 검사 후 추출했다. SHA256 `ac0195c989485828ae9b344dcd527e49698fb1fcba9a6778d3c0068b4c06afad`. 원본과 이전 실험 결과는 보존했다. 다운로드 근거는 `IDMT_SMT_Chords/download_manifest.json`.

6개 기타 음색 × 273구간 = 1,638개, 10개 비기타 음색 × 576구간 = 5,760개. 모두 44.1kHz 모노이며 정수 PCM과 실수 PCM을 구분해 변환했다. MIDI를 소프트웨어 악기로 렌더링한 합성 음원으로 실제 연주 영상 데이터가 아니다. 학습·파라미터 피팅은 하지 않았다.

기존 180개 화음 사전과 FFT 피크 기반 크로마를 유지했다. cosine은 구성음 수로 정규화하며 활성 피치클래스 최소 조건도 3개에서 2개로 바뀐다. 따라서 순수 정규화 단독 효과라고 해석할 수 없다. context는 중심 ±0.1초의 세 점수를 평균하며 미래 오디오가 필요하다. 확률로 보정된 신뢰도는 아니다.

IDMT는 각 2초 구간의 중심 한 곳을 채점했다. 각 중심 ±0.1초에 실제 8192샘플 창을 사용했으며 참조 코드명이 예측 함수에 들어가지 않는다. 주석 시각으로 평가 위치를 선택하므로 전환·온셋 성능은 측정하지 않는다. 후보 피크 범위는 65~1600Hz, 파형 대역 컷은 하지 않았다. GuitarSet은 기존 D2~E6 파형 컷, 100ms 표본을 유지했다. 데이터 간 절대 성적은 직접 비교하지 않고 각 데이터 안에서 방식의 변화를 비교한다.

## 결과

GuitarSet 180파일에서 기존 cut 점수와 파일별 집계가 정확히 재현됐다. 주 성적은 알려진 시간 오류 2파일을 뺀 178파일이다. 상세 수행 주석과 기본 주석은 서로 다른 정답층이다.

|방식|GuitarSet 기본 top1|GuitarSet 상세 전체 top1|IDMT 기타 top1|IDMT 기타 top3|
|---|---:|---:|---:|---:|
|legacy|12.02%|13.59%|44.38%|65.57%|
|cosine|16.87%|20.82%|36.08%|67.89%|
|cosine_context|19.93%|24.61%|36.08%|69.35%|

![실제 성적과 코드 종류별 비교](../dataset/integration_review/runs/idmt_chords_scores_20261105_v2/report/comparison.png)

GuitarSet 기본 도미넌트7은 기존 928/4,230=21.94%에서 context 643/4,230=15.20%로 하락했고, m7b5도 15.53%에서 12.58%로 하락했다. IDMT 기타 도미넌트7은 196/234=83.76%에서 103/234=44.02%, maj7은 85.04%에서 52.99%로 떨어졌다. 전체 평균 개선만 보고 교체하면 실제 7음을 지우는 오류가 커질 수 있다.

|기타 음색|기존|cosine|context|
|---|---:|---:|---:|
|ableton_live_guitar_Campfire|38.83%|20.15%|18.32%|
|ableton_live_guitar_Guitar_Open|54.58%|52.38%|52.75%|
|ableton_live_guitar_Nylon_Concerto_Guitar|25.27%|8.79%|8.79%|
|garageband_guitar_Acoustic_Guitar|54.95%|43.96%|43.59%|
|garageband_guitar_Classic_Clean|38.46%|47.62%|47.62%|
|garageband_guitar_Hard_Rock|54.21%|43.59%|45.42%|

기존 튜토리얼 안정구간 9개를 동일 100ms 표본 방식으로 재생한 비교에서는 top1이 기존 3/9, cosine 4/9, context 6/9였다. 이미 확인해 온 작은 개발 표본이며 독립 시험이 아니다. 이전 0.4초 평균 방식과 직접 비교하지 않는다.

## 실제 원음과 실패 사례

![원본 파형과 중심 창 스펙트럼](../dataset/integration_review/runs/idmt_chords_scores_20261105_v2/report/examples.png)

예시1: Campfire 73.0초, 주석 `C:maj`. 기존 `Cadd9`, 문맥 정규화 `C`. 원본 2초: ![원음](../dataset/integration_review/runs/idmt_chords_scores_20261105_v2/report/case_1.wav)

예시2: Campfire 1.0초, 주석 `E:maj`. 기존 `E`, 문맥 정규화 `E5`. 원본 2초: ![원음](../dataset/integration_review/runs/idmt_chords_scores_20261105_v2/report/case_2.wav)

원본 파형의 빨간 점선은 평가 시점이다. 스펙트럼 피크는 관측이며 실제 기본음 정답이 아니다. 사례는 개선과 퇴보를 각각 하나 선택한 설명용 자료이며 전체 비율은 위 표를 따른다.

## 주석 검사에서 드러난 한계

비기타 자료에는 `C:min/3`, `C:min7/7`, `C:hdim7/5`처럼 표준 Harte 도수로 읽으면 해당 화음 밖의 베이스 음이 추가되는 표기가 있다. 원본을 임의 수정하지 않고 문자 그대로 해석했다. 그 결과 1,680/5,760개가 현 사전 밖이며 전체 분모에 남았다. 비기타 성적은 이 주석 문제를 포함한 진단값이고 정정된 정확도라고 발표하지 않는다. 기타 1,638개는 모두 사전 내이며 위 주요 결론에는 이 문제가 없다. 전위 자체의 정확도는 채점하지 않았다.

첫 실행 v1은 모든 라벨이 사전 내일 것이라는 검증에서 실패했고 결과를 보존했다. 원인을 조사한 뒤 v2에서 OOV를 명시적으로 허용하고 기타 전수 검사 조건을 유지해 다시 완료했다.

## 검증과 다음 단계

`python idmt_chords_benchmark.py` → v2 전체 16파일·7,398구간 완료. `python report_idmt_chords.py` → 이 문서·성적 그림·원음 두 개 재생성. 원시 파일별 결과와 설정은 `dataset/integration_review/runs/idmt_chords_scores_20261105_v2`에 있다.

122개 회귀/신규 단위 테스트 통과. 명령: `python -m unittest test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q`.

다음은 배음 억제 또는 기본음 후보 추출을 독립 실험으로 추가하고, triad/7음의 누락·과검출을 동시에 비교하는 것이다. 학습을 진행한다면 먼저 사용 조건과 연주자 단위 분할을 확정하고 GuitarSet 및 별도 튜토리얼을 분리해야 한다. IDMT-SMT-Guitar 추가 다운로드는 이번에는 하지 않았다. 실제 연주 검증에는 이미 확보한 GuitarSet이 있고, 현 병목인 코드 종류·음색 일반화는 이번 Chords로 확인됐다. 손·지판·접촉 판정 및 비전 가중치는 변경하지 않았다.
