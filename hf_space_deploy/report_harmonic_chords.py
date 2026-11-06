"""Generate a reproducible review, including negative evidence and real audio."""
import json
from pathlib import Path
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from benchmark_harmonic_chords import ROOT,BRANCHES
from guitarset_benchmark import KNOWN_TIMING,load_reference,TEMPLATES,parse_chord
from chord_score_variants import score_variants
from supported_harmonic_features import supported_salience
from idmt_chords_benchmark import pcm_float
from harmonic_chord_features import WINDOW
from compare_guitar_stem_accuracy import safe_evaluate

BASE=ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1'
GATE=ROOT/'dataset/integration_review/runs/supported_harmonics_20261105_v1'

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    summary=read(BASE/'summary.json');gate_summary=read(GATE/'summary.json');audit=read(BASE/'audit.json')
    names=BRANCHES+['supported_legacy','supported_cosine'];short=['Peak/L','Peak/C','Harm/L','Harm/C','Gate/L','Gate/C']
    for domain in summary:summary[domain]['branches'].update(gate_summary[domain]['branches'])
    records=[read(p) for p in sorted((BASE/'records').glob('*.json'))];gate_records={p.stem:read(p) for p in (GATE/'records').glob('*.json')}
    assets=BASE/'report';assets.mkdir(exist_ok=True)
    gate_pc=Counter();verified=0
    for r in records:
        g=gate_records[r['id']]
        assert g['times']==r['times'] and g['audio']==r['audio'] and g['annotation']==r['annotation'];verified+=1
        if r['domain']!='guitarset' or r['id'] in KNOWN_TIMING:continue
        _,notes=load_reference(r['annotation'])
        for t,sal in zip(g['times'],g['salience']):
            sal=np.array(sal);pred=set(np.where((sal>0)&(sal>=.1*sal.max()))[0]);truth={round(n['midi'])%12 for n in notes if n['start']<=t<n['end']}
            gate_pc.update(tp=len(pred&truth),fp=len(pred-truth),fn=len(truth-pred),windows=1)
    p=gate_pc['tp']/(gate_pc['tp']+gate_pc['fp']);r=gate_pc['tp']/(gate_pc['tp']+gate_pc['fn'])
    pc=dict(audit['note_pc_metrics']);pc['supported']=dict(counts=dict(gate_pc),precision=p,recall=r,f1=2*p*r/(p+r))
    tutorial=audit['tutorial'];rate,x=wavfile.read(ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav');x=pcm_float(x).mean(axis=1)
    for row in tutorial['rows']:
        start=round((row['reference']['pts']-194)*rate)-WINDOW//2;s,_,_=supported_salience(x[start:start+WINDOW],rate)
        for scorer,(scores,rank,usable) in score_variants(np.array([s])).items():
            if scorer not in ('legacy','cosine'):continue
            ranked=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
            row['branches']['supported_'+scorer]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,row['reference']))
    tutorial['summary']={b:{k:sum(row['branches'][b]['evaluation'][k] for row in tutorial['rows']) for k in ['exact_top1','exact_top3','root_top1']} for b in names}
    (BASE/'followup_audit.json').write_text(json.dumps(dict(supported_grid_verified=verified,note_pc_metrics=pc,tutorial=tutorial),indent=2),encoding='utf-8')
    fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    for ax,domain,layer in zip(axes,['guitarset','guitarset','idmt'],['nominal','performed','nominal']):
        vals=[100*summary[domain]['branches'][b][layer]['counts']['top1']/summary[domain]['branches'][b][layer]['counts']['evaluated'] for b in names]
        bars=ax.bar(short,vals,color=['#808080','#b2b2b2','#2c7fb8','#7fcdbb','#e48b26','#f4c77a']);ax.bar_label(bars,fmt='%.1f',fontsize=8)
        ax.set_title(f'{domain} / {layer}');ax.set_ylim(0,70);ax.tick_params(axis='x',rotation=45);ax.set_ylabel('Exact top1 (%)')
    fig.suptitle('Same-window ablation: feature extraction and chord scoring have separate trade-offs')
    fig.tight_layout();fig.savefig(assets/'accuracy.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(15,4.7))
    for ax,domain,layer in zip(axes[:2],['guitarset','idmt'],['performed','nominal']):
        bottom=np.zeros(len(names))
        for key,label,color in [('correct','Correct','#229b72'),('wrong_seventh_pc_weak','Wrong: seventh PC weak','#e8a43a'),('wrong_seventh_pc_present','Wrong: seventh PC present','#a75365')]:
            vals=np.array([summary[domain]['branches'][b][layer]['seventh_diagnosis'].get(key,0) for b in names]);ax.bar(short,vals,bottom=bottom,label=label,color=color);bottom+=vals
        ax.set_title(domain+' / 7, maj7, m7, m7b5');ax.tick_params(axis='x',rotation=45);ax.legend(fontsize=7)
    xx=np.arange(3)
    for j,key in enumerate(['precision','recall','f1']):axes[2].bar(xx+(j-1)*.25,[100*pc[b][key] for b in ['peak','harmonic','supported']],.25,label=key)
    axes[2].set_xticks(xx,['Peak','Harmonic','+ support']);axes[2].set_ylim(0,105);axes[2].set_title('GuitarSet actual note-PC evidence');axes[2].legend(fontsize=8)
    fig.tight_layout();fig.savefig(assets/'diagnosis.png',dpi=145);plt.close(fig)
    cases=[]
    for improved in [True,False]:
        found=False
        for rec in records:
            if rec['domain']!='guitarset' or rec['id'] in KNOWN_TIMING:continue
            for old,new in zip(rec['branches']['peak_legacy']['performed']['frames'],rec['branches']['harmonic_legacy']['performed']['frames']):
                ref=parse_chord(old['reference']);quality=next((c['quality'] for c in TEMPLATES if c['root_pc']==ref['root_pc'] and tuple(c['pcs'])==ref['pcs']),None)
                if quality not in ('7','maj7','m7','m7b5'):continue
                if old['correct_top1']==(not improved) and new['correct_top1']==improved:
                    cases.append((rec,old,new));found=True;break
            if found:break
    fig,axes=plt.subplots(2,2,figsize=(13,7));case_text=[]
    note_names=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
    for i,(rec,old,new) in enumerate(cases):
        rate,a=wavfile.read(rec['audio'],mmap=True);t=old['time_s'];lo=max(0,t-1);hi=min(len(a)/rate,t+1);clip=pcm_float(a[round(lo*rate):round(hi*rate)])
        wavfile.write(assets/f'case_{i+1}.wav',rate,clip.astype(np.float32));axes[i,0].plot(np.arange(len(clip))/rate+lo,clip,lw=.5);axes[i,0].axvline(t,color='red',ls='--')
        axes[i,0].set_title(f"{rec['id']} / {t:.1f}s / reference {old['reference']}",fontsize=9)
        index=int(np.argmin(abs(np.array(rec['times'])-t)));g=gate_records[rec['id']]
        for j,(label,sal) in enumerate([('Peak',rec['peak_salience'][index]),('Harmonic',rec['harmonic_salience'][index]),('Supported',g['salience'][index])]):axes[i,1].bar(np.arange(12)+(j-1)*.25,sal,.25,label=label)
        for pc_index in old['reference_pcs']:axes[i,1].axvspan(pc_index-.45,pc_index+.45,color='green',alpha=.08)
        axes[i,1].set_xticks(np.arange(12),note_names);axes[i,1].legend(fontsize=8);axes[i,1].set_ylabel('Normalized candidate salience')
        win=clip[round((t-lo)*rate)-WINDOW//2:round((t-lo)*rate)+WINDOW//2];freq=np.fft.rfftfreq(WINDOW,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(WINDOW)))
        sf,sa=plt.subplots(figsize=(10,3));sa.plot(freq,20*np.log10(np.maximum(mag,1e-9)));sa.set_xlim(50,6000);sa.set_xlabel('Frequency (Hz)');sa.set_ylabel('Uncalibrated magnitude (dB)');sa.set_title(f"Original spectrum / {t:.1f}s");sf.tight_layout();sf.savefig(assets/f'spectrum_{i+1}.png',dpi=130);plt.close(sf)
        pred=lambda f:f['top3'][0]['symbol'] if f['top3'] else '보류'
        case_text.append(f"사례{i+1}: `{rec['id']}` {t:.1f}초, 상세 주석 `{old['reference']}`. Peak/L `{pred(old)}` → Harm/L `{pred(new)}`."+f"\n\n![원음](../{assets.relative_to(ROOT).as_posix()}/case_{i+1}.wav)\n\n![원본 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/spectrum_{i+1}.png)")
    fig.tight_layout();fig.savefig(assets/'cases.png',dpi=145);plt.close(fig)
    def pct(c,key='top1'):return 100*c.get(key,0)/max(1,c['evaluated'])
    rows=[]
    for b in names:
        g=summary['guitarset']['branches'][b];d=summary['idmt']['branches'][b]['nominal']
        rows.append(f"|{b}|{pct(g['nominal']['counts']):.2f}%|{pct(g['performed']['counts']):.2f}%|{pct(g['performed']['counts'],'top3'):.2f}%|{pct(d['counts']):.2f}%|")
    quality_rows=[]
    for q in ['major','minor','7','maj7','m7','m7b5','5']:
        vals=[]
        for domain,layer in [('guitarset','performed'),('idmt','nominal')]:
            for b in ['peak_legacy','harmonic_legacy','supported_legacy']:
                c=summary[domain]['branches'][b][layer]['per_quality'][q];vals.append(f"{pct(c):.2f}% ({c['top1']}/{c['evaluated']})")
        quality_rows.append('|'+q+'|'+'|'.join(vals)+'|')
    pc_rows=['|'+b+'|'+ '|'.join(f'{100*v[k]:.2f}%' for k in ['precision','recall','f1'])+'|' for b,v in pc.items()]
    tutorial_rows=['|'+b+'|'+ '|'.join(str(tutorial['summary'][b][k])+'/9' for k in ['exact_top1','exact_top3','root_top1'])+'|' for b in names]
    td=summary['guitarset']['branches']['peak_legacy']['performed']['seventh_diagnosis'];newd=summary['guitarset']['branches']['harmonic_legacy']['performed']['seventh_diagnosis']
    pic=Path(tutorial['rows'][0]['reference']['image']).relative_to(ROOT).as_posix()
    text=f'''# 7화음 오류 진단과 배음 기반 특징 실험 — 2026-11-05

7음을 잘 못 읽는 문제와 읽은 근거를 잘못 채점하는 문제가 함께 있다. 고정 배음 모델을 추가해 IDMT 및 일부 실제 7화음에서 개선됐지만, 실제 음 후보 과검출과 m7 퇴보가 확인됐다. 운영 기본 설정은 유지하고 새 기능은 재현 가능한 실험으로 보관했다. 학습·외부 API·추가 다운로드·비전 가중치 변경은 하지 않았다.

## 무엇을 만들었나

`harmonic_chord_features.py`는 D2~E6의 51개 기본음 각각을 1~8차 배음(고정 진폭 1/h) 묶음으로 표현한다. 8192샘플 Hann 스펙트럼에서 50~6000Hz를 관측하고 비음수 최소제곱으로 각 후보의 크기를 구한다. 넓은 음색 기울기의 영향을 줄이기 위해 관측과 모델에 동일한 국소 포락선 가중치를 준다. 학습된 모델이 아니라 창마다 크기 계수를 맞추는 신호 처리 실험이다. 동음·옥타브·서로 겹치는 배음은 여전히 모호하다.

첫 결과에서 과검출이 증가해 `supported_harmonic_features.py`를 별도 추가했다. 기존 추출기와 동일한 전역 최대 크기12% 문턱을 넘는 국소 피크가 기본음 위치에서 관측될 때만 후보를 남긴다. 문턱 탐색은 하지 않았다. 비교 이름의 L은 기존 coverage 채점, C는 cosine 채점이다. C에는 활성 피치클래스 최소2개 조건도 포함된다.

## 평가 조건

GuitarSet comp180파일을 실행했고 알려진 시간오류2개를 제외한178파일의 안정창4,886개를 주 결과로 썼다. 0.5초부터1초 간격의 고정 그리드이며 코드 주석으로 예측 시각을 고르지 않았다. 주석 경계에서 창 반폭+0.05초 이상 떨어진 곳만 채점했다. 기본 주석과 상세 수행 주석은 별도로 유지했다. 상세 주석의 사전 밖1,190개도 전체 분모에 남겼다.

IDMT 기타6음색 ×273구간=1,638개의 중심창을 평가했다. 문제가 있는 비기타 전위 주석은 이 실험에서 제외했다. 두 데이터 모두 원본 모노 파형을 쓰고 대역 컷·시간 평균은 하지 않았다. 기존 Peak는65~1600Hz 피크를 사용하고 Harmonic은50~6000Hz의 배음까지 관측하므로 관측 대역 확대와 모델링 효과가 함께 포함된다. 이전 보고서의 D2~E6 파형 컷·100ms 표본 성적과 직접 비교하지 않는다. 이번 표 안에서는 같은 오디오·같은 창·같은 정답 분모로 비교했다.

186개 입력 음원의 SHA256을 기존 수신/IDMT 평가와 대조했고, IDMT 기존 채점·cosine의 구간별 top1/top3 결과가 이전 결과와 전수 일치했다. 후속 support 실험도186파일의 시각 그리드·원음·주석 경로 일치를 확인했다.

## 전체 및 코드 종류별 결과

|방식|GuitarSet 기본 top1|상세 전체 top1|상세 전체 top3|IDMT 기타 top1|
|---|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![동일 창의 추출/채점 분리 비교](../{assets.relative_to(ROOT).as_posix()}/accuracy.png)

|상세 코드|실제 Peak/L|실제 Harm/L|실제 Gate/L|IDMT Peak/L|IDMT Harm/L|IDMT Gate/L|
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(quality_rows)+f'''

기존 채점 그대로 특징만 바꾸면 IDMT 전체는44.38→56.11%로 개선됐다. 실제 GuitarSet의 maj7·도미넌트7·m7b5는 좋아졌지만 m7·일반 장단화음이 퇴보해 상세 전체는13.34→12.61%였다. cosine 채점끼리 비교하면 실제 상세 전체19.83→21.63%로 개선되지만 IDMT는 기존 coverage보다 낮다. 어느 한 방식이 모든 코드·데이터에 우세하지 않다.

## 7음 근거와 과검출 진단

상세 주석에서7·maj7·m7·m7b5인875창을 진단했다. Peak/L의 오답630개 중 7음 피치클래스가 최대 크기의10% 미만인 경우는{td['wrong_seventh_pc_weak']}개, 그 이상인데도 오답인 경우는{td['wrong_seventh_pc_present']}개였다. 후자에는 근음 오류도 포함돼 단순히 채점만의 문제라고 단정할 수 없다. 그 피치클래스가 배음에서 생겼을 수도 있으므로 ‘근거 있음’은 실제 7음 검출 성공을 뜻하지 않는다.

Harm/L은875개 중 정답을{td['correct']}→{newd['correct']}개로 늘리고, 오답 중 7음 근거가 약한 경우를{td['wrong_seventh_pc_weak']}→{newd['wrong_seventh_pc_weak']}개로 줄였다. 하지만 음 후보 과검출이 늘었는지 별도로 확인할 필요가 있었다.

GuitarSet6현 note_midi 주석을 시간별로 합쳐 실제 활성 피치클래스 집합과 대조했다. 아래는5,421창 전체(무음 포함)의 피치클래스 precision/recall이며, 개별 음높이·현·온셋 성적이 아니다. 활성 후보 문턱은 각 창 최대 salience의10%로 고정했다.

|특징|정밀도|재현율|F1|
|---|---:|---:|---:|
'''+ '\n'.join(pc_rows)+f'''

![7화음 근거와 실제 note 주석 비교](../{assets.relative_to(ROOT).as_posix()}/diagnosis.png)

Harmonic은 재현율을 높였으나 정밀도가 크게 떨어졌다. Support 제한은 후보 F1을62.03→68.27%로 높였으나, 약한 실제 7음도 제거하고 보류를 늘린다. ‘배음 제거 완료’라고 볼 수 없으며 기본 시스템에 적용하지 않은 이유다.

## 실제 개선과 실패 원음

![원본 파형과 후보 분포](../{assets.relative_to(ROOT).as_posix()}/cases.png)

초록 배경은 상세 주석의 구성음, 막대는 각 특징의 추정 분포이며 확률이 아니다. 빨간 점선은 창 중심이다. 알파벳 순서의 파일에서 조건에 맞는 첫 개선/퇴보 사례를 각각 골랐다. 사례의 주석은 GuitarSet 상세 수행 주석이며 독립 청음 검수는 아니다. 두 소리는 처리 전 동일 원음으로, 이 실험은 파형을 변경하지 않는다.

'''+ '\n\n'.join(case_text)+f'''

## 현재 튜토리얼 확인

기존 안정구간9개에서 분리된 기타 추정 트랙의 정확한 영상 PTS 중심8192샘플 창을 평가했다. Capo.1 참조를 유지했다. 원본 스테레오는 모노 평균했고 시간 평균은 하지 않았다. 이미 사용한 작은 개발 표본이며 독립 시험이 아니다. 이전100ms 최근접 표본이나0.4초 평균 성적과 직접 비교하지 않는다.

![195초 원본 화면 — 기존 참조 자료](../{pic})

|방식|정확 코드1위|상위3개 포함|근음1위|
|---|---:|---:|---:|
'''+ '\n'.join(tutorial_rows)+'''

## 검증·재현·다음 판단

130개 회귀/신규 테스트 통과. 단일 기본음의 배음, 실제 도미넌트7 구성음 보존, 무음·비정상 입력, 피크 제한,7음 근거 분류를 포함한다. 합성 단위 테스트의 통과를 실제 연주 정확도로 대신하지 않았다.

재현 명령:

```powershell
python benchmark_harmonic_chords.py --output dataset/integration_review/runs/harmonic_ablation_20261105_v1
python audit_harmonic_chords.py
python benchmark_supported_harmonics.py
python report_harmonic_chords.py
python -m unittest test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료된 결과를 보호하기 위해 실행기는 기존 출력에 덮어쓰지 않는다. 재실행은 출력 경로를 새 버전으로 지정하거나 후속 실행기의 OUT 상수를 바꾸고 실행한다. 각 config.json에 소스 해시와 고정 조건, audit.json에 입력 대조·주석 해시, followup_audit.json에 support 평가와 튜토리얼 개별 후보를 남겼다.

이번 시도는 7음 약화의 일부를 개선했으나 전체 문제를 해결하지는 못했다. 다음 우선 과제는 고정1/h 배음 모델이 실제 음색에 맞지 않아 만드는 가짜 기본음과 옥타브 후보를 줄이는 것이다. 검증셋을 따로 고정한 뒤 기존 note 주석의 실제 음 후보 정밀도·재현율을 목표로 비교해야 한다. 9·11·13 텐션은 이번 유효 표본과 사전으로 충분히 검증하지 않았다. 임의 코드별 스위칭이나 정답을 보고 선택하는 합성 성적은 만들지 않았다.
'''
    doc=ROOT/'docs/HARMONIC_SEVENTH_EXPERIMENT_2026-11-05.md';doc.write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 7화음 실험:'
    if marker not in old:
        head,rest=old.split('\n',1);log.write_text(head+'\n\n'+marker+' 배음NNLS 및 기본음 피크 제한을 구현해 GuitarSet180파일·IDMT기타6파일에서6개 조합을 비교했다. IDMT기타 기존채점44.38→56.11%, 실제 상세7화음245/875→301/875로 개선됐지만 실제 음후보 정밀도 하락과m7 퇴보가 있어 운영 기본은 유지했다.130테스트 통과. [원음·그림·실패 포함 보고서](HARMONIC_SEVENTH_EXPERIMENT_2026-11-05.md).\n'+rest,encoding='utf-8')
    print(json.dumps(dict(note_pc=pc,tutorial=tutorial['summary']),indent=2));print(doc)

if __name__=='__main__':main()
