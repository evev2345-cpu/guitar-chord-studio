# 현 대응과 손 선택 실패 원인 확인 — 2026-11-03

최종 산출물: `dataset/integration_review/runs/joint_failure_diagnosis_20261103_v2/`.

## 확인 범위

원본frame124(5.208333초)·190(7.958333초)·215(9초)를 시각 점검하고, 두 앞 프레임의 현검출과 세 번째 창8.75~9.05초의8개 손 관측을 분석했다. 악보/코드 화면은 모델·비교의 입력으로 쓰지 않았다. 추가 사람 검수·API·학습·새 MediaPipe 추론은 없다. 기존 독립 ROI 추론과 기존 현검출기를 재사용했다.

## 두 프레임의 현 대응

기본5개 선 경로를 원본에 역투영하고, 원본→확장 평탄화의 여유20/30/40px에서 재검출해 같은 공통 좌표로 비교했다. 원본 지판 좌표와 현담당 기준을 바꿔 저장하지 않고 진단 run에만 기록했다.

|프레임|기본 선 후보 수|20px 여유|30px 여유|40px 여유|
|---|---:|---:|---:|---:|
|124|5|6|6|5|
|190|5|5|6|6|

기본5개 경로는 대체로 유지됐지만, 추가 선은 가장자리 조건에 민감했다. 예를 들어 frame124에서20px여유 추가선은 공통y≈140,30px여유 추가선은y≈2로 서로 다른 쪽이다. 따라서 ‘6개가 나온 설정’을 선택해 화면순서=물리6현으로 확정할 수 없다. source visibility·경계/반사 오검출과 누락 가능성을 구분할 독립 원본 참조가 없다.

원본 역투영 이미지: `frame_124_string_diagnostic.png`, `frame_190_string_diagnostic.png`. 이는 코드로 그린 검출 경로와 padding 민감도 과학적 시각화이며 사람이 정답 선을 찍은 자료가 아니다. 실제 물리 현 대응은 **미해결**로 유지한다. 먼저 수행한 가능한6가지 순서 매핑도 여전히 조건부다.

## 세 번째 창의 실제 실패 원인

전체 화면에서 검출된 손의 손목은 대체로 원본x≈115~131인 피킹 쪽이다. 지판 쪽 손은 원본x≈970에 보이지만 전체 화면 모델이 놓쳤다. frame210은 전체 화면에 검출 손0개다. 지판 근처가 아니라는 선택 결과는 피킹 손을 올바르게 거부한 결과이며, 문턱을 낮춰 피킹 손을 선택하는 수정은 잘못이다.

같은 프레임에서 독립 실행해 저장해둔 지판 ROI 추론은8개 중7개에서 손1개를 제공했다. 최신 프레임별 지판으로 다시 투영하면 이7개는 기존의 근접성 기준을 통과했다. frame212는 ROI에도 손이 없어 계속 실패다.

즉 주원인은 **전체 화면의 운지 손 검출 누락 + ROI를 별도 후보로 사용하지 않던 경로**다. 단일 원인으로 가림·블러·해상도 중 하나를 확정하지 않았다. 고정/수동 지판 자체의 유효성도 여전히 미검증이다.

## 수행한 다음 작업

- `investigate_joint_failures.py`에 동일 프레임 ROI 복구 후보 경로를 추가했다. 원래 full 화면 상태와 손 관측은 수정하지 않았다.
- ROI가 정확히1개이며 최신 지판 근접성을 통과한 경우만 별도 후보로 남겼다. 여러 ROI/미검출/멀리 있는 손은 선택하지 않는다. 이전 프레임 좌표를 복사하지 않는다.
- ROI는2D 픽셀 관측만 있었으므로 2D 어댑터용 z=0은 실측 깊이가 아님을 명시했다. full 화면의 hand index와 ROI index는 다른 출처다.
- ROI 후보7개를 같은 프레임의 지판·현·오디오3번째창에 연결했다. 원본source/PTS/pixel 해시를 검사했다.
- 조건부 선→현 매핑 아래 주파수 일치 후보가 생겼다. 주된6프레임의 후보에는 C3(MIDI48)·A♭2(44)·A♭4(68)가 포함됐지만, 손가락이 실제 누른 현이나 발음임을 의미하지 않는다. 비접촉 소지 후보도 포함될 수 있다. frame210은 서로 다른 위치·매핑 양상을 보여 별도 보존했다.
- 두 pitch class C/A♭만으로 A♭ major/maj7/add9를 구분할 수 없고, 피아노 음·배음·모델 누출과의 일치 가능성도 남는다. 확정 코드 생성0, 확정 접촉0이다.
- 창 중앙값에 대한4손끝 위치의 중앙 편차는7프레임에서 약1.03~3.07px, 전체 관절 최대편차는 약4.69~21.75px였다. 이것은 실제 움직임을 포함하므로 정확도나 순수 지터 수치가 아니다.

## 운영 반영의 경계

Kim frame120에서는 ROI 모델 평균오차가 full 모델보다 컸다. 따라서 이번7개 후보 증가를 검증된 복구 성공률로 보고하지 않는다. 기존 production gate를 풀거나 손 선택 성공으로 덮어쓰지 않았고, 새 경로는 `uncorroborated_roi_location_candidate_only` 상태다. 정확기하suspect·물리현미확정·접촉unknown은 유지한다.

## 파일과 검증

- 신규 코드 `investigate_joint_failures.py`, 회귀검사 `test_joint_failure_investigation.py`.
- 최종run `result.json`: padding별 선·원본현 결과·ROI 진단·7개 음향대조 전체·입력해시.
- `roi_candidate_observations.json`: 출처가 분리된7개 ROI 후보, `diagnosis.md`:8프레임 상태표.
- `frame_124_string_diagnostic.png`, `frame_190_string_diagnostic.png`: 원본 역투영과padding 실험.

```powershell
python investigate_joint_failures.py --output dataset/integration_review/runs/joint_failure_diagnosis_20261103_v2
python -m unittest test_joint_failure_investigation test_joint_evidence_review test_baze_client test_fret_geometry test_hand_fret_tracker test_fingertip_probability test_chord_photo_validation test_hand_quality test_string_detector test_audio_analysis test_harmony_engine -q
```

11모듈**97개 통과/실패0**. 이후 시간변동 진단·보고서 추가 후 직접관련9개를 다시 실행해 모두 통과했다. 새 검사는 원래 실패 상태 불변, 기존full선택 비대체, ROI미검출/다중검출 보류, 먼손 거부를 포함한다. 기존run을 덮어쓰지 않으므로 재실행은 새 output을 지정한다.

다음 개선 우선순위는 전체화면/ROI의 위치근거를 구분한 후보 정책 검증과 가장자리 현의 원본 가시구간 추적이다. 단순 임계값 완화·6개 강제검출·화면코드에 맞춘 번호 배정은 하지 않는다. 이 결과만으로 추가 사용자 검수를 즉시 요청하지 않는다.
