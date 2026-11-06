# 사전학습 Basic Pitch 오디오 모델 연결 — 2026-11-05

Spotify **Basic Pitch0.4.0의 사전학습 ONNX 모델**을 설치하고 실제 추론·코드 후보 연결·전체 비교까지 완료했다. 자체 학습은 하지 않았다. 손·지판·코드 채점·비전 가중치는 변경하지 않았다. 모델 출력은 음 후보이며 실제 현 접촉·뮤트·개방현 정답이 아니다.

## 설치와 모델

별도 `.venv-audio-model` 환경에 설치했다. ONNX Runtime 1.23.2를 CPU 4스레드로 실행하며 기존 환경은 변경하지 않았다. resampy 호환성을 위해 setuptools 80.9.0을 고정했다. 설치 버전 목록은 requirements.lock.txt에 있다.

모델은공식패키지에동봉된 `nmp.onnx`, 230,444바이트, SHA256 `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`. [공식 프로젝트](https://github.com/spotify/basic-pitch)와 [공식 추론 구현](https://github.com/spotify/basic-pitch/blob/main/basic_pitch/inference.py)의 모델·전처리·기본 디코더를 사용했다. 패키지0.4.0의 출력 시간 문제는 입력 샘플 위치로 연결해 해결했고 패키지 자체는 수정하지 않았다. 패키지의Apache2.0 라이선스를 유지한다. 저장소상세와 연구설명은 공식 프로젝트 참조.

**GuitarSet은 이 모델의 학습 자료 중 하나다.** 아래 GuitarSet 성적은 연결과 오류 진단에만 사용한다. 독립 평가나 미지 연주자에 대한 정확도를 뜻하지 않는다. 여기서 재학습하거나 문턱을 최적화하지 않았다. IDMT는 합성 음색이고 튜토리얼은 기존의 작은 개발 표본이라는 한계도 있다.

## 입력·후처리·평가 조건

GuitarSet 반주 180파일, IDMT 기타 6음색, 현재 기타 추정 트랙 32초를 **컷 없음/컷 사용**으로 각각 추론했다. 총 187개 소스 × 2 = 374개 결과와 MIDI를 저장했다. 컷은 기존과 같은 전체 파일 FFT D2~E6 컷이며 모델 입력 전에 적용한다. **컷 없는 모델도 최종 음 후보는 D2~E6로 제한한다.** 높은 배음은 음을 추정하는 입력 근거로만 활용한다.

프레임 방식은 모델의 note activation이 기본 문턱 0.3 이상인 음을 피치클래스로 합친다. 디코딩 음 방식은 공식 onset 0.5 / frame 0.3 / 최소 11프레임 설정으로 얻은 음이 해당 시각에 활성인지 판단한다. 둘 다 기존 coverage 코드 채점을 사용한다. 활성 피치클래스가 3개 미만이면 기존 채점기가 보류하므로, 모델이 2음을 잘 찾아도 코드 후보가 없을 수 있다. 모델 점수는 보정된 확률이 아니다.

GuitarSet주결과는기존과같은178파일·안정창4,886개, IDMT1,638중심시점, 튜토리얼9시점이다. 주석과정답은추론작업파일에넣지않았다. 동일평가시각·동일코드사전·동일채점으로비교하지만 **모델은약2초문맥을보고기존피크는8192샘플창을보므로 순수 특징 하나만 바꾼 실험은 아니다.** 초기 v1은 공식 출력 시간 변환에서546초 음원의 마지막 시간이542.338초로 잘리는 문제가 확인돼 평가를 중단했다. v2는 입력 창의 실제 시작 샘플 위치·256샘플 홉·양쪽15프레임 제거로 시간을 연결하며 입력 길이만큼 출력도 유지한다. 정답에 맞춘 시간 늘이기나 오프셋 피팅은 하지 않았다. 이전 v1 결과는 보존하되 성적으로 사용하지 않는다.

## 결과

|방식|GuitarSet 기본 top1|상세 전체 top1|상세 전체 top3|IDMT 기타 top1|튜토리얼 top1|
|---|---:|---:|---:|---:|---:|
|기존 피크 / 컷 없음|11.60%|13.34%|29.47%|44.38%|2/9|
|기존 피크 / 컷 사용|11.81%|13.69%|29.53%|46.15%|3/9|
|모델 / 컷 없음 / 프레임|26.44%|26.87%|30.09%|65.14%|5/9|
|모델 / 컷 없음 / 디코딩 음|26.34%|26.05%|29.02%|65.75%|4/9|
|모델 / 컷 사용 / 프레임|17.74%|17.97%|20.55%|45.97%|3/9|
|모델 / 컷 사용 / 디코딩 음|17.83%|17.79%|20.16%|45.18%|3/9|

![기존 방식과 모델 비교](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/accuracy.png)

다음 오디오 개발은 **컷 없는 입력 + 모델 프레임 출력 + D2~E6 음 후보 제한**을 우선 경로로 사용한다. 모델 입력까지 자르면 IDMT와 튜토리얼 양쪽에서 성적이 떨어졌다. 다만 튜토리얼은9곳뿐이므로 이 선택을 일반적인 최적 설정이라고 주장하지 않는다. 기존 FFT 경로와 컷 사용 경로는 비교용으로 보존했다.

모델이 모든 문제를 해결한 것은 아니다. GuitarSet 진단에서 장·단화음은 개선됐지만 maj7·m7·m7b5는 기존보다 낮고, 튜토리얼에서도7음 누락과 보류가 남았다. 따라서 모델 연결 완료와7화음 문제 해결을 구분한다. 다음 검증은 새 연주 구간에서 모델의 음 후보를 확인하고, 그 후보가 맞는데도 기존 채점이 잘못 고르는 사례를 분리하는 것이다. 새 모델을 재학습하거나 문턱을 바꾸기 전에 이 연결 결과를 기준선으로 삼는다.

|GuitarSet 상세 코드|기존/컷 없음|기존/컷 사용|모델 raw/frame|모델 raw/event|모델 cut/frame|모델 cut/event|
|---|---:|---:|---:|---:|---:|---:|
|major|15.18% (257/1693)|15.65% (265/1693)|48.91% (828/1693)|48.38% (819/1693)|33.73% (571/1693)|33.49% (567/1693)|
|minor|23.06% (119/516)|23.45% (121/516)|43.99% (227/516)|42.44% (219/516)|28.68% (148/516)|29.46% (152/516)|
|7|28.57% (84/294)|28.91% (85/294)|28.91% (85/294)|28.23% (83/294)|17.01% (50/294)|18.03% (53/294)|
|maj7|37.50% (102/272)|38.60% (105/272)|35.29% (96/272)|29.78% (81/272)|27.21% (74/272)|25.00% (68/272)|
|m7|17.19% (38/221)|17.65% (39/221)|15.38% (34/221)|15.38% (34/221)|7.69% (17/221)|6.79% (15/221)|
|m7b5|23.86% (21/88)|23.86% (21/88)|21.59% (19/88)|22.73% (20/88)|6.82% (6/88)|5.68% (5/88)|

GuitarSet note_midi 피치클래스 집합과5,421시점에서 비교했다. 프레임·디코딩음의음활성판정은위에고정한공식기본설정을사용한다. 단일음높이·현·온셋F1과는다르다.

|모델 입력/표현|PC 정밀도|PC 재현율|PC F1|
|---|---:|---:|---:|
|raw_frames|86.75%|86.85%|86.80%|
|raw_events|90.37%|86.36%|88.32%|
|cut_frames|88.70%|76.31%|82.04%|
|cut_events|91.42%|75.59%|82.76%|

## 실제 튜토리얼의 성공·보류·실패

|영상초|기존 참조 정답|raw/frame|raw/event|cut/frame|cut/event|
|---|---|---|---|---|---|
|195.0|G|보류|보류|보류|보류|
|197.0|Gbm|Gbm|보류|보류|보류|
|199.0|G|G|G|G|G|
|207.0|G|보류|보류|보류|보류|
|209.0|Gb7|Gb|Gb|Gb|Gb|
|211.0|A|A|A|보류|보류|
|221.0|A7|보류|보류|보류|보류|
|223.0|Bb|Bb|Bb|Bb|Bb|
|225.0|A7|A7|A7|A7|A7|

참조는기존화면코드·TAB·운지대조및Capo.1을반영한개발용9곳이다. 독립청음전사·두번째사람검증이아니다. 모델도보류와7음누락이남으므로 ‘7화음/텐션해결’이라고표현하지않는다. 사전이9·11·13전체를표현하지못하는제약도그대로다.

![원본 파형과 모델의 실제 음 추정](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/tutorial_notes.png)

![199초 원음 스펙트럼](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/spectrum.png)

원본기타추정음198~202초: ![원본](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/tutorial_original_198_202.wav)

컷없는모델의음후보를사인파로재생: ![합성검수음](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/tutorial_raw_notes_sine_198_202.wav)

컷사용모델의음후보를사인파로재생: ![합성검수음](../dataset/integration_review/runs/basic_pitch_20261105_v2/report/tutorial_cut_notes_sine_198_202.wav)

합성검수음은추정된음높이·시작·끝을들어보는도구이며 기타분리음이나 실제연주복원음이아니다. 음색과음량이원음과다르므로 소리가비슷하다는이유만으로정확도를판단하지않는다.

![195초 기존 참조 원본](../dataset/integration_review/runs/tutorial_reference_20261105_v1/pts_195.png)

## 실제 파이프라인 연결

`basic_pitch_worker.py`는라벨없이모델추론만한다. `basic_pitch_adapter.py`는모델의88음출력을D2~E6피치클래스입력으로변환한다. `export_basic_pitch_evidence.py`로현재계약인`guitar_evidence.v1`을만들고 기존`provisional_audio_harmony`까지실제로실행했다.

현재튜토리얼의연결결과는`dataset/audio_analysis/runs/barre_basic_pitch_raw_20261105_v2`와`barre_basic_pitch_cut_20261105_v2`의evidence.json/harmony.json에있다. 원본영상source_id와194초오프셋을명시했고입력해시를검사했다. confirmed note·현번호·접촉판정을만들지않았다. 다른부분의기본실행경로는바꾸지않고모델경로를명시적으로사용할수있게했다.

## 검증과 재현

140개 테스트를 통과했다. 모델 그리드, 기본 문턱, D2/E6 경계, 옥타브 병합, 음 끝의 처리, 무음, 범위 밖 시각 거절, 영상 오프셋, 확정 음으로 승격하지 않는 조건을 확인했다. 기존 오디오·화성 회귀 검사도 통과했다.

374개 출력의 시간 증가·끝부분 보존·평가 시각의 근접성을 전수 검사했다. 최대 마지막 창 간격은11.61ms, 평가 시각과 최근접 모델 프레임 차이는 최대5.71ms다. 합성 시험음의1·10·20초 시작점을 검증한 최대 오차는17.05ms였다. 이 시험으로 실제 음악의 모든 온셋 정확도를 보장하지는 않는다. 정답을 보고 시계를 보정하지 않았다.

추론 누적 처리 시간은431.7초다. 파일 입출력·필터·기본 후처리·첫 JIT 시간이 포함돼 반복 속도 벤치마크로 해석하지 않는다. `run_pretrained_audio.py`의 원음→모델→evidence.json→harmony.json 전체 명령도 실제 실행해 확인했다.

```powershell
.venv-audio-model/Scripts/python.exe basic_pitch_worker.py --tasks dataset/integration_review/runs/basic_pitch_20261105_v2/tasks_all.json --output dataset/integration_review/runs/basic_pitch_20261105_v2/predictions
python evaluate_basic_pitch.py
python audit_basic_pitch.py
python report_basic_pitch.py
python -m unittest test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

일반 오디오 파일에는 다음처럼 모델 경로를 명시적으로 실행한다. `--input-mode raw`는 파형 컷 없이 모델에 주되 출력 음 후보를 D2~E6로 제한한다. `cut`은 입력 파형도 자른다. 기존 FFT 경로를 자동으로 대체하지 않는다.

```powershell
python run_pretrained_audio.py --audio PATH_TO_WAV --source-id SOURCE_ID --offset VIDEO_START_SECONDS --input-mode raw --output NEW_OUTPUT_DIRECTORY
```

완료된 평가 파일은 덮어쓰지 않는다. inference는 모델·입력 해시가 일치하는 기존 추론만 재사용한다. 모델/버전/소스 해시는 predictions/model.json, 평가 조건은 evaluation_config.json, 입력/음 후보는 각 추론 JSON, 세부 성적은 records에 있다. 기존 자료는 보존했다. 시간 문제가 있던 v1에는 superseded 표시를 붙였고, 내보내기 명령에서도 해당 결과를 거절한다.
