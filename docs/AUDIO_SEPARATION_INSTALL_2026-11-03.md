# 로컬 음원 분리 설치 완료 — 2026-11-03

사용자가 “일단 설치하고 알려줘”라고 승인하여 프로젝트 전용 환경에 설치했다. 기존 Python과 각 담당 모듈·원본 결과는 변경하지 않았다. 최초 샌드박스의 외부 DNS 접근 실패 후, 승인된 패키지/모델 다운로드만 네트워크 허용 실행으로 수행했다. 음원 업로드·유료 API 호출은 없다.

## 설치와 버전

- Python3.10.11, `.venv-audio-separation/Scripts/python.exe`
- Demucs4.1.0 / torch2.14.1 CPU / numpy2.2.6 / sphn0.2.1
- 모델: 공식 `adefossez/HTDemucs`, htdemucs, 4-source 모델의 vocals / 나머지 합산 분리
- Hugging Face snapshot: `cbc8a9b1a87023b7fd74e7b3412e6321c0eab003`
- safetensors: 84,025,440바이트, SHA-256 `d9fa14133cfcc034a6758923bb3a8ca9f8dfd0b582134643bbf83f72c17576dd`
- 로컬 모델 캐시: `.cache/audio-models/huggingface`; 설치 캐시: `.cache/audio-install/uv`
- 설치 패키지 메타데이터만으로는 numpy가 설치되지 않아 실행에 필요한 numpy2.2.6을 명시 추가했다. 최종 import/CLI/모델 로딩과 실제 추론 성공.
- `uv pip check` 결과32개 패키지 호환성 통과. 버전 목록은 `audio-separation-requirements.lock.txt`, 모델 경로·해시는 `audio-separation-model-manifest.json`에 보존했다. 버전 목록은 환경 스냅샷이며 모든 플랫폼의 해시 잠금 파일은 아니다.

폴더 파일 크기 합은 환경 약597MB, 모델 캐시 약252MB, 설치 캐시 약587MB다. 캐시 참조·하드링크 등의 중복을 포함할 수 있으며 실제 디스크 추가 점유량과 같지 않다. 모델 실체는 약84MB다.

## 실제 실행 점검

```powershell
python run_local_separation.py --input dataset/audio_analysis/runs/clip_003_012_pts_v3/original.wav --output dataset/audio_analysis/runs/clip_003_012_demucs_install_smoke_20261103
```

위 명령은 이미 실행했다. 재실행하려면 새 output 디렉터리를 지정한다. 래퍼는 프로젝트 전용 Python과 로컬 모델 캐시를 사용하며 `HF_HUB_OFFLINE=1`, CPU4threads, shifts0, segment7, float32, clip-mode none으로 실행한다. 환경 변수는 자식 프로세스에만 적용한다. 기존 출력 디렉터리가 있으면 거부한다.

실행시간 약9.71초, 종료코드0. 입력은 사용자 검수한 보컬+기타의 source3~12초9초 클립이다. 출력:

- `dataset/audio_analysis/runs/clip_003_012_demucs_install_smoke_20261103/htdemucs/original/vocals.wav`
- `dataset/audio_analysis/runs/clip_003_012_demucs_install_smoke_20261103/htdemucs/original/no_vocals.wav`

두 파일 모두44.1kHz stereo float32, 396,900samples/channel, 유한값·샘플 수 일치 확인. manifest·로그·`quality_checks.json`을 새 run에 남겼다. 입력 PTS 매핑은 pts_v3 manifest를 참조한다. 같은 길이는 실제 A/V 동기나 모델 내부 지연의 청각 검증을 대신하지 않는다.

두 추정 stem의 합과 원음의 최대 절대 차는 약0.00679다. 완전 재합성이 보장되지 않으며 이 수치만으로 분리 품질을 평가하지 않는다. 독립 청취·잔여보컬·기타손실 검수는 아직 미수행이다.

## 다음 사용 시 제약

`no_vocals`는 모델이 추정한 반주이며 guitar-only가 아니다. 다른 악기·남은 보컬·분리 아티팩트가 포함될 수 있다. 출처는 `derived_from_separation`, 기타 attribution은 미검증으로 유지한다. 음원 분리 출력에서 음높이를 찾았다는 이유만으로 화성 엔진의 확정 기타 음으로 승격하지 않는다.

다음 오디오 담당은 원음/보컬/반주 비교와 기존 time-local 후보 분석을 수행할 수 있다. 이 설치 점검은 성능 개선을 확인한 실험이나 전체 영상 분리 완료 보고가 아니다. 원본9초만 처리했다.

공식 참고: https://github.com/adefossez/demucs 및 해당 저장소 docs/windows.md. 처음 다운로드 이후 위 래퍼로 오프라인 실행을 검증했다.
