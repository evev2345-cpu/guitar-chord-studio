# C 완료: 실제 가상 grid × 음향 호환성 — 2026-11-03 (Asia/Seoul)

**C 모듈·실제 연결·사진/fixture·D 계약 검증 완료.** 보고서 갱신 후 총괄 채팅에 실제 경로·검증·사진과 함께 직접 전송했고 성공 응답을 확인했다. 높은 음향 점수도 실제현/접촉/기타음으로 승격하지 않는다. 정밀 기하·anchor·튜닝·카포·악기 귀속 미확정은 보존했다. 신규 설치/다운로드/모델 추론/API/업로드0회. 원본/기존run/타 담당파일 보존.

## 실제로 제공한 결과

신규 audio_cell_compatibility.py, test_audio_cell_compatibility.py, audio_cell_demo.py, audio_cell_grid_demo.py, docs/AUDIO_CELL_SCHEMA.md 및 새 run을 만들었다. 먼저 합성cell과 실제 Demucs v5를 독립 연결했고, A 출력이 준비된 뒤 실제 grid를 추가 연결했다. 합성 run은 실제 grid인 것처럼 바꾸지 않았다.

최종 실제 결과: `runs/audio_cell_actual_grid_20261103_v3/bundle.json`. A의 same_frame_fixture.json에서 frame124/190/210의 6모델을 각각 읽어 원음/반주/보컬 54건을 계산했다. 실제 원본 source_id/index/PTS/BGR pixel hash를 확인하고 A의 assert_grid_compatible로 canvas/M/M_inv/grid version/ID를검증했다. 각모델의grid_id를독립보존하며결합키는(grid_id,cell_id)다. frame120/PTS5.041667은 첫음향창5.05~5.35 밖이므로강제로연결하지않았다. 전체11프레임66grid의완료가아니라3대표프레임18grid의54대조다.

각 모델마다 전체36셀의 주파수/지속/PC 점수를 분리했다. D audio branch adapter 54개는 D의 현재 validate에서 모두 통과했다(d_contract_validation.json). 검증에 video.fingers=[]를 명시했으며 손 질량이나 실제운지 조합은 만들지 않았다. D의 가중치결합이나 B 손분포 구현을 대신하지 않았다.

## 관측·추정·미검수 구분

관측: 현재 HTDemucs 반주를 사용자가 듣고 보컬감소양호와 피아노포함을 확인했다. 피치/onset/기타보존/모델아티팩트 정답은 확인하지 않았다. 반주 derived_from_separation=true/guitar_isolation_verified=false, 모든 candidate의 instrument_attribution=unknown이다.

추정: 튜닝6→1 [40,45,50,55,59,64]는 명시적 표준튜닝 가정이다. capo=null. 물리프렛p의 예상MIDI는개방튜닝+p로 계산해카포를중복가산하지않는다. 상대프렛만있고카포를모르면점수null이다. 실제칸의confirmed_physical_fret_num과physical_string_num은null이며 A의조건부번호를정답으로바꾸지않았다.

미검수: 기하상태suspect, 정확기하/접촉판정false, contact/sounding=unknown이다. 위치질량·누름확률·발음확률을 계산하지않는다. 같은음은다른현/피아노에서도나오므로오디오만으로공간칸을확정하지않는다.

## 점수와 실제 수치

exact_frequency_score는같은완전지지STFT창의상대피크진폭×cents커널을프레임별최대화/평균한0~1휴리스틱이다. persistent_frequency_score는지속피크와현재창의겹침을반영한별도진단, pitch_class_score는원래chroma성분평균이다. **D용audio_compatibility_score는exact_frequency_score만**이다. PC-only를exact로승격하거나세지표를독립확률처럼곱하지않는다. None은결측/예상음미확인, 0은입력은있지만선택후보지지가없는상태로구분하며뮤트로바꾸지않는다. 자세한수식/분모/score_type은스키마문서에기록했다.

|대표프레임/PTS|오디오창|반주36cell중주파수후보지지|PC-only|최대exact지표|
|---|---|---|---|---|
|124 / 5.208333|5.05~5.35|11|6|0.675402|
|190 / 7.958333|7.80~8.10|9|10|0.742956|
|210 / 8.791667|8.75~9.05|10|3|0.918348|

위수치는candidate_anchor모델의조건부후보범위이며적중률이아니다. 6개anchor/spacing모델은같은가상현/프렛label을유지하므로같은label의음향점수차는0이다. 이는기하가맞다는검증이아니라오디오점수가공간경계변화를구별하지못한다는한계다. 서로다른모델에서유리한cell을섞지않았다. 손위치질량변화와60:40/80:20/40:60 비교는B/D의독립영역이다.

### 원본 frame124 / 실제 PTS5.208333와 조건부 오버레이

위는원본디코딩프레임, 아래는A의추정공통좌표grid에C의exact호환성을입힌그림이다. 색범위0~1이며노랑쪽은상대호환성이높고보라쪽은낮다. 실제현검출/접촉정답이아니며그림의TAB는계산입력이아니다.

![원본 frame124와 실제 후보 grid의 음향 호환성](runs/audio_cell_actual_grid_20261103_v3/baseline/frame_124_audio_grid_overlay.png)

### 실패·미확정: frame210 / 실제 PTS8.791667

기하suspect와접촉unknown을남겼다. 높은음향지지색이있어도피아노/배음일수있고, 해당손가락이그칸을누르는것을뜻하지않는다.

![frame210 원본과 미확정 grid 호환성](runs/audio_cell_actual_grid_20261103_v3/baseline/frame_210_audio_grid_overlay.png)

### 실제 음향과 옥타브 혼동 사례

파랑=원음,주황=반주,보라=보컬모델stem. 세기존창의실제파형/FFT이며생성형이미지가아니다. 반주에피아노가들린다는사용자확인을유지한다. 보컬stem에서작은신호의상대chroma가커져도잔여보컬양으로해석하지않는다.

![동일 창의 실제 원음 반주 보컬 파형과 스펙트럼](runs/audio_cell_compatibility_20261103_v1/waveform_spectrum_comparison.png)

합성cell s6_p3(표준가정97.999Hz)에실제반주의784.3Hz피크를옥타브대안으로보존했다. exact=0, PC약0.040이며이대안을정확한저음지지로합치지않는다. 초록점선은합성예상음,빨강점선은실제관측피크다. 이그림의cell은실제grid정답이아니며예시선택은탐색적이다.

![합성 cell와 실제 반주의 옥타브 혼동을 분리한 실패 예시](runs/audio_cell_compatibility_20261103_v1/octave_only_failure.png)

재생자료: [원음/반주/보컬 재생과 비교](runs/audio_cell_compatibility_20261103_v1/review.html). 기존청취확인을반복요청하지않는다. 원음과처리음의9초WAV를이페이지에서각각재생할수있다.

## 하류 D에게 제공한 정확한 계약

`bundle.frames[].models[].components.accompaniment`의 result/small_fixture/fusion_audio가각각전체C결과/6셀표본/D전용audio branch의절대경로다. 원음·보컬도동일구조다. 대표반주adapter:

`runs/audio_cell_actual_grid_20261103_v3/models/frame_124/candidate_anchor/accompaniment_fusion_audio.json`

frame190/frame210도같은경로규칙이다. `anchor_minus3`, `anchor_plus3`, `spacing_minus10pct`, `spacing_plus10pct`, `margin_only_alternative`는별도grid_id다. small fixture는사전에고정한물리프렛1후보의6가상현이며점수가높은cell만고르지않았다. 전체결과는같은폴더/accompaniment.json이다. 원본source/frame/canvas/M과C의tuning/capo가정, cents/주파수분해능/시간지지/evidence ID/배음모호성/보컬stem근접ID를보존했다.

D adapter는score_type=normalized_compatibility_0_1,cells[cell_id].score=exact A,evidence_ids,evaluation_status를제공한다. null은그대로전달하고0은평가된무지지/PC-only임을상태로기록한다. quality_status=usable은특징대조가계산가능하다는뜻이지기타귀속/기하가좋다는뜻이아니다. geometrysuspect 보류를D가해제하면안된다.

## 검증·한계·재현

`python -m unittest test_audio_analysis test_audio_cell_compatibility test_cell_audio_fusion test_virtual_string_grid -q`: **58개통과/실패0**. 이중C새검사16개, 오디오20개다. 카포중복가산/상대프렛unknown/옥타브-PC분리/결측-미검출/시간·source거부/부분창보류/동음다른현모호성/score의미검사/실제54개grid별adapter와참조를검증했다. D계약실재생54/54통과. py_compile 성공. 실제그림파일존재와대표출력을열어확인했다.

```powershell
python audio_cell_grid_demo.py --grids dataset/virtual_string_grid/runs/clip_003_012_20261103_v2 --audio-parent dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5 --output dataset/audio_analysis/runs/audio_cell_actual_grid_replay --all-models
python -m unittest test_audio_analysis test_audio_cell_compatibility test_cell_audio_fusion test_virtual_string_grid -q
```

잔여한계: 실제기타음/셀접촉정답없음, 표준튜닝가정/카포null, piano와보컬잔여/배음귀속unknown, 정확기하suspect, 같은모델공통오류미해결, 기존음향창안정성/onset/AVsync미검수. 높은점수나후보개수변화를실연정확도향상으로보고하지않는다. 합성fixture와실제grid결합fixture는폴더와data_origin으로분리했다. 현재승인범위의계산·검증·제공은완료했으며다음은B/D가동일키로위치질량과연결하는단계다.

---

# HTDemucs 반주·원음·보컬 비교 — 2026-11-03 (Asia/Seoul)

상태: **승인된 현재 분리 결과의 비교·후보/fixture 제공 완료**. 새 run `runs/clip_003_012_demucs_evidence_v5`. 아래 과거의 로컬분리 자산 부재는 총괄의 승인 설치로 해결됐다. 이번 작업에서는 추가설치·모델다운로드·재추론·API·업로드0회다. 원본/기존 결과/타 담당 소유파일을 보존했다.

## 사용자 확인과 상류 검증

user_demucs_listening_review_20261103.json: 사용자는 보컬 분리가 잘 됐고 피아노도 들린다고 주관 검수한 뒤 현재 반주를 유지하고 진행하도록 승인했다. 반주no_vocals.wav의 해시는 a97673fb6a1aa8f31fddd124c32459f55c4cc3fcdc645f28e2c06d8fe555be1f로 사용자 기록과 일치한다. 이 확인은 완전보컬제거·기타보존·기타단독·실제음정답 확인이 아니다. 혼합종류나원음청취를 재요청하지 않았다.

상류 docs/AUDIO_SEPARATION_INSTALL_2026-11-03.md, docs/audio-separation-model-manifest.json, 분리run separation_manifest.json/quality_checks.json을 읽고 원음입력hash, 두stemhash, 원본ID, 구간/timebase, rate/shape/finite를 재검증했다. 기존 HTDemucs4.1.0/torch2.14.1 CPU/공식HTDemucs cached model의 생성결과를 사용했으며 이번에 모델을 실행하지 않았다. 분석은 기존 프로젝트 Python/NumPy/SciPy에서 수행했다. 모든 증거에 source/separation/QA/model/user provenance 경로와해시를 보존했다.

원음/반주/보컬모두44.1kHz·396900samples·stereo9초다. pts_v3의원본time mapping을 보존하고 적용AV correction0이다. 원음과각stem의PCM을 새branch에byte-copy하고 분석mono를 별도 생성했다. stem합의원음재구성 최대잔차0.00679217/RMS0.000890933으로 상류와일치한다. sample길이일치는 실제AV동기나모델내부지연 검증이 아니다.

## 관측 수치와 해석 제한

|9초구간|onset후보|peak레코드|지속peak track|정수배모호성track|
|---|---|---|---|---|
|원음|63|10170|371|253|
|반주|54|10028|348|221|
|보컬stem|33|7611|369|195|

모두같은window/hop/상대threshold를 사용했다. counts는 음표수·검출정확도·보컬제거율이 아니다. 지속track은 겹치는STFT창의rounded-MIDI peak를 연결한후보이고 기본음정답이 아니다. 보컬stem에도 기타누출/아티팩트가능성이 있으므로 각피크의악기는unknown이다.

|원본시간|반주chroma TV vs 원음|반주energy/원음|반주peak중보컬stem동시주파수근접|겹친track 원음→반주→보컬|
|---|---|---|---|---|
|5.05~5.35|0.042680|0.919862|13/144|21→19→17|
|7.80~8.10|0.022388|0.889271|24/144|23→28→8|
|8.75~9.05|0.002571|0.994275|6/144|20→20→28|

chroma TV는12차원정규화salience의0.5×L1변화이며 실제확률차가아니다. peak 근접은 같은STFT frame에서35cents이내다. **13/24/6개가잔여보컬개수라는뜻은아니다.** 보컬과악기의공통음, 배음, 모델누출이모두가능하다. 피아노오염은사용자청취로반주에존재함을알지만개별peak중피아노음은모른다. 기타음·피아노음·남은보컬을 분리할정답은없다. 반주상대에너지가유지되거나chroma가거의같아도 기타보존/실제음정답을보장하지않는다. 특히작은보컬stem의높은상대peak score는절대음량이큰보컬이라는증거가아니다.

사용자의보컬감소양호는user_reports_good_not_quantified로기록했다. residual_vocal_amount=unmeasured, guitar_loss/audible_artifacts=unreviewed, guitar_isolation_verified=false다. 피아노포함반주사용이라는현재방침을유지하며추가분리시험을자동수행하지않았다.

## 운지 대조용 식별자·화성 fixture

mixture/accompaniment/vocals 각branch에manifest/evidence/overview 및기존3개time-local fixture를저장했다. 총9개fixtures다. event ID에는component접두사를붙이고parent track evidence_ids/배음참조도갱신하여stem사이ID충돌을피했다.

각fixture의fingering_comparison_candidates와root/fingering_comparison_index.json은창별MIDI후보/medianHz/cents/score/peak evidence_ids/distinct frame count를제공한다. persistence_context는fullparent track ID와해당창교집합을보존한다. 보컬stem근접evidence_ids도반주후보에서찾을수있다. 하류는운지에서가능한MIDI와이ID를대조할수있으며, 맞는음이라도피아노가같은음을낼수있으므로기타발음확정은아니다.

현재실제손/물리현/접촉의검증된possible-note자료를이담당이생성하지않았다. 특히확인된frame120손검수는손대응null/현접촉미검증이고, 예제운지fixture를실제영상정답으로사용하지않았다. string_num=null/contact=unknown/capo=null/tuning=null/observed_audio_notes=[]를유지한다. source_identity.component=accompaniment, derived_from_separation=true, guitar_isolation_verified=false와piano_audible_in_reviewed_accompaniment=true를반주에보존했다.

현재화성adapt_audio/analyze로9개실제fixture재생: **9/9 크래시0,모두insufficient_evidence/코드후보0** (harmony_replay.json). 피크를확정기타음으로승격하지않는정상보류다.

## 검증·변경파일·재현

`python -m unittest test_audio_analysis -v`: **20개통과/실패0**. 새검사는보컬stem동시주파수근접이악기귀속을변경하지않음, namespaced track참조일관성, 실제반주fixture의time support/unknown contact/null capo/evidence ID연결을포함한다. `python -m py_compile audio_stem_analysis.py test_audio_analysis.py` 성공. 상류hash/sample QA 및실제9개화성재생도통과했다. 원본3창의chroma차트는stem_chroma_comparison.png로시각확인했다.

변경: 신규audio_stem_analysis.py, test_audio_analysis.py, docs/AUDIO_SCHEMA.md, 본보고서, 신규demucs_evidence_v5 run. 설치래퍼/분리환경/분리원본/README/타담당모듈수정0.

```powershell
python audio_stem_analysis.py --manifest dataset/audio_analysis/runs/clip_003_012_pts_v3/manifest.json --separation-manifest dataset/audio_analysis/runs/clip_003_012_demucs_install_smoke_20261103/separation_manifest.json --review dataset/audio_analysis/references/user_demucs_listening_review_20261103.json --output dataset/audio_analysis/runs/clip_003_012_demucs_evidence_replay
python -m unittest test_audio_analysis -v
```

제공경로: `runs/clip_003_012_demucs_evidence_v5/comparison.json`, `fingering_comparison_index.json`, `harmony_replay.json`, `stem_chroma_comparison.png`; 각branch/fixtures/audio_5.05_5.35.json, audio_7.80_8.10.json, audio_8.75_9.05.json. 권장음향비교대상은반주branch이지만기타전용이아니다. 다음연결은하류의운지가능음가설과원본ID/시간을대조하는것이며, 물리현·접촉·기타발음확정에는여전히근거가부족하다. 기존정밀onset/안정창/AV정답부족도그대로남는다.

보고서갱신후사용자승인된총괄채팅에직접보고한다.

---

# 사용자 청취 반영·혼합 오염 진단 — 2026-11-03 (Asia/Seoul)

상태: **사용자 검수 반영·설치 없는 진단·실제 fixture 연결 완료 / 학습 vocals-accompaniment 분리는 로컬 자산 부재로 부분 차단**. 원본/pts_v3/기존 run은 보존했다. 새 run은 `runs/clip_003_012_mix_v4/`다. 아래 이전 보고의 혼합unknown은 이 새 검수로 갱신되며 onset/pitch/A/V 검수는 여전히 미완료다.

## 확인된 사용자 검수와 적용 범위

`references/user_listening_review_20261103.json`: project_user가 pts_v3의3~12초 original.wav를 듣고 **“보컬이랑 기타 같이들려”**라고 확인했다. source_id/timebase/구간을 검증하고 파일 해시와 reviewer/scope를 새 증거 provenance에 반영했다. 같은 질문을 다시 요청하지 않았다.

확인된 것은 보컬+기타가 함께 들린다는 source-type 정보다. 다른 악기는unknown, 기타 단독 피치/onset/개별 현/접촉/A/V sync 정답은 없다. 사용자 청취 검수1클립, 담당 에이전트 자체 청취0, 확정 pitch/onset0이다. 지판/손 검수나 운지 예상 음을 음향 정답으로 사용하지 않았다. 각 피크·onset·chroma·track에 instrument_attribution=unknown, source_component를 보존한다.

## 로컬 도구·가중치 확인과 구체적인 차단

활성 Python3.10.11, NumPy2.2.6/SciPy1.15.3/Matplotlib3.10.6, torch2.14.1+cpu, CUDA false, onnxruntime1.23.2. torchaudio/demucs/spleeter/openunmix/audio_separator/librosa/soundfile은 활성 interpreter에 없다. 프로젝트의 .pt/.pth/.th/.ckpt/.onnx 파일과 표준 Torch hub/checkpoints/HuggingFace/audio-separator cache를 확인했으며 소스분리용 가중치는 식별하지 못했다. 프로젝트의 기존 .pt는 지판/pose 자산이다. 모든 외부 디스크나 다른 가상환경의 부재까지 주장하지 않는다. 상세 경로·탐색 범위는 local_environment.json.

이 상태로는 pretrained vocals/accompaniment 모델을 실행할 수 없다. 실제로 필요할 조건은 (1) 로컬 분리 패키지/실행기, (2) 그 실행기와 호환되고 출처/체크섬이 확인된 pretrained weight의 명시 경로, (3) 활성 CPU 환경에서 검증 가능한 의존성, (4) 출력 sample rate/길이/지연 검증이다. 새 대형 weight 다운로드·외부 서비스·전역 환경 변경을 자동 수행하지 않았다. 사용 가능한 로컬 모델 경로가 제공되거나 별도로 설치/다운로드 범위를 승인받아야 학습 분리를 진행할 수 있다. 특정 모델의 기타 보존 성능이나 실행시간/메모리는 현재 자료로 평가하지 않았다.

## 설치 없이 수행한 실제 진단

`audio_mixture_diagnostics.py` 신규 작성. 새 run에서 mixture byte-copy, mid/side 공간 성분, STFT median 기반 harmonic/percussive 진단 성분을 생성했다. **이들은 vocals/accompaniment 분리가 아니며 accompaniment 또는 guitar-only로 부르지 않는다.** 실제 vocals_stem/accompaniment_stem은null이다.

원본 및 세 분석 branch 모두44,100Hz·396,900samples·stereo9초이며 pts_v3의 local_to_source offset과 source_id를 유지했다. source_id는 MP4 식별자이고 각 PCM hash와 component/run_id는 별도다. source PTS gap을 재보정하거나 AV offset을 추가하지 않았다. STFT는 offline time/frequency median31bins, window2048/hop512, 원본 mixture phase, complementary power2 soft mask를 사용했다.

- L/R correlation **0.990598**, mid energy ratio **0.995289**, side **0.004711**. 중앙 억제만으로 보컬을 제거하면서 기타를 보존할 근거가 부족하다. 이는 공간 진단이며 실제 기타 손실량 측정은 아니다.
- harmonic component energy ratio **0.658562**, percussive **0.077449**. soft mask 출력끼리 상관되므로 합이1일 필요가 없고 악기 비율로 해석하지 않는다.
- 저장된 float32 H+P의 원본 재합성 최대 절대잔차 **1.49e-08**. sample grid/원본 길이/시간 매핑도 일치(quality_checks.json). 이 수치는 원음 복원 검사일 뿐 잔여보컬·기타손실·음향아티팩트 검증이 아니다.
- 잔여보컬/기타손실/청각 아티팩트는 **unreviewed**. 원본 stem 정답과 새 성분의 청취 평가가 없어 수치를 만들지 않았다. 특히 보컬 모음은 harmonic에, 기타 어택은 percussive에 들어갈 수 있어 어느 쪽도 기타 정답이 아니다.

동일3창의 chroma 변화(total variation, 정규화 salience 변화이며 확률/보컬 제거율 아님):

|원본 시간|H vs mixture|P vs mixture|
|---|---|---|
|5.05~5.35|0.07067|0.20700|
|7.80~8.10|0.04149|0.31751|
|8.75~9.05|0.02942|0.27296|

성분 처리만으로 음고 후보 증거가 달라짐을 관측했다. 이것이 보컬 제거의 성공인지 기타 손실인지 분리할 근거가 없다. harmonic의 상위 pitch class 순위가 유지된 세 창도 기타 음으로 확정하지 않았다. 전체 비교는 diagnostics.json과 component_chroma_comparison.png. component_review.html은 같은 시간의 원본/H/P/side를 재생할 수 있는 검토자료이며 별도의 혼합 종류 재확인을 요구하지 않는다. 브라우저 UI 자체의 실사용 청취 검수는 수행하지 않았다.

## 하류 산출물·검증

각 branch (`mixture`, `harmonic_component`, `percussive_component`)의 manifest.json/evidence.json/overview.png 및 fixtures/audio_5.05_5.35.json, audio_7.80_8.10.json, audio_8.75_9.05.json을 제공한다. 총9개 실제 time-local fixture다. source_identity, reference hash, provisional pitch_status, event_id, method, score_type과 동일 시간 지지를 보존한다. capo/tuning=null, observed_audio_notes=[]이며 시점/성분을 독립 음표처럼 합치지 않는다.

현재 화성 adapt_audio/analyze에9개 fixture를 재생: **9/9 크래시0, 모두 insufficient_evidence/코드후보0**. harmony_replay.json에 입력 경로와 출력 저장. 현재 계약은 혼합 피크를 확정 기타 음으로 승격하지 않고 정상 보류한다. 다른 담당 소유 코드는 수정하지 않았다.

검증: `python -m unittest test_audio_analysis -v` **17개 통과/실패0**. 새 검사는 complementary-mask 재합성·임펄스 sample grid, stereo center 진단, 잘못된 사용자 source_id 거부, 실제 mixed fixture의unknown attribution/null capo/비승격 보존이다. `python -m py_compile audio_analysis.py audio_mixture_diagnostics.py test_audio_analysis.py` 성공. 실제 output PCM 길이/rate/source offset/float32 재합성 QA 통과. 새 대형 설치·다운로드·외부 API0.

변경 파일: 신규 audio_mixture_diagnostics.py, audio_analysis.py의time-local source_identity 보존, test_audio_analysis.py, docs/AUDIO_SCHEMA.md, 본 보고서, 새 mix_v4 산출물. 원본·기존 run·공용 README·타 담당 소유 파일 변경0.

실행 명령(새 output 폴더 필요):

```powershell
python audio_mixture_diagnostics.py --manifest dataset/audio_analysis/runs/clip_003_012_pts_v3/manifest.json --review dataset/audio_analysis/references/user_listening_review_20261103.json --output dataset/audio_analysis/runs/clip_003_012_mix_replay
python -m unittest test_audio_analysis -v
```

다음 핵심 문제는 기타 음의 source attribution이다. local trained model이 없는 동안은 확인된 혼합 상태와 후보별unknown을 유지하며, H/P 또는 중앙억제 출력을 기타 확정 음으로 전달하지 않는다. 기존 정밀 onset/안정창/A/V sync의 정답 부족도 그대로 남는다. 사용자 승인된 보고 규칙에 따라 총괄 채팅(01a19c25-9b62-71c2-b30c-3dc5c15966de, local)에 이 결과와 구체적인 부분 차단을 직접 전송했고 성공 응답을 확인했다.

---

# 오디오 P0 갱신 — 2026-11-03 (Asia/Seoul)

상태: **구현·실제 fixture 연결 완료 / 청취·정답·정밀 A/V 검수는 입력 필요**. 권장 run은 `runs/clip_003_012_pts_v3`다. 아래 이전 보고서는 이력이며 기존 산출물을 수정하지 않았다. 중간 실험 `clip_003_012_v2`는 초기 PTS 간격을 반영하지 않은 비교 이력이다. 통합에는 v3를 사용한다.

## 관측: 실제 PTS 매핑 결함과 수정

영상 start PTS=0.041667, audio stream start PTS=0은 실제 A/V 지연의 정답이 아니다. 더 중요한 별도 문제를 발견했다. ffprobe decoded audio frame의 첫 frame은 PTS0/1024samples, 다음 frame은 PTS0.064898이다. 누적 raw PCM의 두 번째 frame 시작은1024/44100=0.023219955초이므로 **0.041678045초 PTS 간격**이 남는다. 이후 전체 decoded timeline에는 추가 segment 전환이 없었다. audio_frame_probe 전체는 새 manifest에 보존했다.

기존 추출은 원시 PCM 누적 표본을 재생 시간과 같다고 가정해 이 간격을 누락했다. 이번 수정은 segment별 `source_s=sample_index/44100+offset_s`를 사용한다. 디코더 출력11,767,808samples/channel은 ffprobe frame nb_samples의 합과 일치했다. PTS 간격을 가로지르는 요청은 거부한다.

| 항목 | 기존 | 수정 후 |
|---|---|---|
|3~12초 raw sample 범위|[132300,529200)|[130462,527362)|
|선택 segment sample→source offset|0|0.041678045s|
|원본 채널·샘플레이트|stereo/44100|동일|
|실제 A/V 동기 보정|미검수|미검수, 적용0|

표본 시작 차이는1838samples. 기존 WAV[:-1838]과 새 WAV[1838:]는 배열이 완전히 같다. PCM 내용의 변형이나 리샘플링이 아니라 원본 PTS에 맞춘 구간 선택 수정이다. 이전 audio feature 시간을 비교하려면 약+41.678ms의 매핑 차이를 고려해야 한다. **영상 프레임을41.667ms 일괄 이동하는 수정이나 실제 A/V delay 보정이 아니다.** mapping_correction.json에 전후 근거를 기록했다. manifest start_s/end_s의 표본 반올림 오차는1sample 이내다.

video_pts.json/pts_mapping.csv는 실제 프레임별 PTS와 재생 시간 대응이다. frame0 PTS0.041667이며 frame_index/24와41.667ms 차이가 난다. av_frame_identity.json에는21개 원본 decoded BGR pixel SHA-256과 악보를 가린 crop PNG file SHA-256을 별도로 저장했다.

## 관측과 보류: 스트로크3곳·청취·수작업 참조

3곳의 원본 프레임 연속영상을 악보 영역 없이 파형과 나란히 검토했다(av_stroke_0~2.jpg). 큰 하향 손동작은 보이지만 실제 현 접촉 순간은 불명확하다. 다음 손동작 구간은 접촉시간 정답이 아니다.

|검토|관측 손동작 구간(원본 PTS 초)|파형 에너지 상승의 잠정 구간(수정 PTS 초)|판정|
|---|---|---|---|
|1|4.916667~4.958333|4.986678~5.001678|contact unknown|
|2|7.625~7.708333|7.776678~7.786678|contact unknown|
|3|8.583333~8.625|8.681678~8.701678|contact unknown|

손동작과 파형의 대응도 잠정이다. 영상24fps의41.667ms 표본 간격, 블러와 접촉 가림 때문에 1프레임 이내 sync 여부를 확정하지 못했다. sync_error_s=null이며 보정 전/후 모두 적용0이다. 관측상 지연 가능성을 배제하지 않지만 세 구간을 근거로 실제 A/V correction을 추정하지 않는다. agent_visual_review.json에 상태/근거/전후 시간을 기록했다.

청취 기능이 없는 실행 환경이므로 실제 청취0, 혼합 상태unknown이다. 확정 onset0/목표10, 확정 pitch0, 검수 완료 안정창0/목표3, 독립 검수0이다. 파형만 본 onset 잠정 참조3개와 스펙트럼 검토 대상창3개를 제공했으며 확정 라벨로 쓰지 않는다. 보고 수치를 채우기 위한 추측 라벨은 만들지 않았다. 수동 참조는 출력 후보를 이미 본 뒤 작성되어 선택 편향이 있다.

review_score_hidden.mp4는 악보/TAB를 가린 재생용9초 clip이다. 원본 PTS를 기준으로 video/audio trim하며 원본 waveform WAV와 별도로 손실 사본임을 표시했다. review_clip_provenance.json/검토 clip probe를 보존했다. review.html은 로컬 video/native stereo 재생, 원본시각 표시, JSON 라벨 저장을 제공한다. 브라우저 상호작용은 이번 환경에서 실사용 검수하지 않았다. review_template.json은 별도로 직접 입력할 수 있다.

필요한 최소 입력: 검토자가 클립을 듣고 기타 외 보컬/반주 혼합 여부, 독립적으로 확인 가능한 onset(목표10개, 실제 가능 개수만), 안정 음 창(목표3개), 각 시간의 불확실성을 기록해주어야 한다. 영상에서는 현 접촉을 식별 가능한 스트로크가 있는지 재검수해야 한다. 원본 자체가 접촉을 보여주지 않으면 해당 항목을unknown으로 유지한다.

## 추정: 짧은 onset 창과 긴 pitch 창 비교

v3의 실험 옵션 --split-windows: onset1024/hop220=23.22/4.99ms, pitch8192/hop441=185.76/10ms. onset 후보63개, 같은 PCM의 긴 창 onset22개, spectral peak10170개, 지속 peak track371개다. 피크·track 개수는 음표 수가 아니다. harmonic_ambiguities가 있는 track253개는 실제 배음 확정 개수가 아니라 겹친 낮은 피크와2~6배수 관계라는 휴리스틱 표시다.

잠정 파형 참조3개와의 최근접 오차(선택 편향이 있으므로 정밀도/재현율로 쓰지 않음):

|참조시각|짧은 창 오차|긴 창 오차|
|---|---|---|
|4.994178|+67.77ms|+18.70ms|
|7.781678|+34.01ms|+1.20ms|
|8.691678|+46.92ms|+1.20ms|

이 작은 진단에서는 짧은 창이 좋아지지 않았다. 23→64 같은 후보 수 증가도 성능 개선이 아니다. 따라서 짧은 창을 기본으로 승격하지 않고 선택 실험으로 남겼다. 완전한 독립 onset 정답이 없어 전체±50ms 일대일 precision/recall/MAE는 여전히null(evaluation_pending.json)이다. 매칭 함수 자체는 중복검출·누락·일대일 최적매칭을 합성 시험으로 검증했다. 오탐/누락 개선이나 실연 pitch 옥타브 오류율을 주장하지 않는다.

세 로컬 spectrum을 시각 검토했으나 다수의 피크/배음이 존재하며 기본음 정답을 분리하지 못했다(local_spectra.png). 연속5창 이상의 rounded MIDI 피크를 연결하고 중간 간격이 생기면 분리한다. 창이 겹치므로371 tracks는 독립 발음 횟수가 아니다. 의도적 뮤트/현 번호/음악적 코드명/확정 음은 출력하지 않는다.

## 제공 계약 및 실행 검증

화성용 실제 fixture: runs/clip_003_012_pts_v3/fixtures/audio_5.05_5.35.json, audio_7.80_8.10.json, audio_8.75_9.05.json. 서로 다른 시간의 음을 합치지 않으며 전체 창 지지가 해당 구간에 들어온 관측만 포함한다. 선정은 검수 대상 지정이며 안정성 확정이 아니다. capo=null/tuning=null, observed_audio_notes=[]가 정상 계약이다. peak 및 persistence 후보는 그대로 candidate 상태다. 원본 SHA-256, run ID, method, event ID, score_type, 창/시간 정보와 선정 출처를 보존한다.

현재 화성 담당의 수정된 adapt_audio/analyze를 **읽기만 하여** 위3개 fixture에 실행했다. 3/3 크래시0, 모두 insufficient_evidence/코드후보0이다(harmony_replay.json). 증거 부재에 대한 정상 보류이며 실제 코드 인식 성공을 뜻하지 않는다. 다른 담당 소유 파일·공용 README는 수정하지 않았다.

검증:

- python -m unittest test_audio_analysis -v: **13개 통과**. PTS 불연속 매핑, 실제 PCM 재추출 동일성, 짧은 창, 지속/배음 모호성, 미검수 정답, 일대일 매칭, 실제 time-local fixture를 포함한다.
- python -m unittest test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -v: **72개 통과/실패0** (검증 시점의 공동 파일 기준).
- python -m py_compile audio_extract.py audio_analysis.py audio_review.py audio_visual_review.py test_audio_analysis.py: 성공.
- 외부 API/추가 설치0. 새 직접 의존성은 없음(visual review는 프로젝트 기존 OpenCV 사용).

변경 파일: audio_extract.py, audio_analysis.py, test_audio_analysis.py, 신규 audio_review.py/audio_visual_review.py, docs/AUDIO_SCHEMA.md, 본 보고서 및 신규 dataset/audio_analysis/runs/* 산출물.

재현(원본 명시 경로를 cases.json에서 재사용하며 새 output 폴더 지정):

```powershell
$video = (Get-Content dataset/chord_video_review/cases.json | ConvertFrom-Json)[0].video
python audio_extract.py --video $video --start 3 --end 12 --output dataset/audio_analysis/runs/clip_003_012_pts_replay
python audio_analysis.py --manifest dataset/audio_analysis/runs/clip_003_012_pts_replay/manifest.json --split-windows
python audio_review.py --manifest dataset/audio_analysis/runs/clip_003_012_pts_replay/manifest.json
python audio_visual_review.py --manifest dataset/audio_analysis/runs/clip_003_012_pts_replay/manifest.json
```

실제 확정 정답이 필요한 나머지 항목은 검토자 입력이 있어야 완료 가능하다. 그와 무관한 시간축 수정·검토 패키지·계약·회귀 검증은 완료했다. 사용자 승인에 따라 보고서 갱신 후 총괄 채팅(01a19c25-9b62-71c2-b30c-3dc5c15966de, local)에 완료/부분 차단 상태를 직접 전송했고 성공 응답을 확인했다.

---

# 오디오 기준선 첫 실행 (2026-11-02)

구현·로컬 실행 완료, 첫 제출 완료 기준의 청취/영상 동기화/실음 수작업 검수는 미완료다. 기존 원본·손 모듈·README는 수정하지 않았다. 외부 API 0회, 추가 패키지 설치 0회.

## 확인 결과

원본 경로와 SHA-256은 runs/clip_003_012/manifest.json에 기록했다. ffprobe 실제 결과: 영상 H.264 1280×720, 24fps, time_base 1/12288, start_time 0.041667s. 오디오는 AAC 44,100Hz stereo, time_base 1/44100, start_time 0, duration 266.885397s. **영상 시작 PTS가 오디오보다 41.667ms 늦으므로 frame_index/24만으로 동기화하지 않는다.**

3~12초를 디코딩 표본 [132300,529200)로 잘랐다. 396900 samples/channel. 원본 채널과 모노 자료를 분리하고 rate를 보존했다. mono RMS/평균 채널 RMS=0.997651로 이 구간의 전체 RMS 상쇄는 작다. 이는 주파수별 상쇄가 없다는 증거는 아니다.

실행 산출물: original.wav, analysis.wav, manifest.json, evidence.json, overview.png. onset 후보 23, 창별 spectral peak 후보 10177, chroma 프레임 882, acoustic 창 89. 중복 피크 수는 실제 음표 수가 아니다. 분석 실행 시간은 evidence.json provenance.analysis_elapsed_s에 기록했다. 전체 추출 소요시간은 이번 실행에서 별도 계측하지 않았다.

## 검증과 제한

`python -m unittest test_audio_analysis -v`: 6/6 통과. 440Hz 정현파 위치, 220+440Hz 혼합 보존, 침묵과 뮤트 구분, 감쇠음 어택, 잡음을 의도적 뮤트로 확정하지 않음, 짧은 입력 거부를 검증했다. 합성 통과는 실연 성능 검증이 아니다.

실제 청취 0구간, 수작업 onset 0, 수작업 pitch 0, 수작업 acoustic event 0, 영상/파형 스트로크 비교 0, 독립 검수 0. 기타 단독인지 반주/보컬 혼합인지 현재 unknown이다. 이 실행 환경에서 소리를 들었다고 주장하지 않는다. refs는 references/review.json에 별도 보존한다.

동기화 오차 및 1프레임 이내 여부: 미측정. 보정값 확정 없음. onset ±50ms 일대일 매칭의 precision/recall/MAE: 미평가(null). 피치 옥타브 오류율·누락·오탐: 실음 정답 부재로 미평가. 배음과 기본음 구분을 구현하지 않았으므로 옥타브 중복 및 잘못된 기본음 해석이 예상되는 구조적 한계가 있다. mute성 타격/일반 피킹 구분은 unknown을 유지한다. 짧은 창/감쇠만으로 note offset을 확정하지 않는다.

## 재실행

프로젝트 루트 PowerShell:

```powershell
$video = (Get-Content dataset/chord_video_review/cases.json | ConvertFrom-Json)[0].video
python audio_extract.py --video $video --start 3 --end 12 --output dataset/audio_analysis/runs/clip_003_012_rerun
python audio_analysis.py --manifest dataset/audio_analysis/runs/clip_003_012_rerun/manifest.json
python -m unittest test_audio_analysis -v
```

cases.json의 명시적 원본 경로를 재사용하며 폴더의 첫 MP4를 고르지 않는다. 다음 단계는 클립 청취, 코드/TAB를 보지 않고 독립적인 실음 표본 라벨 작성, 실제 PTS로 추출한 영상의 명확한 스트로크 3개 이상과 파형 비교다. 그 검수가 안정되기 전 194.88/217.21/206.04초로 확대하지 않았다.
