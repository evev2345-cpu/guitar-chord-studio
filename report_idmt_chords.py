"""Reproduce plots, listening examples, and the cross-dataset review."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from idmt_chords_benchmark import ROOT,OUT,pcm_float

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    idmt=read(OUT/'summary.json');gs=read(ROOT/'dataset/integration_review/runs/chord_scores_guitarset_20261105_v1/summary.json')['primary']['variants']
    names=['legacy','cosine','cosine_context'];assets=OUT/'report';assets.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,3,figsize=(15,4.3))
    for ax,domain in zip(axes[:2],['GuitarSet nominal','IDMT guitar']):
        vals=[100*gs[n]['nominal']['top1'] if domain.startswith('GuitarSet') else 100*idmt['guitar'][n]['counts']['top1']/1638 for n in names]
        bars=ax.bar(['Legacy','Cosine','+ context'],vals,color=['#777777','#297fb8','#169c75']);ax.bar_label(bars,fmt='%.2f%%');ax.set_ylim(0,60);ax.set_title(domain+' / exact top1');ax.set_ylabel('Accuracy (%)')
    qs=['maj','min','7','maj7','min7','hdim7','5'];x=np.arange(len(qs))
    for i,n in enumerate(names):
        vals=[100*idmt['guitar'][n]['per_quality'][q]['top1']/234 for q in qs]
        axes[2].bar(x+(i-1)*.25,vals,.25,label=n)
    axes[2].set_xticks(x,qs,rotation=35);axes[2].set_title('IDMT guitar / 234 examples per quality');axes[2].legend(fontsize=7);axes[2].set_ylim(0,100)
    fig.suptitle('Fixed DSP scoring: real-performance gain does not generalize to synthetic timbres')
    fig.tight_layout();fig.savefig(assets/'comparison.png',dpi=150);plt.close(fig)
    rec=read(OUT/'ableton_live_guitar_Campfire.json')
    cases=[next(r for r in rec['rows'] if not r['variants']['legacy']['top1'] and r['variants']['cosine_context']['top1']),
           next(r for r in rec['rows'] if r['variants']['legacy']['top1'] and not r['variants']['cosine_context']['top1'])]
    rate,a=wavfile.read(rec['file']);fig,axes=plt.subplots(2,2,figsize=(12,6));captions=[]
    for i,row in enumerate(cases):
        t=row['time_s'];clip=pcm_float(a[round((t-1)*rate):round((t+1)*rate)])
        wavfile.write(assets/f'case_{i+1}.wav',rate,clip.astype(np.float32))
        axes[i,0].plot(np.arange(len(clip))/rate+t-1,clip,lw=.5);axes[i,0].axvline(t,color='red',ls='--');axes[i,0].set_title(f"Campfire / {t:.1f}s / annotation {row['label']}")
        segment=clip[round(rate)-4096:round(rate)+4096];mag=np.abs(np.fft.rfft(segment*np.hanning(8192)));freq=np.fft.rfftfreq(8192,1/rate)
        axes[i,1].plot(freq,20*np.log10(np.maximum(mag,1e-8)));axes[i,1].set_xlim(65,1600);axes[i,1].set_xlabel('Frequency (Hz)');axes[i,1].set_ylabel('Magnitude (dB, uncalibrated)')
        captions.append(f"예시{i+1}: Campfire {t:.1f}초, 주석 `{row['label']}`. 기존 `{row['variants']['legacy']['predictions'][0]}`, 문맥 정규화 `{row['variants']['cosine_context']['predictions'][0]}`. 원본 2초: ![원음](../{assets.relative_to(ROOT).as_posix()}/case_{i+1}.wav)")
    fig.tight_layout();fig.savefig(assets/'examples.png',dpi=140);plt.close(fig)
    rows=[]
    for n in names:
        g=gs[n];c=idmt['guitar'][n]['counts']
        rows.append(f"|{n}|{100*g['nominal']['top1']:.2f}%|{100*g['performed']['top1']:.2f}%|{100*c['top1']/c['evaluated']:.2f}%|{100*c['top3']/c['evaluated']:.2f}%|")
    inst=[]
    for f in sorted(OUT.glob('*.json')):
        if f.name in ('config.json','summary.json'):continue
        r=read(f)
        if r['domain']!='guitar':continue
        vals=[sum(row['variants'][n]['top1'] for row in r['rows'])/len(r['rows'])*100 for n in names]
        inst.append('|'+f.stem+'|'+'|'.join(f'{v:.2f}%' for v in vals)+'|')
    text='''# IDMT 코드 데이터 검증과 채점 개선 비교 — 2026-11-05

IDMT-SMT-Chords 다운로드·검증·전체 7,398구간 평가를 완료했다. 새 정규화는 실제 GuitarSet에서 개선됐지만 IDMT 기타에서 퇴보했다. 운영 기본 채점은 변경하지 않았고 새 방식은 평가 전용이다. 지금은 작은 모델 학습보다 배음과 실제 구성음을 분리하는 특징 개선을 먼저 할 근거가 확보됐다.

## 데이터와 재현

공식 [Zenodo 자료](https://zenodo.org/records/7544213)의 ZIP 1,306,388,518바이트, MD5 `af2239fcc468ce653c9d9350ceaa3eb5` 일치, CRC 24개 항목 검사 후 추출했다. SHA256 `ac0195c989485828ae9b344dcd527e49698fb1fcba9a6778d3c0068b4c06afad`. 원본과 이전 실험 결과는 보존했다. 다운로드 근거는 `IDMT_SMT_Chords/download_manifest.json`.

6개 기타 음색 × 273구간 = 1,638개, 10개 비기타 음색 × 576구간 = 5,760개. 모두 44.1kHz 모노이며 정수 PCM과 실수 PCM을 구분해 변환했다. MIDI를 소프트웨어 악기로 렌더링한 합성 음원으로 실제 연주 영상 데이터가 아니다. 학습·파라미터 피팅은 하지 않았다.

기존 180개 화음 사전과 FFT 피크 기반 크로마를 유지했다. cosine은 구성음 수로 정규화하며 활성 피치클래스 최소 조건도 3개에서 2개로 바뀐다. 따라서 순수 정규화 단독 효과라고 해석할 수 없다. context는 중심 ±0.1초의 세 점수를 평균하며 미래 오디오가 필요하다. 확률로 보정된 신뢰도는 아니다.

IDMT는 각 2초 구간의 중심 한 곳을 채점했다. 각 중심 ±0.1초에 실제 8192샘플 창을 사용했으며 참조 코드명이 예측 함수에 들어가지 않는다. 주석 시각으로 평가 위치를 선택하므로 전환·온셋 성능은 측정하지 않는다. 후보 피크 범위는 65~1600Hz, 파형 대역 컷은 하지 않았다. GuitarSet은 기존 D2~E6 파형 컷, 100ms 표본을 유지했다. 데이터 간 절대 성적은 직접 비교하지 않고 각 데이터 안에서 방식의 변화를 비교한다.

## 결과

GuitarSet 180파일에서 기존 cut 점수와 파일별 집계가 정확히 재현됐다. 주 성적은 알려진 시간 오류 2파일을 뺀 178파일이다. 상세 수행 주석과 기본 주석은 서로 다른 정답층이다.

|방식|GuitarSet 기본 top1|GuitarSet 상세 전체 top1|IDMT 기타 top1|IDMT 기타 top3|
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![실제 성적과 코드 종류별 비교](../{assets.relative_to(ROOT).as_posix()}/comparison.png)

GuitarSet 기본 도미넌트7은 기존 928/4,230=21.94%에서 context 643/4,230=15.20%로 하락했고, m7b5도 15.53%에서 12.58%로 하락했다. IDMT 기타 도미넌트7은 196/234=83.76%에서 103/234=44.02%, maj7은 85.04%에서 52.99%로 떨어졌다. 전체 평균 개선만 보고 교체하면 실제 7음을 지우는 오류가 커질 수 있다.

|기타 음색|기존|cosine|context|
|---|---:|---:|---:|
'''+ '\n'.join(inst)+f'''

기존 튜토리얼 안정구간 9개를 동일 100ms 표본 방식으로 재생한 비교에서는 top1이 기존 3/9, cosine 4/9, context 6/9였다. 이미 확인해 온 작은 개발 표본이며 독립 시험이 아니다. 이전 0.4초 평균 방식과 직접 비교하지 않는다.

## 실제 원음과 실패 사례

![원본 파형과 중심 창 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/examples.png)

'''+ '\n\n'.join(captions)+'''

원본 파형의 빨간 점선은 평가 시점이다. 스펙트럼 피크는 관측이며 실제 기본음 정답이 아니다. 사례는 개선과 퇴보를 각각 하나 선택한 설명용 자료이며 전체 비율은 위 표를 따른다.

## 주석 검사에서 드러난 한계

비기타 자료에는 `C:min/3`, `C:min7/7`, `C:hdim7/5`처럼 표준 Harte 도수로 읽으면 해당 화음 밖의 베이스 음이 추가되는 표기가 있다. 원본을 임의 수정하지 않고 문자 그대로 해석했다. 그 결과 1,680/5,760개가 현 사전 밖이며 전체 분모에 남았다. 비기타 성적은 이 주석 문제를 포함한 진단값이고 정정된 정확도라고 발표하지 않는다. 기타 1,638개는 모두 사전 내이며 위 주요 결론에는 이 문제가 없다. 전위 자체의 정확도는 채점하지 않았다.

첫 실행 v1은 모든 라벨이 사전 내일 것이라는 검증에서 실패했고 결과를 보존했다. 원인을 조사한 뒤 v2에서 OOV를 명시적으로 허용하고 기타 전수 검사 조건을 유지해 다시 완료했다.

## 검증과 다음 단계

`python idmt_chords_benchmark.py` → v2 전체 16파일·7,398구간 완료. `python report_idmt_chords.py` → 이 문서·성적 그림·원음 두 개 재생성. 원시 파일별 결과와 설정은 `dataset/integration_review/runs/idmt_chords_scores_20261105_v2`에 있다.

122개 회귀/신규 단위 테스트 통과. 명령: `python -m unittest test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q`.

다음은 배음 억제 또는 기본음 후보 추출을 독립 실험으로 추가하고, triad/7음의 누락·과검출을 동시에 비교하는 것이다. 학습을 진행한다면 먼저 사용 조건과 연주자 단위 분할을 확정하고 GuitarSet 및 별도 튜토리얼을 분리해야 한다. IDMT-SMT-Guitar 추가 다운로드는 이번에는 하지 않았다. 실제 연주 검증에는 이미 확보한 GuitarSet이 있고, 현 병목인 코드 종류·음색 일반화는 이번 Chords로 확인됐다. 손·지판·접촉 판정 및 비전 가중치는 변경하지 않았다.
'''
    (ROOT/'docs/IDMT_CHORDS_SCORING_REVIEW_2026-11-05.md').write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8')
    marker='후속 야간 작업 완료:'
    if marker not in old:
        head,rest=old.split('\n',1)
        log.write_text(head+'\n\n'+marker+' IDMT-SMT-Chords 1.3GB 다운로드·MD5/CRC 검증·7,398구간 평가를 완료했다. 고정 정규화+문맥 채점은 GuitarSet 기본 코드 12.02→19.93%, 상세 전체 13.59→24.61%였으나 IDMT 기타는 44.38→36.08%로 퇴보하고 7화음 손실이 확인됐다. 기본 채점은 유지했다. 122개 테스트 통과. [전체 보고서와 실제 원음/성적 그림](IDMT_CHORDS_SCORING_REVIEW_2026-11-05.md).\n'+rest,encoding='utf-8')
    print('Report generated',flush=True)

if __name__=='__main__':main()
