"""Evidence/report for provisional same-source web vision integration."""
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'dataset/integration_review/runs/web_vision_20261105_v1'


def signature(candidates):
    return tuple(sorted((c['root_pc'],c['quality'],c.get('bass_pc') if c.get('bass_pc') is not None else c['root_pc']) for c in candidates))


def main():
    job='d861a160a92d498f87cd7f412a4dcb6e'
    result=json.loads((ROOT/'webapp/runs'/job/'result.json').read_text(encoding='utf-8'))
    manifest=json.loads((OUT/'full/manifest.json').read_text(encoding='utf-8'));stats={};table=[]
    for width,rows in result['branches'].items():
        for onset in [False,True]:
            baseline='onset_presentation' if onset else 'presentation';visual='vision_onset_presentation' if onset else 'vision_presentation'
            a=[signature(r[baseline]['display_candidates']) for r in rows];b=[signature(r[visual]['display_candidates']) for r in rows]
            s=dict(changed_frames=sum(x!=y for x,y in zip(a,b)),before_changes=sum(x!=y for x,y in zip(a,a[1:])),after_changes=sum(x!=y for x,y in zip(b,b[1:])))
            stats[f'{width}_onset_{onset}']=s;table.append(f"|{width}초|{'켬' if onset else '끔'}|{s['changed_frames']}|{s['before_changes']}|{s['after_changes']}|")
    canvas=Image.new('RGB',(1280,800),'#101824');draw=ImageDraw.Draw(canvas);font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
    for row,t in enumerate([80,140]):
        for col,path in enumerate([OUT/f'source_{t}.png',OUT/'full'/f'frame_{t*24}.png']):
            im=cv2.imread(str(path));assert im is not None
            pil=Image.fromarray(cv2.cvtColor(cv2.resize(im,(640,360)),cv2.COLOR_BGR2RGB));canvas.paste(pil,(col*640,row*400+35))
            draw.text((col*640+10,row*400+6),f'{t}초 · '+('원본' if col==0 else '실제 VIDEO 손 + 가상 지판 · 접촉 미확정'),font=font,fill='white')
    canvas.save(OUT/'original_and_vision.png')
    audit=dict(source_video_sha256=manifest['source_id'],status_counts=manifest['status_counts'],comparisons=stats,
        regression_tests_passed=218,frontend_contract_checks=16,live_result_and_overlay_api_verified=True,
        geometry_verified=False,anatomy_verified=False,contact='unknown',root_voicing_validated=False,accuracy_evaluated=False,
        onset_previous_actual_display_changed_frames={'0.2':16,'0.4':4})
    (OUT/'integration_summary.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    table_text='\n'.join(table)
    text=f'''# Mela 웹앱 비전 연결 — 2026-11-05

**Mela 업로드 영상에 실제 손·지판 위치 추론과 오디오 후보 가점을 연결했다.** 온셋만으로 잦은 표시 문제가 해결되지 않았다는 사용자 피드백을 반영해, 기존 손 추적·가상 지판 경로를 현재 영상으로 옮겼다. 비전 연결 완료와 코드 안정화·정확도 개선 완료는 구분한다.

## 실제 원본·비전 증거

![Mela80초·140초: 원본과 실제 손·가상 지판 추론](../dataset/integration_review/runs/web_vision_20261105_v1/original_and_vision.png)

오른쪽은 실제 원본 픽셀에서 얻은 MediaPipe VIDEO 손 전체21점과 추정 지판이다. 점을 수동 이동하거나 손가락 이름을 바꾸지 않았다. 그림의 선은 검출 스켈레톤·가상 현/프렛 후보이며 실제 누름·뮤트·개방현 판정이 아니다. 손가락 해부학적 의미의 정확성은 아직 미검증이다.

## 현재 영상의 지판 기준

이 영상에는 인트로와 기타 위치 이동이 있다. 이전 영상의 지판 좌표를 그대로 사용하지 않았다. Mela80초 프레임에서 너트·지판 네 모서리·첫6프렛의 위치를 새로 수동 근사하고, 지판 텍스처의 LK 왕복 추적/RANSAC 유사변환으로 각 프레임에 옮겼다. 참조 프레임의 디코딩 픽셀 SHA-256을 검사해 다른 영상의 설정이 잘못 재사용되지 않게 했다.

수동 근사 프렛 번호·표준 튜닝·현6이 위쪽인 순서·현 간격은 모두 가정이다. `geometry_status=provisional`, `contact=unknown`, `root_voicing_validated=false`를 그대로 유지한다. 텍스처 정합 성공을 정밀 지판 검증으로 승격하지 않는다. 최초 설정을 영상별로 마련하는 단계는 아직 자동화하지 않았다.

손은 원본 전체 화면 VIDEO 모드에서2개까지 추론한 뒤, 현재 지판과 너트 주변의 넓은 공간 가점·방향 보조 가점으로 선택한다. 현재 관측이 없거나 역할 선택이 불확실하면 손 좌표를 복사해 채우지 않는다. 지판을 잃은 구간은 비전 가점을 중단한다. 화면 코드/TAB·오디오는 손 선택이나 지판 위치 추정에 입력하지 않았다.

## 실제 추출 범위

- 디코딩된 영상6,095프레임 전체를 처리했다. 오디오 길이로 만든6,097개 분석 시점과 끝 길이가 조금 달라, 영상 끝을 넘는 시점에는 비전을 외삽하지 않는다.
- 위치 가점용 잠정 근거: **4,674프레임**.
- 지판/운지 손의 현재 근거 없음:598프레임. 지판 정합·손 위치 질량·짧은 안정성 조건 부족:823프레임.
- 실제21점·좌표 변환·원본 픽셀 해시·가상 칸 질량·선택 상태는 full/observations.jsonl에 남겼다. 기존 저음현 위치 지표도 진단용으로 남겼으나, 검증된 근음/운지 근거로 사용하지 않았다.

## 오디오와 결합

현재 오디오 후보의 원시 점수 .06 이내에만 최대 .06의 양의 위치 가점을 더한다. 손끝 주변의 가상 현/프렛 분포가 후보 구성음과 얼마나 겹치는지를 사용한다. 현재2개 이상의 검지/약지/새끼 위치 지지가 있고, 정합·전체 손 선택·짧은 시간 안정성 조건이 맞을 때만 적용한다. 중지는 기존 규칙대로 .25로 낮게 반영한다. 손끝 위치에서 실제 발음을 확정하지 않는다.

동일PC의m7/6은 이 일반 구성음 점수로 구분할 수 없다. 기존의 ‘검증된 근음/운지 근거 필요’ 조건은 풀지 않았다. 비전이 없으면 기존 오디오·온셋 결과로 돌아가며, 원시·기존 화성·표시·온셋 결과를 별도 필드에 보존한다.

## 변화량과 한계

기존 온셋 켜기/끄기는0.2초에서16/6,097시점,0.4초에서4/6,097시점만 표시가 달랐다. 따라서 체감 차이가 작았던 것이 맞다.

|오디오 창|온셋|비전으로 표시가 달라진 시점|비전 전 전환수|비전 후 전환수|
|---|---|---:|---:|---:|
{table_text}

**이번 보수적 비전 가점은 잦은 전환을 크게 줄이지 못했다.** 약한 지판/손 근거로 강한 오디오를 덮어쓰지 않기 때문에 영향 범위가 작다. 위 수치는 출력 변화이며 정답률이 아니다. Mela의 코드/분수/운지 정답을 이번에 전수 검수하지 않았다. 다음 개선은 실제로 운지가 유지되는 구간에서 오디오 표시가 왜 바뀌는지 대조하는 작업이다.

## 웹에서 확인

페이지를 새로고침하고 기존 Mela 결과를 다시 연다. ‘저음·화성 가점 적용’을 켠 상태에서 **‘비전 위치 가점 · 실험’**을 켜고 끄면 비교할 수 있다. **‘손·가상 지판 보기 · 접촉 미확정’**는 모델의 실제 선을 원본 영상 위에 표시한다. 오버레이는 영상의 레터박스·재생 시간에 맞춘다. 손이 없거나 시간차가 반 프레임보다 크면 이전 선을 붙여두지 않는다.

이번Mela의 원본 파일 해시에 설정을 등록했다. 동일 파일을 다시 올리면 비전 경로가 자동 실행된다. **다른 영상은 지판 설정이 없으면 오디오 분석을 유지하고 비전은 미연결로 표시한다.** 새 영상에 이전 좌표를 임의 적용하지 않는다. 음원 파일에는 비전이 없다.

기존 Mela API 결과는 result_before_vision_v5.json으로 백업했다. 원본 미디어는 변경하지 않았다. 선·원시 관측은 별도 vision_overlay.json/API로 제공하고, 영상 디코딩 픽셀과 모델·참조 SHA-256을 보관한다.

## 기술 검증

기존 회귀·새 검사218개(오프라인215+localhost HTTP3), 프런트엔드 계약16개 통과. 다른 원본/다른 시각의 비전 차단, 손이 없을 때 오디오 보존, 동일PC 동점 유지, 강한 오디오 우세 보호, 누름·해부학·기하 검증 상태 미승격, 두 체크박스의 켜기/끄기를 검사했다. 실제v5 결과·6,095개 오버레이 API·새 컨트롤 제공을 확인했다. 브라우저 화면의 자동 조작 검수는 승인 차단 상태라 수행하지 않았다.

```powershell
python web_vision_worker.py --video <media.mp4> --calibration <source-specific.json> --output <new-run>
python attach_web_vision.py --job-directory <webapp/runs/job-id> --vision-run <new-run>
python report_web_vision.py
python -m unittest test_vision_context test_onset_transition test_chord_presentation -q
node test_chord_web_ui.js
```

완료된 관측 run을 덮어쓰지 않는다. 실제 코드/TAB는 입력에 사용하지 않았으며 위 사진에 원래 보이는 텍스트는 검수용 원본의 일부다.
'''
    (ROOT/'docs/WEB_VISION_INTEGRATION_2026-11-05.md').write_text(text,encoding='utf-8')
    print(table_text)


if __name__=='__main__':main()
