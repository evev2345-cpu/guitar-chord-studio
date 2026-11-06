# 7화음 오류 진단과 배음 기반 특징 실험 — 2026-11-05

7음을 잘 못 읽는 문제와 읽은 근거를 잘못 채점하는 문제가 함께 있다. 고정 배음 모델을 추가해 IDMT 및 일부 실제 7화음에서 개선됐지만, 실제 음 후보 과검출과 m7 퇴보가 확인됐다. 운영 기본 설정은 유지하고 새 기능은 재현 가능한 실험으로 보관했다. 학습·외부 API·추가 다운로드·비전 가중치 변경은 하지 않았다.

## 무엇을 만들었나

`harmonic_chord_features.py`는 D2~E6의 51개 기본음 각각을 1~8차 배음(고정 진폭 1/h) 묶음으로 표현한다. 8192샘플 Hann 스펙트럼에서 50~6000Hz를 관측하고 비음수 최소제곱으로 각 후보의 크기를 구한다. 넓은 음색 기울기의 영향을 줄이기 위해 관측과 모델에 동일한 국소 포락선 가중치를 준다. 학습된 모델이 아니라 창마다 크기 계수를 맞추는 신호 처리 실험이다. 동음·옥타브·서로 겹치는 배음은 여전히 모호하다.

첫 결과에서 과검출이 증가해 `supported_harmonic_features.py`를 별도 추가했다. 기존 추출기와 동일한 전역 최대 크기12% 문턱을 넘는 국소 피크가 기본음 위치에서 관측될 때만 후보를 남긴다. 문턱 탐색은 하지 않았다. 비교 이름의 L은 기존 coverage 채점, C는 cosine 채점이다. C에는 활성 피치클래스 최소2개 조건도 포함된다.

## 평가 조건

GuitarSet comp180파일을 실행했고 알려진 시간오류2개를 제외한178파일의 안정창4,886개를 주 결과로 썼다. 0.5초부터1초 간격의 고정 그리드이며 코드 주석으로 예측 시각을 고르지 않았다. 주석 경계에서 창 반폭+0.05초 이상 떨어진 곳만 채점했다. 기본 주석과 상세 수행 주석은 별도로 유지했다. 상세 주석의 사전 밖1,190개도 전체 분모에 남겼다.

IDMT 기타6음색 ×273구간=1,638개의 중심창을 평가했다. 문제가 있는 비기타 전위 주석은 이 실험에서 제외했다. 두 데이터 모두 원본 모노 파형을 쓰고 대역 컷·시간 평균은 하지 않았다. 기존 Peak는65~1600Hz 피크를 사용하고 Harmonic은50~6000Hz의 배음까지 관측하므로 관측 대역 확대와 모델링 효과가 함께 포함된다. 이전 보고서의 D2~E6 파형 컷·100ms 표본 성적과 직접 비교하지 않는다. 이번 표 안에서는 같은 오디오·같은 창·같은 정답 분모로 비교했다.

186개 입력 음원의 SHA256을 기존 수신/IDMT 평가와 대조했고, IDMT 기존 채점·cosine의 구간별 top1/top3 결과가 이전 결과와 전수 일치했다. 후속 support 실험도186파일의 시각 그리드·원음·주석 경로 일치를 확인했다.

## 전체 및 코드 종류별 결과

|방식|GuitarSet 기본 top1|상세 전체 top1|상세 전체 top3|IDMT 기타 top1|
|---|---:|---:|---:|---:|
|peak_legacy|11.60%|13.34%|29.47%|44.38%|
|peak_cosine|16.21%|19.83%|37.78%|36.08%|
|harmonic_legacy|9.62%|12.61%|27.77%|56.11%|
|harmonic_cosine|17.74%|21.63%|37.60%|50.24%|
|supported_legacy|16.68%|17.03%|25.42%|52.87%|
|supported_cosine|16.78%|19.18%|34.49%|36.45%|

![동일 창의 추출/채점 분리 비교](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/accuracy.png)

|상세 코드|실제 Peak/L|실제 Harm/L|실제 Gate/L|IDMT Peak/L|IDMT Harm/L|IDMT Gate/L|
|---|---:|---:|---:|---:|---:|---:|
|major|15.18% (257/1693)|12.40% (210/1693)|26.70% (452/1693)|22.65% (53/234)|38.03% (89/234)|49.57% (116/234)|
|minor|23.06% (119/516)|15.31% (79/516)|30.23% (156/516)|31.20% (73/234)|50.00% (117/234)|62.82% (147/234)|
|7|28.57% (84/294)|33.33% (98/294)|27.89% (82/294)|83.76% (196/234)|94.44% (221/234)|85.47% (200/234)|
|maj7|37.50% (102/272)|54.41% (148/272)|27.94% (76/272)|85.04% (199/234)|96.58% (226/234)|77.35% (181/234)|
|m7|17.19% (38/221)|13.57% (30/221)|10.86% (24/221)|56.84% (133/234)|67.95% (159/234)|56.84% (133/234)|
|m7b5|23.86% (21/88)|28.41% (25/88)|23.86% (21/88)|31.20% (73/234)|45.30% (106/234)|38.03% (89/234)|
|5|0.98% (4/407)|0.00% (0/407)|1.23% (5/407)|0.00% (0/234)|0.43% (1/234)|0.00% (0/234)|

기존 채점 그대로 특징만 바꾸면 IDMT 전체는44.38→56.11%로 개선됐다. 실제 GuitarSet의 maj7·도미넌트7·m7b5는 좋아졌지만 m7·일반 장단화음이 퇴보해 상세 전체는13.34→12.61%였다. cosine 채점끼리 비교하면 실제 상세 전체19.83→21.63%로 개선되지만 IDMT는 기존 coverage보다 낮다. 어느 한 방식이 모든 코드·데이터에 우세하지 않다.

## 7음 근거와 과검출 진단

상세 주석에서7·maj7·m7·m7b5인875창을 진단했다. Peak/L의 오답630개 중 7음 피치클래스가 최대 크기의10% 미만인 경우는257개, 그 이상인데도 오답인 경우는373개였다. 후자에는 근음 오류도 포함돼 단순히 채점만의 문제라고 단정할 수 없다. 그 피치클래스가 배음에서 생겼을 수도 있으므로 ‘근거 있음’은 실제 7음 검출 성공을 뜻하지 않는다.

Harm/L은875개 중 정답을245→301개로 늘리고, 오답 중 7음 근거가 약한 경우를257→131개로 줄였다. 하지만 음 후보 과검출이 늘었는지 별도로 확인할 필요가 있었다.

GuitarSet6현 note_midi 주석을 시간별로 합쳐 실제 활성 피치클래스 집합과 대조했다. 아래는5,421창 전체(무음 포함)의 피치클래스 precision/recall이며, 개별 음높이·현·온셋 성적이 아니다. 활성 후보 문턱은 각 창 최대 salience의10%로 고정했다.

|특징|정밀도|재현율|F1|
|---|---:|---:|---:|
|peak|46.65%|92.52%|62.03%|
|harmonic|29.54%|95.18%|45.09%|
|supported|56.65%|85.89%|68.27%|

![7화음 근거와 실제 note 주석 비교](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/diagnosis.png)

Harmonic은 재현율을 높였으나 정밀도가 크게 떨어졌다. Support 제한은 후보 F1을62.03→68.27%로 높였으나, 약한 실제 7음도 제거하고 보류를 늘린다. ‘배음 제거 완료’라고 볼 수 없으며 기본 시스템에 적용하지 않은 이유다.

## 실제 개선과 실패 원음

![원본 파형과 후보 분포](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/cases.png)

초록 배경은 상세 주석의 구성음, 막대는 각 특징의 추정 분포이며 확률이 아니다. 빨간 점선은 창 중심이다. 알파벳 순서의 파일에서 조건에 맞는 첫 개선/퇴보 사례를 각각 골랐다. 사례의 주석은 GuitarSet 상세 수행 주석이며 독립 청음 검수는 아니다. 두 소리는 처리 전 동일 원음으로, 이 실험은 파형을 변경하지 않는다.

사례1: `00_BN1-129-Eb_comp` 19.5초, 상세 주석 `D#:maj7/1`. Peak/L `Bbmaj7` → Harm/L `Ebmaj7`.

![원음](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/case_1.wav)

![원본 스펙트럼](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/spectrum_1.png)

사례2: `00_BN2-131-B_comp` 21.5초, 상세 주석 `G:maj7/1`. Peak/L `Gmaj7` → Harm/L `Abm7b5`.

![원음](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/case_2.wav)

![원본 스펙트럼](../dataset/integration_review/runs/harmonic_ablation_20261105_v1/report/spectrum_2.png)

## 현재 튜토리얼 확인

기존 안정구간9개에서 분리된 기타 추정 트랙의 정확한 영상 PTS 중심8192샘플 창을 평가했다. Capo.1 참조를 유지했다. 원본 스테레오는 모노 평균했고 시간 평균은 하지 않았다. 이미 사용한 작은 개발 표본이며 독립 시험이 아니다. 이전100ms 최근접 표본이나0.4초 평균 성적과 직접 비교하지 않는다.

![195초 원본 화면 — 기존 참조 자료](../dataset/integration_review/runs/tutorial_reference_20261105_v1/pts_195.png)

|방식|정확 코드1위|상위3개 포함|근음1위|
|---|---:|---:|---:|
|peak_legacy|2/9|5/9|8/9|
|peak_cosine|5/9|6/9|8/9|
|harmonic_legacy|3/9|4/9|8/9|
|harmonic_cosine|4/9|5/9|9/9|
|supported_legacy|4/9|5/9|7/9|
|supported_cosine|3/9|6/9|6/9|

## 검증·재현·다음 판단

130개 회귀/신규 테스트 통과. 단일 기본음의 배음, 실제 도미넌트7 구성음 보존, 무음·비정상 입력, 피크 제한,7음 근거 분류를 포함한다. 합성 단위 테스트의 통과를 실제 연주 정확도로 대신하지 않았다.

재현 명령:

```powershell
python benchmark_harmonic_chords.py --output dataset/integration_review/runs/harmonic_ablation_20261105_v1
python audit_harmonic_chords.py
python benchmark_supported_harmonics.py
python report_harmonic_chords.py
python -m unittest test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료된 결과를 보호하기 위해 실행기는 기존 출력에 덮어쓰지 않는다. 재실행은 출력 경로를 새 버전으로 지정하거나 후속 실행기의 OUT 상수를 바꾸고 실행한다. 각 config.json에 소스 해시와 고정 조건, audit.json에 입력 대조·주석 해시, followup_audit.json에 support 평가와 튜토리얼 개별 후보를 남겼다.

이번 시도는 7음 약화의 일부를 개선했으나 전체 문제를 해결하지는 못했다. 다음 우선 과제는 고정1/h 배음 모델이 실제 음색에 맞지 않아 만드는 가짜 기본음과 옥타브 후보를 줄이는 것이다. 검증셋을 따로 고정한 뒤 기존 note 주석의 실제 음 후보 정밀도·재현율을 목표로 비교해야 한다. 9·11·13 텐션은 이번 유효 표본과 사전으로 충분히 검증하지 않았다. 임의 코드별 스위칭이나 정답을 보고 선택하는 합성 성적은 만들지 않았다.
