"""Report the fixed-cut, fixed-scorer experiment with actual audio/plots."""
import argparse
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from benchmark_cut_audio import ROOT,NAMES,BASE
from idmt_chords_benchmark import pcm_float
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();out=a.run.resolve();read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    summary=read(out/'summary.json');tutorial=read(out/'tutorial.json');assets=out/'report';assets.mkdir(exist_ok=True)
    metric=lambda c,key='top1':100*c.get(key,0)/max(1,c['evaluated'])
    titles=['Existing peaks','Harmonic fit','Harmonic + peak support'];fig,axes=plt.subplots(1,3,figsize=(14,4))
    for ax,domain,layer in zip(axes,['guitarset','guitarset','idmt'],['nominal','performed','nominal']):
        vals=[metric(summary[domain]['branches'][n][layer]['counts']) for n in NAMES];bars=ax.bar(titles,vals,color=['#777777','#2b8cbe','#ec9a38']);ax.bar_label(bars,fmt='%.2f%%',fontsize=9);ax.set_ylim(0,70);ax.tick_params(axis='x',rotation=20);ax.set_title(domain+' / '+layer);ax.set_ylabel('Exact chord top1 (%)')
    fig.suptitle('All branches: D2-E6 waveform cut + unchanged existing chord scorer');fig.tight_layout();fig.savefig(assets/'accuracy.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(12,4));qs=['major','minor','7','maj7','m7','m7b5']
    for ax,domain,layer in zip(axes,['guitarset','idmt'],['performed','nominal']):
        for j,n in enumerate(NAMES):
            vals=[metric(summary[domain]['branches'][n][layer]['per_quality'][q]) for q in qs];ax.bar(np.arange(len(qs))+(j-1)*.25,vals,.25,label=titles[j])
        ax.set_xticks(np.arange(len(qs)),qs);ax.set_title(domain+' / '+layer);ax.set_ylim(0,100);ax.legend(fontsize=8)
    fig.tight_layout();fig.savefig(assets/'qualities.png',dpi=145);plt.close(fig)
    rate,raw=wavfile.read(tutorial['audio']);x=pcm_float(raw).mean(axis=1);cut=band_cut(x,rate);fig,axes=plt.subplots(2,2,figsize=(12,6))
    for i,(name,s) in enumerate([('Original guitar estimate',x),('D2-E6 waveform cut',cut)]):
        clip=s[4*rate:8*rate];axes[i,0].plot(198+np.arange(len(clip))/rate,clip,lw=.4);axes[i,0].set_title(name+' / 198-202s')
        win=s[5*rate-4096:5*rate+4096];freq=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));axes[i,1].plot(freq,20*np.log10(np.maximum(mag,1e-9)));axes[i,1].axvspan(LOW_HZ,HIGH_HZ,color='green',alpha=.12);axes[i,1].set_xlim(0,6000);axes[i,1].set_ylim(-100,50);axes[i,1].set_xlabel('Frequency (Hz)');axes[i,1].set_ylabel('Magnitude (dB, uncalibrated)');axes[i,1].set_title('199s center window; green = retained band')
    fig.tight_layout();fig.savefig(assets/'audio_comparison.png',dpi=145);plt.close(fig)
    rows=[];qrows=[];pcrows=[]
    for n,title in zip(NAMES,titles):
        g=summary['guitarset']['branches'][n];d=summary['idmt']['branches'][n]['nominal'];t=tutorial['summary'][n]
        rows.append(f"|{title}|{metric(g['nominal']['counts']):.2f}%|{metric(g['performed']['counts']):.2f}%|{metric(g['performed']['counts'],'top3'):.2f}%|{metric(d['counts']):.2f}%|{t['exact_top1']}/9|")
        pc=g['note_pc'];pcrows.append('|'+title+'|'+'|'.join(f'{100*pc[k]:.2f}%' for k in ['precision','recall','f1'])+'|')
    for q in qs:
        cells=[]
        for domain,layer in [('guitarset','performed'),('idmt','nominal')]:
            for n in NAMES:
                c=summary[domain]['branches'][n][layer]['per_quality'][q];cells.append(f"{metric(c):.2f}% ({c['top1']}/{c['evaluated']})")
        qrows.append('|'+q+'|'+'|'.join(cells)+'|')
    paired={n:dict(wins=0,losses=0) for n in NAMES[1:]};verified=0
    from guitarset_benchmark import KNOWN_TIMING
    for f in sorted((out/'records').glob('*.json')):
        r=read(f);old=read(BASE/'records'/f.name);assert r['times']==old['times'] and r['audio_sha256']==old['sha256'];verified+=1
        if r['domain']!='guitarset' or r['id'] in KNOWN_TIMING:continue
        for n in NAMES[1:]:
            frames=r['branches'][n]['performed']['frames'];base=r['branches']['peak']['performed']['frames'];assert len(frames)==len(base)
            for b,new in zip(base,frames):
                assert b['time_s']==new['time_s'] and b['reference']==new['reference']
                paired[n]['wins']+=int(new['correct_top1'] and not b['correct_top1']);paired[n]['losses']+=int(b['correct_top1'] and not new['correct_top1'])
    raw_summary=read(BASE/'summary.json');raw_g=raw_summary['guitarset']['branches']['peak_legacy']['performed']['counts'];cut_g=summary['guitarset']['branches']['peak']['performed']['counts']
    audit=dict(verified_source_grid_files=verified,paired_guitarset_performed=paired,
               note='Same existing scorer on all cut branches. Model and observations both band-limited; no training or threshold search.')
    (out/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    g=summary['guitarset']['branches'];d=summary['idmt']['branches'];seventh=lambda domain,n:100*summary[domain]['branches'][n]['performed' if domain=='guitarset' else 'nominal']['seventh_diagnosis']['correct']/summary[domain]['branches'][n]['performed' if domain=='guitarset' else 'nominal']['seventh_diagnosis']['evaluated']
    text=f'''# D2~E6 컷 유지: 음 추출 방식만 바꾼 비교 — 2026-11-05

사용자가 요청한 현재 단계의 오디오 실험을 완료했다. **주파수 컷과 기존 코드 채점을 고정하고 음 추출만 비교했다.** 학습 모델은 만들지 않았고 손·지판·화성 채점·비전 가중치는 변경하지 않았다. 아래 수치는 이번 동일 조건 비교 안에서 해석한다.

## 고정 조건과 세 가지 방식

원음 → 전체 파일 FFT로D2({LOW_HZ:.3f}Hz)~E6({HIGH_HZ:.3f}Hz) 밖 제거 → 동일8192샘플 창 → 음 추출 → 기존 coverage 채점. 세 방식은 **기존 피크**, **배음 모델**, **배음 모델+실제 피크 확인**이다. ‘기존 채점’은 코드 점수 공식이고 주파수 컷 여부와 별개다. 이번에는 전부 컷을 사용했다. 시간 평균·cosine 점수·코드별 방식 전환·문턱 탐색은 사용하지 않았다.

배음 모델은 기존1/h·1~8차 배음 템플릿을 쓰되 **관측 스펙트럼과 모델 둘 다 컷 안의 주파수만** 사용한다. 제거한 높은 배음을 실제 부재로 오해하지 않도록 했다. 기본음 후보도D2~E6이다. 피크 확인은 기존 최대 스펙트럼12% 조건과 컷 대역을 사용한다. 모델 자체의 음색 가정은 여전히 제한적이다.

GuitarSet comp180파일·IDMT 기타6음색을 실행했다. 주 결과는 알려진 시간 오류2개를 뺀178파일, 안정창4,886개다. IDMT는1,638구간이다. GuitarSet은0.5초부터1초 간격, IDMT는구간중심으로 이전 실험과 같은 시점을 유지했다. 주석 경계의 창은 제외했다. 상세 수행 주석의 사전 밖 코드도 분모에 유지했다.186파일의 SHA256·시각 그리드를 이전 입력과 대조했다. 새 피크 추출이 같은 컷 창의 기존 추출기와 정확히 같은지 단위 테스트했다.

## 결과

|음 추출|GuitarSet 기본 top1|상세 전체 top1|상세 전체 top3|IDMT 기타 top1|튜토리얼 top1|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![같은 컷·같은 채점 비교](../{assets.relative_to(ROOT).as_posix()}/accuracy.png)

동일 시점의 **컷 미사용+기존 피크+기존 채점**은 GuitarSet 상세 전체{metric(raw_g):.2f}%, 이번 **컷 사용+기존 피크+기존 채점**은{metric(cut_g):.2f}%다. 이 두 값은 컷 효과 비교용이며, 위 세 방식의 비교에는 모두 컷을 적용했다. 앞선100ms 표본·시간 평균 실험과는 표본이 다르다.

|코드 종류|실제 기존 피크|실제 배음|실제 배음+확인|IDMT 기존 피크|IDMT 배음|IDMT 배음+확인|
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(qrows)+f'''

![일반 코드와7화음 손익](../{assets.relative_to(ROOT).as_posix()}/qualities.png)

7화음 묶음(7·maj7·m7·m7b5)의 실제 상세 정답률은 기존{seventh('guitarset','peak'):.2f}%, 배음{seventh('guitarset','harmonic'):.2f}%, 피크 확인 추가{seventh('guitarset','supported'):.2f}%다. IDMT는 각각{seventh('idmt','peak'):.2f}%, {seventh('idmt','harmonic'):.2f}%, {seventh('idmt','supported'):.2f}%다. 전체 개선 여부와 종류별 퇴보 여부를 함께 판단해야 한다.

실제 상세 정답 기준, 배음 모델은 기존 오답을 정답으로 바꾼{paired['harmonic']['wins']}창 / 기존 정답을 오답으로 바꾼{paired['harmonic']['losses']}창, 피크 확인 추가는 각각{paired['supported']['wins']}창 / {paired['supported']['losses']}창이었다. 시점들은 서로 상관된 표본이며 통계적 독립 사례 수로 해석하지 않는다.

## 실제 음 후보 검증

GuitarSet6현 note_midi 주석의 활성 피치클래스와5,421창(무음 포함)에서 대조했다. 활성 문턱은각창최대salience10%다. 음높이 옥타브·현·온셋 정확도가 아니다.

|음 추출|정밀도|재현율|F1|
|---|---:|---:|---:|
'''+ '\n'.join(pcrows)+f'''

## 원음·컷 소리와 실제 영상

![198~202초 파형과199초 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/audio_comparison.png)

원본 기타 추정음: ![원음](../{out.relative_to(ROOT).as_posix()}/tutorial_raw_198_202.wav)

D2~E6 컷: ![컷 음원](../{out.relative_to(ROOT).as_posix()}/tutorial_cut_198_202.wav)

세 추출기는 모두 같은 컷 소리를 분석한다. 음 추출 방식에 따라 소리를 새로 합성하거나 볼륨을 보정하지 않았다. 초록 영역은 유지 대역이다. 창을 씌우면 경계 밖에 스펙트럼 누출이 생길 수 있어 그래프의 모든 바깥 성분이 정확히0은 아니다. 분석은 대역 안만 사용한다.

![195초 원본 영상 — 기존 참조 자료](../{Path(tutorial['rows'][0]['reference']['image']).relative_to(ROOT).as_posix()})

튜토리얼9곳은 기존 안정구간의 화면 코드·TAB·운지 대조 참조이며 독립 청음 전사나 두 번째 사람의 검증은 아니다. 정확한 영상PTS의 중심창을 사용했고Capo.1을 반영했다. 작은 개발 표본으로 모델 채택을 결정하지 않는다. 개별 후보·보류와 참조는tutorial.json에 보관했다.

## 검증과 결정

133개 테스트 통과. 무음·잘못된 입력·실제7음 합성·기존 추출 동일성·모델대역 제한 등을 확인했고, 합성 단위 테스트 결과를 실제 정확도로 대신하지 않았다. 원본 데이터와 과거 실험 결과는 보존했다. 운영 기본은 변경하지 않았다.

이번 결과로 기본 교체는 보류한다. 배음 분석은 실제7화음 묶음을28.57→32.80%로 높이지만 전체상세13.69→12.71%로 퇴보한다. 피크 확인은 전체상세를15.88%로 높이지만7화음 묶음은22.17%로 낮추고 상위3개 포함률도29.53→25.64%로 낮춘다. m7은 두 개선 후보 모두 기존보다 낮다. 현재 목표인 ‘일반 코드 유지와7화음 개선’을 동시에 충족하지 못했고, 튜토리얼은 모두3/9로 같았다. 다음은 고정된 이 평가기에 기존 사전학습 오디오 모델 하나를 연결해 비교하는 것이다. 자체 소규모 모델 학습을 바로 시작하지는 않는다.

재현:

```powershell
python benchmark_cut_audio.py --output dataset/integration_review/runs/cut_audio_features_20261105_v1
python report_cut_audio.py --run dataset/integration_review/runs/cut_audio_features_20261105_v1
python -m unittest test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료된 출력은 덮어쓰지 않으므로 재실행은 새출력경로를 사용한다. 설정·소스해시는config.json, 원음·주석해시는records, 입력대조·정오답교체수는audit.json에 보관했다. 9·11·13텐션 전반은 아직 검증하지 않았다. 기존 도구로 비교를 먼저 마친 뒤, 모든 종류에서 균형 있는 개선이 없으면 추가 규칙을 계속 쌓기보다 기존 사전학습 오디오 모델을 같은 평가기에 연결하는 것이 다음 단계다. 소규모 자체 학습은 그 비교 이후 결정한다.
'''
    doc=ROOT/'docs/CUT_AUDIO_FEATURE_COMPARISON_2026-11-05.md';doc.write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 컷 조건 고정 비교:'
    if marker not in old:
        head,rest=old.split('\n',1)
        scores=' / '.join(f"{n} {metric(summary['guitarset']['branches'][n]['performed']['counts']):.2f}%" for n in NAMES)
        log.write_text(head+'\n\n'+marker+' 오디오만 작업. D2~E6 파형 컷과 기존 코드채점을 고정해3개 음추출을186파일에서 비교했다. 실제 상세top1: '+scores+'.133테스트 통과. [원음·그래프·코드종류별 결과](CUT_AUDIO_FEATURE_COMPARISON_2026-11-05.md).\n'+rest,encoding='utf-8')
    print(doc)

if __name__=='__main__':main()
