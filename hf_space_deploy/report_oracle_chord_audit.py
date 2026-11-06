"""Render oracle-only diagnostic evidence and original audio examples."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from oracle_chord_audit import ROOT,OUT

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));s=read(OUT/'summary.json');assets=OUT/'report';assets.mkdir(exist_ok=True)
    names=['annotated_note_pcs','annotated_note_counts','reference_chord_pcs'];labels=['Active note-PC oracle','Active note-count oracle','Full chord-label PC oracle'];pct=lambda c:100*c['top1']/c['evaluated']
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    for ax,layer in zip(axes,['nominal','performed']):
        vals=[pct(s['layers'][layer][n]['counts']) for n in names];bars=ax.bar(labels,vals,color=['#3589b7','#7abca8','#e5a24c']);ax.bar_label(bars,fmt='%.2f%%',fontsize=9);ax.set_ylim(0,108);ax.tick_params(axis='x',rotation=20);ax.set_title(layer+' reference');ax.set_ylabel('Exact chord top1 (%)')
    fig.suptitle('ORACLE DIAGNOSTIC: reference annotations deliberately supplied as input; not model accuracy');fig.tight_layout();fig.savefig(assets/'oracle_comparison.png',dpi=145);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,4));cats=s['layers']['performed']['annotated_note_pcs']['categories'];mapping={'correct':'Correct','dictionary_missing':'Reference outside dictionary','fewer_than_three_active_pcs':'<3 PCs: scorer abstains','reference_pcs_missing':'Reference PCs missing','extra_observed_pcs':'Extra observed PCs','exact_pcs_root_or_quality_tie':'Same-PC root/quality tie'}
    keys=sorted(cats,key=cats.get,reverse=True);bars=ax.barh([mapping[k] for k in keys],[cats[k] for k in keys],color='#4088a9');ax.bar_label(bars);ax.invert_yaxis();ax.set_xlim(0,2300);ax.set_title('Active annotated notes -> performed reference / mutually exclusive diagnosis');fig.tight_layout();fig.savefig(assets/'failure_categories.png',dpi=145);plt.close(fig)
    records=[read(p) for p in sorted((OUT/'records').glob('*.json'))];cases=[]
    for cat in ['fewer_than_three_active_pcs','reference_pcs_missing','exact_pcs_root_or_quality_tie']:
        found=next(((r,f) for r in records for f in r['branches']['performed']['annotated_note_pcs']['frames'] if f['category']==cat),None)
        if found:cases.append(found)
    fig,axes=plt.subplots(len(cases),2,figsize=(13,3*len(cases)));captions=[]
    for i,(r,f) in enumerate(cases):
        rate,x=wavfile.read(r['audio'],mmap=True);t=f['time_s'];lo=max(0,t-.8);hi=min(len(x)/rate,t+.8);clip=x[round(lo*rate):round(hi*rate)].astype(float)/32768
        wavfile.write(assets/f'case_{i+1}.wav',rate,clip.astype(np.float32));axes[i,0].plot(lo+np.arange(len(clip))/rate,clip,lw=.5);axes[i,0].axvline(t,color='red',ls='--');axes[i,0].set_title(f"{r['id']} / {t:.1f}s / reference {f['reference']}",fontsize=9)
        observed=np.zeros(12);observed[f['observed_pcs']]=1;ref=np.zeros(12);ref[f['reference_pcs']]=1
        axes[i,1].bar(np.arange(12)-.17,observed,.34,label='Annotated notes active at center');axes[i,1].bar(np.arange(12)+.17,ref,.34,label='Reference chord PCs');axes[i,1].set_xticks(np.arange(12),['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']);axes[i,1].set_ylim(0,1.35);axes[i,1].legend(fontsize=7);axes[i,1].set_title(mapping[f['category']],fontsize=9)
        captions.append(f"사례{i+1}: `{r['id']}` {t:.1f}초, 상세 코드 `{f['reference']}`, 활성 MIDI `{f['annotated_active_midi']}`, 후보 `{f['top1'] or '보류'}`. 주석과 다른 추정 결과를 구분해 표시했다.\n\n![원음](../{assets.relative_to(ROOT).as_posix()}/case_{i+1}.wav)")
    fig.tight_layout();fig.savefig(assets/'cases.png',dpi=145);plt.close(fig)
    # Original spectrum for the first real example.
    r,f=cases[0];rate,x=wavfile.read(r['audio'],mmap=True);mid=round(f['time_s']*rate);win=x[mid-4096:mid+4096].astype(float)/32768
    fig,ax=plt.subplots(figsize=(10,3));freq=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));ax.plot(freq,20*np.log10(np.maximum(mag,1e-9)));ax.set_xlim(0,6000);ax.set_title(f"Original waveform spectrum / {r['id']} / {f['time_s']:.1f}s");ax.set_xlabel('Hz');fig.tight_layout();fig.savefig(assets/'spectrum.png',dpi=140);plt.close(fig)
    rows=[]
    for n,label in zip(names,['활성 음 주석 / PC별 같은 가중치','활성 음 주석 / 중복 옥타브 수 반영','참조 코드의 전체 구성음 / 진단 전용']):
        a=s['layers']['nominal'][n]['counts'];b=s['layers']['performed'][n]['counts'];rows.append(f"|{label}|{pct(a):.2f}%|{pct(b):.2f}%|{b['abstain']:,}|")
    d=s['dictionary_self_test'];catsrows=['|'+mapping[k]+'|'+str(cats[k])+'|' for k in keys]
    text=f'''# 정답 음을 넣은 코드 판별기 진단 — 2026-11-05

**현재 병목은 오디오 모델만이 아니다. 한 순간의 음만으로 코드 전체를 요구하는 평가 방식과, 최소3음 보류 조건이 큰 영향을 준다.** 정답 주석의 활성 음을 넣어도 상세 코드1위는28.57%였으며 전체4,886시점 중2,595곳(53.11%)은 음 종류가3개 미만이라 보류됐다. 모델의 기존 상세 성적26.87%와 가까운 수치다. 정답 주석 자체도 완벽한 실제 청음 정답은 아니므로 이 값을 절대적인 성능 상한으로 해석하지 않는다.

이번 작업은 진단이며 **정답 정보를 의도적으로 입력했다. 모델의 정확도 결과가 아니다.** 코드 판별기·가중치·학습 모델·운영 기본은 변경하지 않았다.

## 입력을 세 가지로 분리

GuitarSet 반주180개 중 알려진 시간 오류2개를 제외한178파일을 사용했다. 기존 평가와 똑같은1초 그리드·전환 제외 규칙으로4,886시점을 평가했다. 주석 해시를 이전 수신 결과와 대조했다.

1. 각 시점에 활성인6현 note_midi 주석을 모아 옥타브를 합치고, PC마다 같은 가중치를 준다.
2. 같은 음 정보를 쓰되 다른 현·옥타브의 같은 PC는 개수만큼 가중한다. 주석에 실제 음량이 없으므로 음량 정답을 가정하지 않는다.
3. 참조 코드명에서 전체 구성음을 만들어 입력한다. 이는 코드 판별기 자체를 검사하는 정답 주입 실험이다. 실제 그 시점에 전부 울렸다는 뜻은 아니다.

세 입력 모두 기존 coverage 채점과같은180개사전을사용했다. 기본 주석과 상세 수행 주석은 다른 목표이므로 분리했다. note_midi는반올림한MIDI, 시작시각이상/끝시각미만을활성으로취급했다. 소리·그림을새로만들어정답으로쓰지않았다.

## 결과

|주어진 정보|기본 코드 top1|상세 수행 코드 top1|상세 평가 보류수|
|---|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![정답 정보 입력 진단](../{assets.relative_to(ROOT).as_posix()}/oracle_comparison.png)

코드 전체 구성음을 주면 기본 코드 기준4,820/4,886=98.65%였다. 나머지66곳은 같은 피치클래스 집합을 다른 근음·코드로 읽을 수 있는 동점이었다. 목표 코드가 최고 점수에 포함되는 비율은100%였다. 따라서 구성음 전체가 주어질 때 기본 코드의 점수 순서 자체가 무너진 상태는 아니다.

상세 코드 전체 구성음에서는3,119/4,886=63.84%다. 상세 참조의1,190곳(24.36%)이현재사전밖이고, 사전안에있어도407곳은파워코드처럼2음이라기존규칙이보류했다.170곳은동일PC집합의근음/종류동점이었다. 사전범위안으로분모를좁히면84.39%지만 전체 성적과 구분해야 한다.

## 실제 활성 음 주석에서 무엇이 막히나

아래는 상세 수행 주석 기준의 서로 배타적인 분류다. 사전 밖을 먼저 분류하므로 표의 ‘3음 미만’1,960곳과 전체 보류2,595곳은 다르다. 사전 밖인 경우에도3음 미만이 겹칠 수 있다.

|분류|시점 수|
|---|---:|
'''+ '\n'.join(catsrows)+f'''

![실패 원인 분류](../{assets.relative_to(ROOT).as_posix()}/failure_categories.png)

이는 **음이2개만있을때나머지음을마음대로채워도된다는뜻이아니다.** 정확한소리추정과코드맥락추정을분리해야한다. 기타가줄을순서대로치거나앞선음이감쇠하면서, 한순간의활성음은구간의코드구성음보다적을수있다. 주석의음끝처리·코드주석불일치도일부차이를설명할수있고독립청음전사로확정한원인비율은아니다.

활성 PC별 같은 가중치와 현별 개수 가중치의 top1은 같았다. 이번 진단에서는 단순 음 개수 가중치만 바꾸는 것으로 병목이 해결되지 않았다.

## 사전 자체의 완전 구성음 검사

180개템플릿각각의정확한구성음만균등입력했을때top1은{d['top1']}/{d['total']}=63.89%, 목표가최고점수동점에포함되면{d['reference_at_top_score']}/{d['total']}=93.33%였다.12개파워코드는2음이라전부보류됐다. 그외53개top1오류는같은음집합을다르게읽는동점이었다. 예를들어C6와Am7은같은C·E·G·A를공유하므로PC집합만으로근음과기능을항상확정할수없다. 동점정렬을바꾸는것만으로음악적정답을복원할수는없다.

## 실제 원음과 진단 사례

![원본 파형과 주석의 음 대조](../{assets.relative_to(ROOT).as_posix()}/cases.png)

빨간 점선은평가시각이다. 파란막대는그시각에활성인음주석, 주황막대는구간참조코드의구성음이다. 어느것도모델이검출한결과로표시하지않았다. 각분류에서파일이름순첫사례를골랐으며대표비율은전체표를따른다.

'''+ '\n\n'.join(captions)+f'''

![첫 사례 원본 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/spectrum.png)

## 다음 작업의 우선순위

1. **새 학습보다 짧은 시간 구간의 음 근거를 모으는 코드 판단을 먼저 비교한다.** 고정된짧은창·음감쇠·코드전환을고려하고, 정답코드경계를추론에넣지않아야한다. 양쪽코드를섞어새텐션으로오인하지않는지도평가한다.
2. 사전 안에 이미 있는2음 파워코드를 무조건 보류하는 정책을 별도 검토한다.2음만으로일반장단코드를확정하지않고모호성은남겨야한다.
3. 상세주석의생략음·추가음·9/11/13을현재사전이표현하지못하는한계를정리한다. 사전밖정답은기존결과분모에서빼서성적을높이지않는다.
4. 같은PC집합의근음동점은베이스·코드진행·시간맥락의추가근거가필요하다. 정답을보고동점을선택하는결과를실제성적으로보고하지않는다.

이번 턴에서는 진단까지만 수행했고 위 개선안을 운영에 적용하지 않았다. 기존 Basic Pitch 원음 입력 경로를 유지하며, 새 보정 가중치는 계속 미채택 상태다.

## 검증과 재현

148개 회귀/신규 테스트 통과. 정확한장화음, 동일음집합의다른근음,2음파워코드보류, 주석끝시각exclusive, 옥타브합침을검사했다. 전체평가에서수치합계와주석해시도검사했다.

```powershell
python oracle_chord_audit.py
python report_oracle_chord_audit.py
python -m unittest test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료결과는덮어쓰지않는다. 설정과소스해시는config.json, 개별시점의입력음·부족/추가음·동점후보는records,180템플릿검사는dictionary_self_test.json에있다. 정답 주입 값은 향후 오디오 모델 성적과 별도 보관한다.
'''
    (ROOT/'docs/ORACLE_CHORD_DIAGNOSIS_2026-11-05.md').write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 정답 음 진단:'
    if marker not in old:
        head,rest=old.split('\n',1);log.write_text(head+'\n\n'+marker+' 178파일4,886시점에서음주석·코드전체구성음의정답주입검사를완료했다. 활성음주석의상세코드top1은28.57%,전체2,595시점이3음미만으로보류됐다. 코드전체구성음은기본98.65%였고상세는사전밖/파워코드보류/동점제약이남았다.148테스트통과. [진단·원음·그림](ORACLE_CHORD_DIAGNOSIS_2026-11-05.md).\n'+rest,encoding='utf-8')
    print('Oracle report generated',flush=True)

if __name__=='__main__':main()
