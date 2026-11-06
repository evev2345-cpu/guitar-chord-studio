"""Actual cached observations, additive-score diagnostics and review report."""
import json
from pathlib import Path
import subprocess
import cv2
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from review_harmonic_context import ROOT, OUT


def main():
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    demo_id='1101a8a1324040b49e32d6a65fb1475f';mela_id='d861a160a92d498f87cd7f412a4dcb6e'
    demo=json.loads((OUT/(demo_id+'_result.json')).read_text(encoding='utf-8'))
    mela=json.loads((OUT/(mela_id+'_result.json')).read_text(encoding='utf-8'))
    row=demo['branches']['0.2'][480]
    original=cv2.imread(str(ROOT/'dataset/hand_analysis/runs/low_string_stability_20261105_v1/frames/f5135.png'))
    cap=cv2.VideoCapture(str(ROOT/'webapp/runs'/mela_id/'media.mp4'));cap.set(cv2.CAP_PROP_POS_MSEC,89250);ok,frame=cap.read();actual=cap.get(cv2.CAP_PROP_POS_MSEC)/1000;cap.release();assert ok
    example=mela['branches']['0.2'][round(actual*24)]
    fig,axes=plt.subplots(2,2,figsize=(14,10))
    axes[0,0].imshow(cv2.cvtColor(original,cv2.COLOR_BGR2RGB));axes[0,0].axis('off');axes[0,0].set_title('Original source214s / f5135; no labels fed to model')
    candidates=[c for c in row['context']['top3'] if c['quality'] in ('m7','6') and c['root_pc'] in (0,9)]
    names=[c['symbol'] for c in candidates];raw=[c['score'] for c in candidates];axes[1,0].bar(names,raw,label='Original audio score',color='#91aaa6');bottom=np.array(raw)
    for component,color in [('key','#72c7a5'),('progression','#c79842'),('bass','#3986a8')]:
        values=[c['bonus_components'][component] for c in candidates];axes[1,0].bar(names,values,bottom=bottom,label=component+' bonus',color=color);bottom+=values
    axes[1,0].set_ylim(.9,1.12);axes[1,0].set_title('Actual source214s: same audio scores; bonuses only');axes[1,0].legend(fontsize=8)
    axes[0,1].imshow(cv2.cvtColor(frame,cv2.COLOR_BGR2RGB));axes[0,1].axis('off');axes[0,1].set_title(f'Mela original playback ~{actual:.3f}s / slash proposal UNVERIFIED')
    axes[1,1].axis('off')
    old=example['display']['display_candidate'];shown=example['context']['display_candidates']
    text='Mela actual API output (not a browser screenshot)\n\n'+f"Before: {(old or {}).get('symbol','unknown')}\nAfter: {' | '.join(c['symbol'] for c in shown)}\n\n"+f"Bass model candidate: MIDI{example['context']['bass'].get('midi')}\nInstrument attribution: UNKNOWN\n\nNo slash-chord ground truth reviewed.\nBass spelling is a provisional observation."
    axes[1,1].text(.03,.93,text,va='top',fontsize=13,linespacing=1.65)
    fig.tight_layout();fig.savefig(OUT/'actual_before_after.png',dpi=125);plt.close(fig)
    audio=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
    sr,pcm=wavfile.read(audio);x=pcm.astype(float)
    if np.issubdtype(pcm.dtype,np.signedinteger):x/=2**(np.iinfo(pcm.dtype).bits-1)
    if x.ndim==2:x=x.mean(axis=1)
    x=x[19*sr:round(20.5*sr)]
    fig,axes=plt.subplots(2,1,figsize=(10,5));t=np.arange(len(x))/sr+213
    axes[0].plot(t[::20],x[::20],lw=.6);axes[0].set_ylabel('Wave amplitude')
    axes[1].specgram(x,NFFT=2048,Fs=sr,noverlap=1536,xextent=(213,214.5),cmap='magma');axes[1].set_ylim(65,2000);axes[1].set_ylabel('Hz');axes[1].set_xlabel('Original source time (s)')
    fig.suptitle('Existing guitar estimate: actual waveform/spectrum, source213-214.5s');fig.tight_layout();fig.savefig(OUT/'source_audio.png',dpi=125);plt.close(fig)
    listen=OUT/'source_213_214_5.mp3'
    if not listen.exists():subprocess.run(['ffmpeg','-v','error','-nostdin','-n','-ss','19','-i',str(audio),'-t','1.5','-c:a','libmp3lame','-b:a','128k',str(listen)],check=True)
    rel=OUT.relative_to(ROOT).as_posix();table=[]
    for e in summary['reference_evaluation']:
        for width,c in e['checks'].items():
            table.append(f"|{e['case']}|{width}초|{c['baseline_visible_single_correct']}/{c['points']}|{c['context_single_correct']}/{c['points']}|{c['context_contains']}/{c['points']}|")
    m=summary['jobs'][mela_id]['metrics']['0.2']
    text=f'''# 저음·키·진행 가점과 분수코드 웹 연결 — 2026-11-05

기존 음 후보·코드 채점을 보존한 채 **양의 가점만 추가**하는 경로를 만들었다. 분수코드는 코드 본체와 저음 후보를 따로 저장하고 표시한다. 근거가 충분한 동점에서는 가점 우선 후보를 보여주며, 약하면 복수 해석을 유지한다. 웹의 ‘저음·화성 가점 적용’을 끄면 종전 표시와 비교할 수 있다.

## 실제 비교

![원본과 실제 코드 후보·가점 비교 — 브라우저 화면 캡처가 아닌 검수 그림](../{rel}/actual_before_after.png)

원본214초의 실음 C6/Am7(카포1 운지 B6/G#m7)은 오디오가 동점이었다. 새 경로는 모델에서 지속된 MIDI45/A 저음을 관측했고 Am7을 가점 우선 표시했다. C6/A 해석은 다른 후보로 남는다. 이는 보편적인 화성 정답 증명이 아니라 저음·진행을 사용한 잠정 선호이며, 화면 정답을 추론에 입력하지 않았다.

Mela 약89초의 분수코드 예시는 기존 코드 본체와 저음 후보를 결합한 **미검수 출력**이다. 이 장면의 실제 정답 분수코드를 대조하지 않았으므로 맞았다고 주장하지 않는다. 원음 전체를 분석했기 때문에 저음이 기타인지 베이스 기타인지 구분하지 못한다.

![기존 기타 분리음의 실제 파형과 스펙트럼](../{rel}/source_audio.png)

![원본213~214.5초에 대응하는 기존 기타 추정음](../{rel}/source_213_214_5.mp3)

## 가점 규칙과 제한

- 오디오 1위에서 원시 점수 .06 이내인 후보에만 가점을 준다. 키 최대 .02, 앞뒤 진행 최대 .025, 지속 저음 최대 .05다. 어떤 항목도 감점하거나 키 밖 코드를 제거하지 않는다. 원시 후보와 점수·기존 표시 정리는 별도로 보존한다.
- 키는 전체 음 후보의 조성 음집합으로 추정한다. 상대 장·단조를 구분했다고 주장하지 않으며, 짧거나 모호하면 키 가점을 끈다. **이번 실제 음원들의 키 후보는 모두 모호해 키 가점이 활성화되지 않았다.** 조성이 바뀌는 곡에도 고정 키를 강제하지 않는다. 장기적으로 국소 조성 검증이 필요하다.
- 진행은 ±0.5/1초의 원시 후보만 참고하는 작은 가점이다. 앞뒤에서 갱신된 결과를 재귀적으로 정답처럼 사용하지 않는다. 관용 진행 목록으로 후보를 제한하지 않는다.
- 저음은 기존 MIDI38~59 범위에서 0.30초 창의 70% 이상, 평균 활성 .35 이상인 가장 낮은 모델 후보다. 모델 점수는 정답 확률이 아니다. D2 아래 베이스를 새로 추론하지 않으며, 잘못 지속된 저음·옥타브 오류를 완전히 배제하지 못한다.
- 루트와 저음이 다르면 C/E처럼 잠정 표기한다. 루트와 저음이 같으면 불필요한 /C는 붙이지 않는다. 카포 표기는 코드 루트와 분모를 모두 환산한다. 근거가 없으면 분모를 만들어 넣지 않는다.
- m7/6의 동일 구성음은 ‘루트 위치를 선호한다’는 제한된 저음 가점으로 비교한다. Am7과 C6/A를 음집합만으로 유일하게 판별할 수 있는 것은 아니다. 가점 차이가 .025보다 작으면 기존 동점 해석을 함께 남긴다.

## 검증 결과

기존 4개 웹 작업의 원시 top3·점수·상태·시간·기존 표시 정리가 새 결과와 동일함을 전수 확인했다. 기존 결과는 각 작업의 result_before_harmony_v2.json에 남기고 새 결과만 원래 API에 연결했다. Mela 0.2초의 {m['frames']}프레임 중 코드 본체 우선 표시가 달라진 곳은 {m['changed_root_quality']}프레임, 분수 표기가 나온 곳은 {m['slash_frames']}프레임이다. 이 수치는 출력 변화이며 개선된 정답 수가 아니다.

화면상 복수 후보를 포함한 **기존 웹 표시 방식과 동일한 기준**으로 이전 검수 지점을 비교했다. 후보 집합에 정답이 포함되는 것과 단독으로 정답을 표시하는 것은 별도로 집계했다. 검수 라벨은 추론 후 평가에만 사용했다.

|구간|창|기존 웹 단독 일치|새 웹 단독 일치|새 후보에 본체 정답 포함|
|---|---|---:|---:|---:|
'''+ '\n'.join(table)+f'''

기존 내부 표시 정리의 대표 1위만 세면 새16초/0.4초는3/4→단독1/4처럼 보이지만, 기존 웹도 Dm7/F6 동점을 함께 표시하던 두 지점이다. 새 표시에서도 이 두 해석을 유지한다. 세부 기록은 summary.json에 남겼다. **분수의 분모 정답은 이 검수 라벨에 없으므로 위 표는 코드 본체(root/quality) 평가이며 분수코드 정확도가 아니다.** 이번에 전체 정확도가 올랐다고 주장하지 않는다.

전체 회귀·신규 **196개 테스트**, 프런트엔드 표기 계약 **9개**가 통과했다. 지속 저음과 순간 저음 구분, 무음·가장자리 보류, 가점만 적용, 키 밖 후보 보존, 강한 오디오 우세 보호, 동일PC 동점, C/E→카포1 B/D# 환산을 검사했다.

```powershell
python review_harmonic_context.py
python review_harmonic_context.py --apply
python report_harmonic_context.py
python -m unittest test_harmonic_context test_chord_web -q
node test_chord_web_ui.js
```

웹 서버를 새 코드로 다시 시작했다. 기존 결과를 열고 새로고침하면 가점 켜기/끄기를 비교할 수 있다. 브라우저 자동 접근 승인 차단으로 실제 화면 조작 검수는 하지 않았으며, 이 보고서의 그림은 원본과 실제 API 결과로 생성했다. 다음 검수는 Mela의 실제 분수코드 시점을 사용자가 지정하거나 원본 TAB와 대조해 분모까지 평가하는 것이다.
'''
    (ROOT/'docs/HARMONIC_CONTEXT_2026-11-05.md').write_text(text,encoding='utf-8')
    print('\n'.join(table))


if __name__=='__main__':main()
