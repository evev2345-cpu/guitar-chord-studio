"""Actual Mela display before/after, source unchanged above appended panel."""
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from review_chord_presentation import ROOT, OUT

SHARP=['C','C#','D','D#','E','F','F#','G','G#','A','A#','B']


def label(cs,capo=0):
    out=[]
    for c in cs:
        base=c.get('base_symbol',c['symbol'].split('/')[0]);pc=c.get('bass_pc')
        symbol=SHARP[(c['root_pc']-capo)%12]+base[len(SHARP[c['root_pc']]):]
        if pc is not None and pc!=c['root_pc']:symbol+='/'+SHARP[(pc-capo)%12]
        out.append(symbol)
    return ' · '.join(out) if out else '보류'


def main():
    job='d861a160a92d498f87cd7f412a4dcb6e';data=json.loads((OUT/(job+'_result.json')).read_text(encoding='utf-8'))
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'));stats=summary[job]['branches']['0.2']
    source=ROOT/'webapp/runs'/job/'media.mp4';clip=OUT/'mela_88_98_before_after.mp4'
    rows=data['branches']['0.2'];font=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',29);small=ImageFont.truetype('C:/Windows/Fonts/malgun.ttf',18)
    cap=cv2.VideoCapture(str(source));cap.set(cv2.CAP_PROP_POS_FRAMES,88*24)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-nostdin','-n','-f','rawvideo','-pixel_format','bgr24','-video_size','1280x900','-framerate','24','-i','pipe:0','-ss','88','-i',str(source),'-map','0:v','-map','1:a','-t','10','-c:v','libx264','-preset','fast','-crf','21','-pix_fmt','yuv420p','-c:a','aac','-movflags','+faststart',str(clip)]
    process=None
    if not clip.exists():process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    for i in range(240):
        ok,original=cap.read();assert ok;t=88+i/24;row=rows[88*24+i]
        panel=Image.new('RGB',(1280,180),(18,26,36));draw=ImageDraw.Draw(panel)
        draw.text((18,8),f'Mela · 재생 {t:.3f}초 · 같은 소리 / 같은 음 후보 / 표시 정책만 비교',font=small,fill='#c3cddd')
        for x,title,cs,color in [(18,'수정 전',row['context']['display_candidates'],'#e7b676'),(658,'수정 후',row['presentation']['display_candidates'],'#6ce7c6')]:
            draw.text((x,38),title,font=small,fill=color);draw.text((x,65),'실음 '+label(cs),font=font,fill='white');draw.text((x,110),'카포1 운지 '+label(cs,1),font=small,fill='#c3cddd')
        draw.text((18,148),'약한 저음은 분모로 표시하지 않음 · 강한 실제 코드 전환에는 일괄 대기시간을 붙이지 않음',font=small,fill='#a4b4c7')
        combined=np.vstack([original,cv2.cvtColor(np.asarray(panel),cv2.COLOR_RGB2BGR)])
        if i==30:cv2.imwrite(str(OUT/'mela_before_after.png'),combined)
        if process:process.stdin.write(combined.tobytes())
    cap.release()
    if process:
        process.stdin.close();error=process.stderr.read().decode();code=process.wait()
        if code:raise RuntimeError(error)
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,key,title in zip(axes,['display_changes','short_display_runs_under_0_2s','slash_frames'],['Main label changes','Runs shorter than0.2s','Frames with slash spelling']):
        values=[stats['before'][key],stats['after'][key]];ax.bar(['Before','After'],values,color=['#c39765','#429d89']);ax.set_title(title)
        for i,value in enumerate(values):ax.text(i,value+max(values)*.02,str(value),ha='center')
        ax.set_ylim(0,max(values)*1.2)
    fig.suptitle('Mela 254s: display variation only; not chord accuracy');fig.tight_layout();fig.savefig(OUT/'metrics.png',dpi=130);plt.close(fig)
    rel=OUT.relative_to(ROOT).as_posix()
    text=f'''# 분수코드 과다 표시와 잦은 전환 수정 — 2026-11-05

사용자 피드백: 분수코드를 너무 자주 가정하고 코드 표시가 자주 바뀐다. 원인은 낮게 검출된 음을 곧바로 분모에 붙이는 것과, 동점 후보 목록의 변화·짧은 약한 후보를 그대로 메인에 표시하는 데 있었다.

## 실제 영상 비교

![Mela 재생89.25초: 원본 보존·같은 음원과 후보의 표시 전후](../{rel}/mela_before_after.png)

[Mela 재생88~98초 실제 소리 포함 비교 영상](../{rel}/mela_88_98_before_after.mp4). 위 원본은 그대로이고 아래 왼쪽은 이전 표시, 오른쪽은 새 표시다. 코드 분석을 다시 학습하거나 원음을 바꾸지 않았다. 카포1 표기는 원본 화면의 카포 안내와 구분해서 함께 표시했다. 화면 코드/TAB는 이번 표시 알고리즘에 입력하지 않았다.

## 변경 규칙

- 분모는 0.5초 창에서 같은 저음 후보가 90% 이상 유지되고 모델 활성 중앙값 .65 이상이며, 코드 구성음에 속하고 해석이 하나일 때만 잠정 표기한다. 짧은 0.35초 미만 분수 표기 섬도 제거한다. 임계값은 경험적 표시 기준이지 정답 확률이 아니다.
- 약한 저음·비구성음 페달·모호한 해석은 메인 분모에 붙이지 않는다. **일부 실제 빠른 분수 진행이나 비구성음 베이스도 보류될 수 있다.** 후보와 원래 저음은 context/presentation.observed_bass에 보존하고 화면에는 별도 ‘실음 저음 후보’로 남긴다.
- 현재 동점 후보 안에 직전 단독 해석이 있으면 그 해석을 표시하되 ‘동점 · 직전 해석 유지’로 구분한다. 다른 해석은 상세 후보에 남는다. 동점 해석을 확정했다고 주장하지 않는다.
- 0.25초 이하의 A-B-A 튐과 0.18초 미만 약한 변화를 정리한다. 이전 해석이 현재 원시 후보에서 .08 점수차 이내로 계속 지지될 때만 유지한다. 강한 새 음 근거(.12 이상 원시 우세), 이전 후보가 사라진 경우, 지속된 실제 전환은 유지한다. 모든 전환에 고정 대기시간을 붙이지 않는다.
- 원시 top3·화성 가점 결과·기존 표시 정리는 수정하지 않았다. 새 presentation 계층만 추가했다. 가점을 끄면 종전 오디오 경로를 비교할 수 있다.

## Mela 전체 결과 — 0.2초 창

![실제 표시 전환·짧은 구간·분수 표기 수](../{rel}/metrics.png)

|지표|수정 전|수정 후|
|---|---:|---:|
|메인 코드 표기 전환|{stats['before']['display_changes']}|{stats['after']['display_changes']}|
|코드 본체 후보집합 전환|{stats['before']['base_changes']}|{stats['after']['base_changes']}|
|0.2초 미만 표시 구간|{stats['before']['short_display_runs_under_0_2s']}|{stats['after']['short_display_runs_under_0_2s']}|
|분수 표기 프레임|{stats['before']['slash_frames']}|{stats['after']['slash_frames']}|

표기 전환은 인접 24Hz 프레임의 후보집합·실제 표시 분모 변화를 센 값이며, 동점 목록의 순서나 ‘분모 없음/근음과 같은 분모’의 메타데이터 차이는 전환으로 세지 않는다. 기존 보고 과정에서 사용했던 메타데이터 단순 비교 수치와 직접 혼용하지 않는다. 실제 해석의 집합을 기준으로 동일하게 다시 계산했다.

이 영상의 기존 분수 후보는 새 기준에서 모두 보류됐다. 기능을 전역으로 끈 것은 아니며, 강하고 지속된 C/E 합성 입력은 분수 표기를 유지하는 테스트를 통과했다. 그렇다고 실제 분수코드 검출률이 검증됐다는 뜻은 아니다. **표시 전환 약44% 감소는 정확도 상승이나 전환 문제 완전 해결을 뜻하지 않는다.** 여전히 짧은 변동이 남고, 실제 빠른 약한 코드 전환이 일부 억제될 수 있다.

## 검증·적용

4개 기존 웹 작업의 원시·화성 관측을 그대로 보존했는지 전수 대조했다. API 결과를 갱신하기 전 result_before_presentation_v3.json으로 백업했다. 214초 G#m7 우선 표시는 유지되며, 기존9개 검수 지점의0.2초 코드 본체 일치도7/9를 유지했다. Mela 전체 코드/분모 정답은 미검수이므로 이 영상의 정확도를 계산하지 않았다.

전체 **205개 테스트**, 프런트엔드 계약 **11개**를 통과했다. 짧은 지지된 튐 제거·강한 짧은 전환 유지·이전 해석의 현재 근거 필요·실제 지속 전환의 시작시각 보존·순간/약한 저음의 분모 보류·강한 지속 전위 유지·무음에 코드 생성 금지를 검사했다.

```powershell
python review_chord_presentation.py
python review_chord_presentation.py --apply
python report_chord_presentation.py
python -m unittest test_chord_presentation test_harmonic_context test_chord_web -q
node test_chord_web_ui.js
```

웹 서버에 새 정책을 연결했다. 페이지를 새로고침하고 기존 Mela 결과를 다시 열면 재업로드 없이 비교할 수 있다. 브라우저 자동 접근은 승인 차단 상태여서 실제 UI 렌더링 검수는 하지 않았다. 위 영상과 사진은 실제 원본·실제 API 후보를 코드로 합성한 검수 자료이며 브라우저 화면 캡처는 아니다.

다음 확인은 실제 영상 재생으로 과한 변화가 남는 구간과 빠른 실제 전환을 놓친 구간을 분리 검수하는 것이다. 새 정책은 더 적은 표시를 선택한 것이며, 낮은 근거의 저음을 새 정답으로 승격하지 않는다.
'''
    (ROOT/'docs/CHORD_PRESENTATION_2026-11-05.md').write_text(text,encoding='utf-8')
    print('Saved actual comparison video, preview, metrics and report')


if __name__=='__main__':main()
