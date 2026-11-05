# 화성 엔진 첫 제출 — 2026-11-02

## 2026-11-04 손가락 의미·체인 P0 완료

전송상태갱신: 사용자가 본인채팅에서 총괄직접전송을 명시적으로 승인한 뒤
완료결과·사진·산출물경로를 총괄01a19c25-9b62-71c2-b30c-3dc5c15966de에
전송성공했다. 아래 거부기록은 승인 전 이력이다.

실제frame210 sidecar v2의30개분포를fusion전에검증했다.
중지/약지/소지18invalid, 엄지/검지12unknown을분리하고 모든가중치에서
오류/미확정손가락의칸배정·MIDI·운지조합0을확인했다. 원질량과좌표는보존했다.
기하/위치/오디오품질과독립인hard gate이며 손복구완료를주장하지않는다.
선택검사78개통과/실패0, Fusion19개. 상세계약·사진·재현·이전자료대조는
`dataset/cell_audio_fusion/report.md` 맨위최종절에있다.

![실제원질량과의미게이트,frame210 PTS8.791667](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_semantic_frame210_20261104_v5/actual_semantic_gate.png)

실제결과는 `dataset/cell_audio_fusion/runs/actual_semantic_frame210_20261104_v5/`
summary.json 및single_fixture_replay.json, 6grid전체/30단일분포결과다.
총괄채팅직접전송은자동승인검토에서승인부족으로거부돼재시도하지않았다.
변경파일·산출물은이보고서와본인채팅에남긴다. API/추론/설치0,
타담당코드/원본/기존run수정0.

## 2026-11-03 D 가상 칸·오디오 결합 제출

새 cell_audio_fusion.py / cell_audio_fusion_replay.py / test_cell_audio_fusion.py,
harmony_input_adapter.py의실제A/B/C어댑터를구현했다. 상세사진·가중치비교·
검증은 `dataset/cell_audio_fusion/report.md`, 계약은
`docs/CELL_AUDIO_FUSION_SCHEMA.md`에있다. 합성5가중치검사와 실제
A v2/B/C공개API18건연결을완료했다. geometry=suspect와 손보류를
유지해 실제조합0이며, 실제원시질량/호환성만진단으로보여준다.
합성결과를실제정확도로해석하지않았다. 관련전체116개통과/실패0,
Fusion12개. 원본/타담당파일/기존run보존, API/다운로드0.

![실제frame124 원질량·음향호환성, 결합판단보류](C:/Users/evev2/Documents/antigravity/GUITAR/dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/clip003012_f000124_candidate_anchor/raw_modalities.png)

원본PTS5.208333의실제입력이다. 왼쪽은원위치질량, 오른쪽은명시표준튜닝
가정의오디오호환성이며 양쪽척도는누름확률이아니다. 실제grid모델6개를
각각분리하며 source/PTS/grid/canvas/행렬·원본해시를검증했다.
반주화성/운지가설/확정기타는분리, 같은오디오증거의중복가산은막았다.
하류제공경로: `dataset/cell_audio_fusion/runs/actual_abc_20261103_v4/`
summary.json과18개input/result, 대표3프레임 raw_modalities.png 및
보류heatmap.png. 실연현/접촉/기하가미확정이라정확도평가는남아있다.

## 2026-11-03 실제 Demucs v5 연결 완료

상태: 이전 Demucs fixture 입력 대기 해소, 실제9개 연결·후보분석 완료.
새 파일 harmony_demucs_review.py, 기존 test_harmony_engine.py 및 자기 스키마/
보고서를 갱신했다. 타 담당 파일·원본·이전 run은 보존했다. API/업로드0.

입력 audio root `dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5`의
최신 보고서, comparison.json, fingering_comparison_index.json,
harmony_replay.json, branch evidence와 실제9개 fixture를 읽었다.
stem_chroma_comparison.png를 시각 확인했다. 공유 원본ID/시간축/PTS 시작,
branch component/separation/피아노 검수 플래그, 실제PCM 해시, 상류 source/
separation/model/review/QA provenance 파일 해시와 parent peak/track 참조를
재생 코드에서 검증했다. source time mapping은 상류 값을 그대로 보존하며
AV correction0, 실제 A/V 지연 미검수라는 제한도 유지한다.

```powershell
python harmony_demucs_review.py --input-root dataset/audio_analysis/runs/clip_003_012_demucs_evidence_v5 --output dataset/harmony_analysis/runs/demucs_v5_review_20261103
python -m unittest test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -q
```

실제9/9 재생 오류0. 전체88개 통과/실패0, 화성27개(병행 변경 포함한 현재
전체 수치). 실제9개를 직접 읽어 source 검증·잠정 상태·namespaced 증거ID·
기타확정/운지가설 비생성·기존출력 덮어쓰기 거부를 회귀검사한다.

새 결과 root `runs/demucs_v5_review_20261103/`:
`comparison.md`는 사용자용3창 비교표, `results.json`은 입력해시와9개 전체
결과·프레임별 후보 근거, `summary.json`은 검증해시와 top1변동/동률 집계다.

| 원본 검토창 | 반주 중앙 eligible frame 잠정 상위3개 | 반주 시간 변동 |
|---|---|---|
| 5.05~5.35 | Abadd9 .961 / Abmaj7 .916 / Ab .914 | Abmaj7 3프레임→Abadd9 9프레임, 변경1 |
| 7.80~8.10 | Cm7 .926 / Eb6 .926 / Cm7b5 .819 | Cm7/Eb6 12프레임 정확동률, 우선정렬은 근거우위 아님 |
| 8.75~9.05 | Abmaj7 1.000 / Ab .949 / Fm7 .911 | Abmaj7 12프레임 최상위, 점수차는 여전히 모호 |

모든 반주창은12프레임 모두 top2 gap<.1로 ambiguous다. 첫창 원음은
Abmaj7 1→Abadd9 11프레임으로 반주와 변화가 유사하고, 둘째/셋째는
최상위가 각각 Cm7(동률)/Abmaj7으로 같다. 보컬stem은 첫창9/12,
둘째1/12, 셋째12/12프레임만 순위가 나오며 첫창 Bmaj7/Cmaj7,
둘째 Cdim/Ebdim/Ebm 동률, 셋째 여러 Eb/Bb 계열 등으로 변한다.
이는 stem의 악기 귀속이나 보컬 잔존·기타 보존을 정량 평가한 것이 아니다.

확정 기타·확정 mixed_audio_harmony·실제 운지가설은9개 모두0이다.
provisional_audio_harmony만 시간별 salience를 독립 사용했고 피크·track·
운지대조 MIDI 후보는 확정/잠정음으로 승격하지 않았다. tuning/capo null,
instrument unknown, string null/contact unknown과 모든 parent persistence
참조를 보존한다. 반주 피아노 존재는 사용자 주관 청취 범위로만 반영한다.
각 코드 후보의 event ID, weighted coverage, matched/missing/extra PC,
원래 salience는 results.json에서 검토 가능하다. scores는 확률이 아니다.

상류/하류 제공: 위3개 결과파일과 재생CLI. 이번 요청 범위 차단 없음.
남은 것은 실제 안정음/개별악기/접촉·가능운지 검증이며 이번 창은 여전히
계약·검토창이다. 현·접촉 미확정 손8점과 프렛 의미 확인으로 음 생성0.
새 Demucs 결과를 기존HPSS와 혼합하거나 그 결과를 덮어쓰지 않았다.

## 2026-11-03 반주 잠정 화성 경로

상태: 구현 완료, Demucs 새 음향 fixture 연결은 상류 입력 대기.
사용자의 주관 검수는 보컬 감소 양호·피아노 청취만 확인한다.
반주를 accompaniment / derived_from_separation=true /
guitar_isolation_verified=false로 유지하며 완전 제거·기타 보존·음 정답은
미검수다. 반주의 피아노 음을 기타 확정 음으로 사용하지 않는다.

변경 파일: harmony_engine.py, harmony_input_adapter.py, test_harmony_engine.py,
docs/HARMONY_SCHEMA.md 및 본 보고서. provisional_audio_harmony에 salience
프레임별 순위와 시간 지지가 있는 tentative_notes 순위를 추가했다.
확정 기타 코드·확정 혼합음 해석·운지 가설과 별도 필드다. 프레임별
weighted coverage와 누락 패널티를 공개하며 점수는 확률이 아니다.
분리 flag가 부모 출처에만 있어도 기타 확정 승격을 차단한다.

현재 실제 Demucs 분석 fixture는 탐색 시 없었다. 따라서 실제 no_vocals.wav
경로·사용자 리뷰·오디오 해시만 보존한
`fixtures/actual_accompaniment_pending.json`을 생성했고 음향 증거는 비워 두었다.
없는 반주 salience를 혼합/HPSS에서 복사하지 않았다. 기존 실제 HPSS 입력은
`fixtures/actual_hpss_salience.json`에 고정했고 Demucs 반주가 아님을 명시했다.

실제 결과: `runs/accompaniment_provisional_20261103/hpss_result.json`에서
5.142879859초는 활성 PC 부족으로 보류, 5.152879859초는 Ab 0.933 /
Abadd9 0.930 / Abmaj7 0.928의 잠정 모호 가설을 출력했다. 이는 실연
정답이나 기타 코드가 아니다. 확정 기타 후보는 계속0이다.
`accompaniment_pending_result.json`은 증거 대기로 정상 insufficient_evidence다.

검증 명령: 이전 절과 동일한 9개 모듈 명시 unittest -q.
현재 전체84개 통과/실패0, 화성26개. 추가 시험은 피아노 포함 salience가
잠정 가설에만 나타남, 시간별 단일 PC를 화음으로 합치지 않음,
NaN salience 거부, 잠정 음 별도 출력 및 부모 분리 출처 비승격이다.
다른 담당 코드·기존 결과 수정0, API/업로드0.

상류 요청: Demucs 반주에서 추출한 time-local salience/tentative fixture와
source identity·분리 provenance·시간축을 제공하면 현재 경로로 연결 가능하다.
현·접촉이 불명인 손 자료에서 운지 음을 만들지 않았다. 실제 반주 기반
성능 검증과 기타 운지 가설 비교는 검수 가능한 상류 증거 도착 후 수행한다.

## 2026-11-03 사용자 혼합 음향 검수 반영

상태: 담당 구현·검증 완료. 관측/사용자 보고: listening review의
“보컬이랑 기타 같이들려”는 vocal_and_guitar 혼합 종류만 확인한다.
실제 음높이·기타별 발음·onset·A/V 동기는 여전히 미검수다.
프렛 부품 의미 검수와 손 visible8/unknown1 검수는 음 생성 입력으로
사용하지 않았다. 손 대응 null, 현·접촉 불명을 화성 엔진이 보충하지 않는다.

변경: harmony_engine.py / harmony_input_adapter.py / test_harmony_engine.py /
docs/HARMONY_SCHEMA.md / 이 보고서. 새 fixture:
`fixtures/actual_pts_v3_mixed.json`. 원본 pts_v3의 5.05~5.35초 fixture를
보존 복사하고 사용자 청취 검수의 원본 ID·구간 범위를 검사한 뒤
source_context와 양쪽 파일 SHA-256을 기록했다. 타 담당 파일 수정0,
외부 API/업로드0. 기존 결과는 보존했다.

출처 정체성 mixed/vocal/accompaniment/unknown/guitar와
spectral/provisional/confirmed 음 상태를 별도로 처리한다. main 기타 후보는
출처가 verified guitar인 확정 음만 받아들이며, 분리 음원 표시가 있으면
기타 확정으로 자동 승격하지 않는다. pitch-confirmed 혼합 음은 별도
mixed_audio_harmony에 가설로 표시한다. possible joint string states는
fingering_hypotheses로 분리해 발음이나 실제 기타 코드로 확정하지 않는다.

검증:

```powershell
python -m unittest test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -q
python harmony_engine.py --input dataset/harmony_analysis/fixtures/actual_pts_v3_mixed.json --output dataset/harmony_analysis/runs/mixed_source_20261103/cli
```

현재 전체 77개 통과/실패0 (병행 개발 중인 다른 담당 검사 포함).
화성 23개: 출처×음 상태 조합, 분리 stem 비승격, source review ID 불일치
거부, 가능 운지 출력 분리, 실제 pts_v3 재생 검사를 포함한다.
실제 새 결과 `runs/mixed_source_20261103/result.json` 및 `cli/result.json`:
피크144개 원시 보존, main insufficient_evidence/코드0,
mixed_audio_harmony insufficient_evidence/코드0. 이는 확정 음 부재와
출처 모호성에 따른 정상 보류이며 실제 연주 정확도 수치가 아니다.

하류 제공: 위 result.json과 계약 문서. 상류 제안: source_identity,
source_attribution_status, derived_from_separation 및 검증 provenance를
pitch_status·event_id·시간 지지와 함께 보존. 다음 실제 기타 코드 검증은
개별 음높이와 기타 출처가 검수된 동시 구간 증거가 필요하다. 새 오디오
fixture가 준비되면 기존 세 계층을 유지해 재생 가능하다. 현재 담당 범위의
차단은 없으며, 기타 출처별 정답·분리 품질 평가는 미완료다.

## 2026-11-03 P0 실제 오디오 계약 수정

보고 상태(Asia/Seoul 2026-11-03): P0 담당 구현 완료. 사용자 승인으로
완료·차단 시 이 파일 갱신 후 총괄 채팅 「프로젝트 개발 방향 지시」
(01a19c25-9b62-71c2-b30c-3dc5c15966de, local)에 직접 보고한다.
현재 관측 결과는 아래 실제 재생·검사 수치이며, 안정 음과 동기 정확도는
미검수다. 후속 오디오 계약 fixture 검증에 필요한 입력은 담당자의 검수된
시간 지지 구간 및 pitch_status가 명시된 증거이며, 이번 완료 범위를 막지는 않는다.

수정 파일: harmony_engine.py, harmony_input_adapter.py, test_harmony_engine.py,
docs/HARMONY_SCHEMA.md, 이 보고서. 새 최소 fixture는
`fixtures/actual_audio_minimal.json`이다. 실제 원본 evidence.json에서 각
후보 계층의 첫 레코드를 추출하고 원본 파일 SHA-256과 선정 방식을 기록했다.
합성 음표를 추가하지 않았다. 다른 담당 소유 파일·기존 run은 수정하지 않았다.

변경 전 총괄 리뷰에서 실제 capo=null 입력의 AttributeError가 재현되었다.
변경 후 missing/null/unknown 객체는 unknown 카포로 정규화된다.
프렛 음은 보류하지만 독립적인 실제 정수 MIDI는 계속 분석할 수 있다.
spectral_peak_candidate와 tentative는 코드·최저 관측음·충돌 계산에서 제외한다.
실제 오디오 피크의 소수 MIDI는 반올림하지 않는다. raw 후보는 그대로 남긴다.

최종 검증 명령:

```powershell
python -m unittest test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -q
python harmony_engine.py --input dataset/audio_analysis/runs/clip_003_012/evidence.json --output dataset/harmony_analysis/runs/actual_audio_20261103/full
python harmony_engine.py --input dataset/audio_analysis/runs/clip_003_012/evidence.json --start 3 --end 3.2 --selection-source contract_smoke_not_stability_review --output dataset/harmony_analysis/runs/actual_audio_20261103/window_003_0032
```

최종 65개 통과/실패0: 기존 리뷰 59개에 화성 경계 회귀 6개 추가.
화성 자체 18개. 시간별 문자열 상태와 음표 모두 창 전체 지지가 없으면
제외하며, 순차 음을 한 화음으로 합치지 않는 시험을 추가했다.
실제 전체 파일과 3~3.2 / 6~6.2 / 11~11.2초 CLI 재생 4건 오류0,
전부 insufficient_evidence / 코드0개다. 전체 입력의 스펙트럼 피크
10,177개는 확정 음으로 승격하지 않고 보존했다.

하류 통합 산출물은 `runs/actual_audio_20261103/`의 full 및 window 폴더
각각의 result.json이다. 원본 source_id·시간축·후보 event_id와 점수 종류를
보존한다. 상류 오디오 담당과의 연결 제안은 docs/HARMONY_SCHEMA.md의
2026-11-03 절: confirmed 정수 concert MIDI / tentative notes / spectral peaks /
salience를 분리하고 event_id, start_s/end_s, pitch_status, score_type을 유지한다.
어댑터는 창 선정 출처를 필수로 기록하고, 창을 지정할 때 확정 증거의
시간 지지가 없으면 거부한다. 확정 음 없는 실제 입력은 정상 보류한다.

두 PC 정책은 보류로 명시했다. 독립적인 E/B 파워코드 인식은 지원하지
않으며 5 사전은 3개 이상 PC와의 비교에만 남긴다. 임계값 완화는 없다.
실제 세 창은 계약 스모크용으로 선정했으며 안정 음 검수가 아니다.
잠정 음·salience 기반 별도 화성 가설 계산, 실제 A/V 동기 검수, 청취,
연주 정답 평가는 수행하지 않았다. 오디오 담당의 이후 새 계약·검수
fixture와의 상호 검증은 남아 있으며 연결 완료나 실연 정확도를 주장하지 않는다.

단계 A·B의 독립 CLI와 단계 C 연결용 보수적 경계 어댑터를 구현했다.
기존 지판·손·현 모듈과 공용 README 및 원본 결과는 수정하지 않았다.
표준 라이브러리만 사용하며 API 호출·학습·오디오 추출은 수행하지 않았다.

## 검증

```powershell
python -m unittest test_harmony_engine test_hand_fret_tracker test_fret_geometry test_baze_client -v
python harmony_engine.py --input dataset/harmony_analysis/fixtures/input.json --output dataset/harmony_analysis/runs/demo
python harmony_engine.py --input dataset/harmony_analysis/fixtures/audio_contract.json --output dataset/harmony_analysis/runs/audio_contract
python harmony_engine.py --input dataset/harmony_analysis/fixtures/legacy_hand.json --output dataset/harmony_analysis/runs/legacy_hand
```

최종 결과: 화성 12개 + 기존 회귀 22개 = 34개 통과, 실패 0개.
3개 CLI 재생 모두 성공. 최초 실행에서 불일치 프렛 검증이 카포 뒤
위치 판정보다 늦게 실행되어 검사 1개가 실패했다. 검증 순서를 수정해
상충하는 두 프렛 입력은 명시적으로 거부하도록 한 뒤 전체를 재실행했다.

검증 범위: 표준 튜닝 모든 현 / 카포 0·1·2 / 상대·물리 프렛 등가,
카포 중복 가산 방지, X·뮤트·미연주·불명, 잘못된 프렛 거부,
옥타브 중복, 확인된 전위, 모호성, 무음·두 음의 코드 배정 보류,
가능 운지와 발음 분리, 사전 모든 품질의 정확한 음집합, 증거 충돌,
기존 손 캐시에서 참조 코드 유입 방지를 검사했다.

## 검토 가능한 출력

- `runs/demo/result.json`: 합성 MIDI 52·55·59·62 = E3·G3·B3·D4.
  Em7과 G6 모두 PC {2,4,7,11}, 누락·추가 없음, score 1.0.
  베이스 미확인으로 slash 없음, status=ambiguous.
- `runs/audio_contract/result.json`: 합성 오디오 계약 C4·E4·G4.
  C major의 일치 PC {0,4,7}, 누락·추가 없음, score 1.0.
  실제 오디오 검출 결과가 아니다.
- `runs/legacy_hand/result.json`: 기존 5초 손 캐시의 선택 손 위치 후보와
  원본 레코드 해시를 보존한다. 현·접촉 미확정이므로 음 생성 0개,
  코드 후보 0개, status=insufficient_evidence.
- 단위검사에서 G 모양의 확정 발음 가정에 카포 1을 적용하면 Ab가
  최상위다. shape_symbol은 튜토리얼 모양 규칙 검수 전이므로 null이다.

점수는 `(일치 수 - 0.5*누락 수 - 추가 수)/합집합 크기`를 0 이상으로
제한한 유사도다. 구성 요소·음·증거 ID·사전 가정을 출력에 공개했다.
보정된 확률이나 실제 연주 코드 정확도로 해석할 수 없다.

## 미확정 및 다음 단계

단계 C의 실제 오디오 연결과 관측 동기화, 현 상태 결합·조합 탐색은
상류 계약 준비 후 진행한다. 현재 어댑터는 손가락 최고 후보를 합치지
않으며 손 결과만으로 발음·베이스를 만들지 않는다. 입력의 명시적
joint string_states만 계산한다. 오디오·확정 현 음집합 불일치는 보수적으로
evidence_conflict를 반환하므로 부분 관측도 검수 대상으로 남는다.

합성 fixture는 source_id=null이며 실제 영상 SHA-256을 꾸며 넣지 않았다.
기존 손 레코드의 시간 길이는 1/24초라는 가정을 따로 기록했다.
전체 영상이나 3~12초 구간의 실제 발음·화면 참조 검수는 수행하지 않았다.
독립 촬영 성능, 접촉 검출, 기능화성, 진행 분석, TAB 출력은 이번 범위 밖이다.
상세 계약과 사전은 `docs/HARMONY_SCHEMA.md`에 있다.
