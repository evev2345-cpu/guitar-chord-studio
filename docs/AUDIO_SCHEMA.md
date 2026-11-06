> 2026-11-03 수정: 아래 최초 추출의 단일 origin 가정은 원본의 초기 오디오 PTS 간격을 누락했다. 현재 계약과 권장 run은 이 문서 끝의 v3 절을 따른다. 기존 run은 이력으로 보존한다.

# 오디오 증거 스키마 / baseline v1

`guitar_evidence.v1`, 모든 시간은 `source_video_seconds`다. 표본/참조는 `dataset/audio_analysis/`에 있다. 직접 의존성의 로컬 검증 버전은 해당 디렉터리 requirements.txt에 기록했다. 추가 설치나 네트워크 호출은 없다.

## 추출

`audio_extract.py --video <명시적 경로> --start 3 --end 12 --output <새 폴더>`

원본 SHA-256을 source_id로 쓴다. 원본 전체를 native rate/channel float32 PCM으로 디코딩한 후 `[round((start-origin)*sr), round((end-origin)*sr))`를 자른다. origin은 audio start_time - format start_time이다. FFmpeg AAC skip_samples 처리를 사용하며 추가 priming 보정은 하지 않는다. 컨테이너 시간 매핑 가정으로서 실제 영상 동기화는 별도 검수한다. 비영 start_time/불연속 PTS를 가진 다른 원본에서는 재검증이 필요하다.

original.wav는 채널 보존, analysis.wav는 채널 산술평균이다. 리샘플링하지 않는다. manifest는 원본 ffprobe 전체 출력, 도구 버전, 실행 인수, 샘플 범위, 채널 RMS와 모노 상쇄 비율을 보존한다. 추출 명령의 임시 PCM 경로는 실행 이력이며 영구 자산 경로가 아니다. 기존 manifest가 있으면 덮어쓰지 않는다.

## 분석

`audio_analysis.py --manifest <manifest.json>` → evidence.json, overview.png.

공통 필드: schema_version, run_id, source_id, start_s/end_s ([start,end)), timebase, tuning/capo (미검수 null), assumptions, evidence, provenance, status, limitations.

- onsets: 점 사건 time_s, event_id, score, score_type, method, status=candidate. 양의 spectral flux의 상대 피크. 최대 flux 기준 점수이며 확률이 아니다.
- pitch_candidates: event_id, start_s/end_s, midi(실수), frequency_hz, frequency_resolution_hz, pitch_status=spectral_peak_candidate, score/score_type, method, status. 스펙트럼 피크가 기본음이라는 보장은 없다. end_s는 창 끝이며 offset_status=analysis_window_only다. 화성 담당은 이를 확정 observed_audio_notes로 승격하면 안 된다.
- pitch_class_salience: time_s(창 중심), C=0 순서의 12차원 salience. 선택한 피크의 상대 진폭 합을 정규화한 수치다. 옥타브나 현 복원에 쓰지 않는다.
- acoustic_events: 창 구간, event_id, RMS, spectral flatness score, method, status, acoustic_state=silent/unknown. 낮은 RMS는 silent일 뿐 muted가 아니다. 감쇠와 의도적 뮤트는 미추정이다.

Hann 8192, hop 441 (44.1kHz에서 약185.76ms/10ms), 기본 bin 간격 5.383Hz. 중심시간 flux는 창의 전후 신호를 섞으므로 onset 정밀도가 hop과 같지 않다. 명목 lookahead는 반 창 92.88ms이며 offline 분석이다. 보간은 피크 위치를 세밀화할 뿐 주파수 분해능을 개선하지 않는다. 저음 인접 반음과 배음/옥타브 혼동이 남는다.

`fixtures/harmony_input.json`은 첫 프레임과 소수 사건을 담은 계약용 자료다. 전체 구간이나 확정 음표 자료가 아니다. `references/review.json`은 알고리즘에서 읽지 않는 검수 기록이다. 빈 정답의 평가 수치는 null이며 0점이나 100%로 해석하지 않는다.


## 2026-11-03: 원본 PTS 매핑 및 분리 창 계약

권장 실제 출력: `dataset/audio_analysis/runs/clip_003_012_pts_v3/`.

`audio_extract.py`는 이제 모든 decoded audio frame의 best_effort_timestamp_time 및 nb_samples를 검사한다. raw PCM 누적 sample index와 PTS의 차이가 2 samples를 초과하면 새로운 연속 segment를 만든다. manifest.decoded_timeline은 각 segment의 first_sample/end_sample, offset_s, first_source_s를 갖는다. **source_time = raw_sample_index / sample_rate + segment.offset_s**다. `decoded_origin_video_s`는 최초 원점이며 구간 전체의 상수 매핑으로 사용하면 안 된다. 실제 선택 구간의 상수는 decoded_sample_mapping_offset_s이고 local_to_source_offset_s는 잘린 WAV의 로컬 0에 해당한다. segment 사이 PTS 간격을 가로지르는 추출은 추측/침묵 삽입 대신 거부한다. ffprobe frame sample 합과 실제 raw decoder sample 수도 일치해야 한다. 현재 원본에서는 첫 1024 samples 뒤에 약41.678ms PTS 간격이 존재한다. 이 매핑 수정은 실제 A/V 지연 보정이 아니다.

`--split-windows` 실험 모드는 onset Hann1024/hop220 (44.1kHz에서23.22/4.99ms), pitch Hann8192/hop441 (185.76/10ms)을 별도로 쓴다. 기본 CLI는 호환을 위해 긴 창 onset이다. 실험 결과에 onsets는 짧은 창, legacy_long_window_onsets는 같은 PCM의 긴 창 비교 자료다. 창 중심, lookahead, correction을 provenance에 기록한다. onset의 uncorrected_time_s/time_s는 같으며 applied_correction_s=0이다. PTS 매핑을 반영한 원본 시각이며 임의의 동기 보정은 없다.

pitch_tracks는 동일 반올림 MIDI의 피크가 연속5창 이상 유지되는 구간이다. frame_count는 독립 측정 수가 아니고 center_span_s는 겹친 창 중심의 지속 길이다. pitch_status=persistent_spectral_peak_candidate, score_type=median_relative_spectral_peak_amplitude이며 확정/잠정 기본음으로 승격하지 않는다. 겹치는 낮은 피크의2~6배수(35cents 이내)는 harmonic_ambiguities에 남긴다. 이 플래그는 실제 배음 판정이 아니며 낮은 피크가 누락되면 오류를 놓친다. 두 독립 발음도 정수비가 될 수 있어 삭제/합치지 않는다.

time_local_evidence(record,start,end)는 범위 밖 요청을 거부한다. pitch/acoustic는 전체 창 지지가 구간 안에 있는 항목만 남기고 chroma도 반 창 여유를 요구한다. 구간 경계를 넘는 track은 보류한다. 이는 다른 시점의 음을 한 화음으로 합치는 방지를 위한 보수적 정책이다. observed_audio_notes=[]; capo/tuning=null은 정상 입력이다. fixtures/audio_5.05_5.35.json 등 세 구간은 실제 원음 후보이지만 안정 구간 정답으로 검수되지 않았다. 선정 출처는 automatic_review_target_not_validated_stable다.

review_template.json/review.html은 화면 악보 없이 청취/검수할 자료다. review_score_hidden.mp4는 손·기타만 crop한 손실 검토 사본이며 분석에는 원 PCM을 쓴다. video_pts.json/pts_mapping.csv는 실제 프레임 PTS 대응, av_frame_identity.json은 원본 decoded BGR 해시와 crop PNG 파일 해시를 구분한다. frame_pts_s는 원본 PTS, source_video_s는 format start_time을 뺀 시간이다. 현재 원본 format start=0이다.

evaluate_onsets는 ±50ms 내 순서 보존 일대일 매칭에서 매칭 수를 우선 최대화하고 총 오차를 최소화한다. reviewed=False는 정답0개라도 precision/recall/MAE=null이다. 부분/편향 표본은 전체 구간 평가로 쓰지 않는다.


## 2026-11-03: 사용자 혼합 검수 및 mix_v4 계약

`references/user_listening_review_20261103.json`은 사용자가 pts_v3 original.wav를 듣고 보컬+기타가 들린다고 확인한 근거다. 이 한 클립의 source-type 검수이며 onset/pitch/다른 악기/A/V sync 정답은 아니다. reference의 source_id/timebase/구간을 검사하고 파일 SHA-256을 evidence.provenance.listening_review에 기록한다. 원본 MP4 source_id는 변환 전후 동일하고 component/run_id/PCM file hash를 별도로 쓴다.

새 출력 `runs/clip_003_012_mix_v4/{mixture,harmonic_component,percussive_component}/`는 source_identity에 input_mix=vocal_and_guitar, other_sources=unknown, component, instrument_attribution=unknown, guitar_isolation_verified=false를 갖는다. 모든 피크·track·chroma·onset·acoustic event에도 instrument_attribution=unknown과 source_component를 붙인다. time_local_evidence는 source_identity 및 listening provenance를 보존한다. observed_audio_notes는 비어 있고 capo/tuning은null이다. 보컬 또는 기타 단독 음으로 승격하지 않는다.

`audio_mixture_diagnostics.py --manifest ...pts_v3/manifest.json --review .../user_listening_review_20261103.json --output <새 폴더>`는 설치된 패키지/캐시를 기록하고 추가 설치·다운로드·외부 API 없이 진단한다. mixture 원본 stereo WAV는 byte copy다. 조화·타격 성분은 SciPy STFT2048/hop512, magnitude의 time/frequency median31bins, power2 soft mask를 사용한다. 두 성분의 mask 합은1이고 원본 phase로 ISTFT한 뒤 원본 길이로 자른다. 44.1kHz에서 창46.44ms/hop11.61ms, 시간 median은 전후15hop(약174.15ms)을 보며 offline이다. 두 성분의 합이 원음을 복원하는 검사는 소스 분리 정확도나 성분별 어택 지연이0이라는 검증이 아니다. 출력 sample grid와 PTS mapping은 그대로 유지하며 임의 동기 보정은0이다.

조화 성분은 기타의 동의어가 아니며 보컬도 조화적일 수 있다. 타격 성분에는 기타 어택/보컬 자음 등이 섞일 수 있다. mid=(L+R)/2, side=(L-R)/2의 공간 성분도 instrument stem이 아니다. `vocals_stem=null`, `accompaniment_stem=null`은 실제 vocals/accompaniment 분리를 하지 않았다는 뜻이다. 학습 분리모델은 현재 실행환경에 없으며 이 진단을 대체 분리 결과로 부르지 않는다.

diagnostics.json은 채널 상관/mid-side 에너지, 조화/타격 에너지와 같은 시간창의 chroma total variation을 비교한다. 성분별 에너지 비율 합은1일 필요가 없고 악기별 비중이 아니다. 변환 전후 salience 변화도 보컬 오염 제거량이 아니다. residual_vocals/guitar_loss/audible_artifacts는 청취/독립 stem 부재로unreviewed다. quality_checks.json은 저장된 WAV sample grid·원본 ID·mapping·재합성 잔차만 검증한다. 실제 소스 품질 수치로 쓰지 않는다.

3창×3성분의 fixture는 각 성분/fixtures 아래에 있다. 모두 실제 혼합 신호에서 나온 provisional 후보이며 source_identity와 같은 구간 지지를 유지한다. 원본 source_id가 같아도 세 성분은 서로 다른 처리 결과이므로 중복 증거를 독립 음표로 합치지 않는다.


## 2026-11-03: 기존 HTDemucs stem 분석 v5

`audio_stem_analysis.py`는 **이미 생성된** separation_manifest.json과 upstream quality_checks.json, user_demucs_listening_review_20261103.json을 입력으로 받는다. 입력 원음/반주/보컬 stem의 SHA-256, 원본source_id, 사용자 검수 구간/timebase 및 rate/shape/finite를 검증한다. 모델 추론·설치·다운로드·업로드는 하지 않는다. 원본/기존 run을 보존하고 새 output directory만 생성한다.

각 branch `mixture/accompaniment/vocals`는 별도 run_id/원 PCM hash를 가지며 원본 MP4 source_id와 pts_v3 mapping은 공유한다. source_identity는 component, derived_from_separation, guitar_isolation_verified=false, instrument_attribution=unknown을 보존한다. piano_audible_in_reviewed_accompaniment=true는 반주에 대한 사용자 청취 범위다. vocals branch도 모델 추정 stem이며 개별 피크가 보컬이라는 정답이 아니다. 전체분석 record.provenance.separation에 상류 source/separation/QA/model manifest 및 사용자 청취 기록의 경로·해시·scope를 저장한다. 설치 환경은 상류를 참조하며 이번 특징 분석은 기존 프로젝트 Python에서 실행한다.

피크/track/onset/acoustic/chroma의 event_id는 component 접두사를 붙여 서로 구별하고, track evidence_ids/harmonic link도 같이 갱신한다. 동일3창의9개 fixture는 기존 complete-window-support 정책을 유지한다. 서로 다른 stem은 독립 악기 정답으로 합치지 않는다.

accompaniment peak의 coincident_vocal_stem_evidence_ids는 같은STFT frame에서35cents 이내인 vocals peak ID다. 이 값은 공통 음·배음·모델 누출이 모두 가능한 **대조 단서**이며 잔여보컬 라벨/누출률이 아니다. 특히 낮은 주파수에서5.38Hz 해상도와 피크 보간의 불확실성도 남는다. vocals stem의 작은 신호도 프레임 최대치로 정규화되므로 높은 상대score가 높은 실제 발음 에너지를 뜻하지 않는다.

fingering_comparison_candidates는 같은창의 rounded MIDI별 peak evidence_ids/median frequency/median cents/상대score/peak_record_count/distinct_analysis_frame_count를 제공한다. persistence_context는 해당peak를 지지하는 full parent track ID와 현창의 교집합 시간만 제공한다. 이는 음표 분할이나 검수된 기본음이 아니다. string_num=null/contact=unknown, instrument_attribution=unknown, observed_audio_notes=[]다. 실제 손/현/프렛을 이 담당이 추정하지 않으며 하류는 가능음 대조만 수행할 수 있다. 운지와 맞더라도 피아노가 같은음을 낼 수 있으므로 기타발음 확정 기준이 될 수 없다.

comparison.json의 counts는 후보 수이며 정확도나 음표 수가 아니다. chroma TV는 같은시간창의정규화salience 차이, stem energy_ratio_to_mixture는 실제 출력 에너지 비교일 뿐 분리율이 아니다. reconstruction error/sample grid검사는 완전 재합성/악기보존/모델내부지연의 검증이 아니다. 사용자 subjective vocal reduction 확인과piano presence를 보존하되 residual_vocal_amount는unmeasured, guitar_loss/audible_artifacts는unreviewed다.
