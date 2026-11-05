"""Short audio evidence-window review with original excerpts and transition checks."""
import json
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from evaluate_temporal_audio import ROOT,OUT,PRED
from temporal_audio_pool import VARIANTS,pooled_chroma

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));summary=read(OUT/'summary.json');tutorial=read(OUT/'tutorial.json');assets=OUT/'report';assets.mkdir(exist_ok=True)
    pct=lambda c,k='top1':100*c.get(k,0)/max(1,c.get('evaluated',0))
    rows=[]
    for name in VARIANTS:
        a=summary['guitarset']['branches'][name]['performed'];d=summary['idmt']['branches'][name]['nominal'];t=tutorial['summary'][name]
        rows.append(f"|{name}|{pct(a['all']):.2f}%|{pct(a['common_clean']):.2f}%|{a['all']['abstain']:,}|{pct(d['all']):.2f}%|{t['exact_top1']}/9|")
    fig,axes=plt.subplots(1,3,figsize=(14,4.4));widths=[0,.1,.2,.4,.8]
    for ax,domain,layer,scope,title in [(axes[0],'guitarset','performed','all','GuitarSet / same4850centers'),(axes[1],'guitarset','performed','common_clean','GuitarSet / common3758clean centers'),(axes[2],'idmt','nominal','all','IDMT synthetic guitar')]:
        baseline=pct(summary[domain]['branches']['instant'][layer][scope]);ax.axhline(baseline,color='gray',ls='--',label='Instant')
        for method in ['max','mean']:
            vals=[baseline]+[pct(summary[domain]['branches'][f'{method}_{w:.1f}s'][layer][scope]) for w in widths[1:]];ax.plot(widths,vals,marker='o',label=method)
        ax.set_title(title);ax.set_xlabel('Evidence pooling width (s)');ax.set_ylabel('Exact chord top1 (%)');ax.legend(fontsize=8)
    fig.suptitle('Time-window pooling only; raw model input, note range and chord scorer unchanged');fig.tight_layout();fig.savefig(assets/'accuracy.png',dpi=145);plt.close(fig)
    qualities={n:{} for n in VARIANTS};paired=dict(wide_crossing_centers=0,instant_correct=0,max04_correct=0,max08_correct=0,wide_wins_vs04=0,wide_losses_vs04=0);verified=0;excluded=0
    for file in sorted((OUT/'records').glob('*.json')):
        r=read(file);verified+=1;excluded+=r['excluded_audio_edge_centers']
        if r['domain']!='guitarset':continue
        for n in VARIANTS:
            for q,c in r['branches'][n]['performed']['per_quality'].items():qualities[n].setdefault(q,Counter()).update(c)
        a=r['branches']['instant']['performed']['frames'];b=r['branches']['max_0.4s']['performed']['frames'];c=r['branches']['max_0.8s']['performed']['frames']
        assert len(a)==len(b)==len(c)
        for i,j,k in zip(a,b,c):
            if not k['window_crosses_reference_boundary']:continue
            paired['wide_crossing_centers']+=1;paired['instant_correct']+=int(i['correct_top1']);paired['max04_correct']+=int(j['correct_top1']);paired['max08_correct']+=int(k['correct_top1'])
            paired['wide_wins_vs04']+=int(k['correct_top1'] and not j['correct_top1']);paired['wide_losses_vs04']+=int(j['correct_top1'] and not k['correct_top1'])
    (OUT/'quality_summary.json').write_text(json.dumps({n:{q:dict(v) for q,v in qs.items()} for n,qs in qualities.items()},indent=2),encoding='utf-8')
    audit=dict(evaluated_files=verified,paired_transition_check=paired,total_excluded_edge_centers=excluded,
               baseline_replay='Instant results equal original raw-frame model on common audio-supported centers',
               prediction_uses_reference_boundaries=False)
    (OUT/'audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
    qrows=[]
    for q in ['major','minor','7','maj7','m7','m7b5']:
        qrows.append('|'+q+'|'+'|'.join(f"{pct(qualities[n][q]):.2f}%" for n in ['instant','max_0.1s','max_0.2s','max_0.4s','max_0.8s'])+'|')
    meta=read(PRED/'tutorial_raw.json');rate,x=wavfile.read(meta['audio']);x=x.mean(axis=1)
    with np.load(PRED/'tutorial_raw.npz') as d:grid=d['times'];frames=d['note']
    fig,axes=plt.subplots(3,2,figsize=(13,8));cases=[207,211,223];colors=['#555555','#2070b0','#27a080','#e58b30'];pcs=['C','Db','D','Eb','E','F','Gb','G','Ab','A','Bb','B']
    for row,pts in enumerate(cases):
        center=pts-194;lo=round((center-.5)*rate);hi=round((center+.5)*rate);clip=x[lo:hi];axes[row,0].plot(pts-.5+np.arange(len(clip))/rate,clip,lw=.5)
        for width,color in zip([.1,.2,.4,.8],['#888888','#2070b0','#27a080','#e58b30']):axes[row,0].axvline(pts-width/2,color=color,alpha=.6,label=f'{width}s');axes[row,0].axvline(pts+width/2,color=color,alpha=.6)
        axes[row,0].axvline(pts,color='black',ls='--',lw=.8,label='center');axes[row,0].legend(fontsize=6,ncol=5,loc='upper left')
        axes[row,0].set_title(f'Original guitar estimate / PTS{pts}s; pooling boundaries')
        for j,(width,color) in enumerate(zip([0,.2,.4,.8],colors)):
            sal=pooled_chroma(grid,frames,[center],width,'max')[0];axes[row,1].bar(np.arange(12)+(j-1.5)*.2,sal,.2,label='instant' if not width else f'{width}s',color=color)
        axes[row,1].set_xticks(np.arange(12),pcs);axes[row,1].set_title('Model PC evidence; max pool, not ground truth');axes[row,1].legend(fontsize=7)
        if pts in [207,211]:
            for width in [.2,.8]:
                audio=x[round((center-width/2)*rate):round((center+width/2)*rate)]
                wavfile.write(assets/f'pts_{pts}_{width:.1f}s.wav',rate,audio.astype(np.float32))
    fig.tight_layout();fig.savefig(assets/'cases.png',dpi=145);plt.close(fig)
    fig,ax=plt.subplots(figsize=(10,3));win=x[round(13*rate)-4096:round(13*rate)+4096];freq=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));ax.plot(freq,20*np.log10(np.maximum(mag,1e-9)));ax.set_xlim(0,6000);ax.set_title('207s original spectrum; frequency range unchanged');ax.set_xlabel('Hz');fig.tight_layout();fig.savefig(assets/'spectrum.png',dpi=140);plt.close(fig)
    trows=[]
    for r in tutorial['rows']:
        pred=[]
        for n in ['instant','max_0.1s','max_0.2s','max_0.4s','max_0.8s']:
            top=r['branches'][n]['top3'];pred.append(top[0]['concert_symbol'] if top else '보류')
        trows.append('|'+str(r['reference']['pts'])+'|'+r['reference']['concert_symbol']+'|'+'|'.join(pred)+'|')
    pic=next(r['reference']['image'] for r in tutorial['rows'] if r['reference']['pts']==207)
    text=f'''# 짧은 시간 구간으로 오디오 음 근거 모으기 — 2026-11-05

사용자가 지정한 **시간 구간**을0.1·0.2·0.4·0.8초로 좁혀 비교했다. 주파수 컷 실험이 아니다. Basic Pitch가 이미 추출한 음의 활성값을 짧은 구간에서 모으고, 기존 코드 채점으로 판단했다. **새 학습 없이 개선을 확인했다.** 튜토리얼9곳은순간5/9에서0.1~0.2초모으기7/9, GuitarSet의같은시점상세코드정확도는26.72→0.4초42.80%였다. 다만 모두 이미 본 개발 자료이며 최적 폭을 독립 검증한 결과는 아니다.

## 고정 조건과 범위의 의미

- 모델: 보정하지 않은 Basic Pitch, 컷 없는 기타 오디오 입력, 출력 음 후보만 D2~E6, 기본 문턱0.3.
- 비교: 한 시점 / 중심±0.05·0.1·0.2·0.4초. 같은 구간에서각음의최대활성값(max)을취하는방식과평균(mean)을비교했다. 음은단순합산하지않았다.
- 판단: 기존180개화음사전·기존coverage채점·3종류미만보류조건을고정했다.
- 추론은모델활성값과시각만받는다. 정답코드경계로창을자르거나창폭을고르지않았다.

**모델에 넣는 원음 자체를0.2초로 잘라 다시 추론한 것은 아니다.** 이번에 좁힌 범위는 ‘코드 판단에 모으는 음 근거의 시간 범위’다. Basic Pitch 자체의약2초문맥은그대로다. 중심창은미래오디오도사용하므로실시간지연최적화실험도아니다.

모든창을공정하게비교하기위해0.8초전체창이음원안에들어오는시점만공통으로사용했다. 그결과GuitarSet178파일의상세평가시점은기존4,886에서4,850개로36개줄었다. 각방식의분모는같다. IDMT6파일1,638곳과튜토리얼9곳도비교했다. 순간방식은같은시점의이전모델결과와top1/top3가전수일치했다.

## 결과

‘공통 안정구간’은모든방식에서동일한3,758시점으로, ±0.4초가참조코드구간안에들어오는곳이다. 이는평가분류에만정답경계를사용한것이며실제알고리즘에는경계가주어지지않는다.

|시간 모으기|GuitarSet 상세 전체 top1|공통 안정구간 top1|보류수 /4,850|IDMT 기타 top1|튜토리얼|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![시간 범위별 같은 조건 비교](../{assets.relative_to(ROOT).as_posix()}/accuracy.png)

max가mean보다순차적으로울리는음을모으는데효과적이었다. max0.4초는전체코드1위를42.80%로높이고보류를2,682→898개로줄였다.0.8초는안정구간에서는더좋았지만전체는42.76%로비슷하고튜토리얼은5/9로내려갔다. 폭을늘리면계속좋아지는것은아니다.

|상세 코드 종류|순간|max0.1초|max0.2초|max0.4초|max0.8초|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(qrows)+f'''

GuitarSet은기본모델의학습자료중하나이므로독립일반화성적이아니다. 이번에학습하거나문턱을최적화하지않았지만, 이개발결과만으로미지영상에서같은이득을보장하지는않는다.

## 코드 전환이 섞이는지 확인

0.8초창이참조코드경계를가로지르는시점은{paired['wide_crossing_centers']}개였다. 같은시점에서순간정답{paired['instant_correct']}개,0.4초정답{paired['max04_correct']}개,0.8초정답{paired['max08_correct']}개였다.0.4→0.8초로넓힐때정답으로바뀐{paired['wide_wins_vs04']}곳과오답으로바뀐{paired['wide_losses_vs04']}곳이있었다. ‘전환을가로지르면전부실패’하거나‘좁힐수록무조건좋다’고해석하지않는다.

기존평가가중심시점의코드전환주변약0.143초를이미제외했기때문에0.1·0.2초창의경계교차가0으로나오는선정효과가있다. 실제모든영상시점에서전환에안전하다는뜻이아니다. 모델의2초문맥자체가코드전환을포함할가능성도남아있다.

## 실제 튜토리얼 사례

|영상초|참조 코드|순간|max0.1초|max0.2초|max0.4초|max0.8초|
|---|---|---|---|---|---|---|
'''+ '\n'.join(trows)+f'''

207초G와221초A7은순간판단에서보류였지만0.1~0.2초에서정답이됐다. 반면211초A는0.4초에서Amaj7,223초Bb는0.4초에서Bbadd9로변해추가음누적오류가생겼다. 이음이실제이전코드잔향인지모델오검출인지는따로청음검증하지않았으므로원인을확정하지않는다.

![원본 파형·창 범위·실제 모델 후보 비교](../{assets.relative_to(ROOT).as_posix()}/cases.png)

왼쪽선은중심에서0.1/0.2/0.4/0.8초범위를표시한다. 오른쪽막대는모델의정규화된PC활성값이며정답이나보정된확률이아니다.

207초 원음0.2초: ![짧은 원음](../{assets.relative_to(ROOT).as_posix()}/pts_207_0.2s.wav)

207초 원음0.8초: ![넓은 원음](../{assets.relative_to(ROOT).as_posix()}/pts_207_0.8s.wav)

211초 원음0.2초: ![짧은 원음](../{assets.relative_to(ROOT).as_posix()}/pts_211_0.2s.wav)

211초 원음0.8초: ![넓은 원음](../{assets.relative_to(ROOT).as_posix()}/pts_211_0.8s.wav)

재생자료는같은기타추정트랙을실제로잘라낸음원이다. 모델출력을사인파로합성한것이아니고게인보정도하지않았다. 짧은재생파일은귀로코드를확정하기어려울수있다.

![207초 원음 스펙트럼 — 주파수 범위 변경 없음](../{assets.relative_to(ROOT).as_posix()}/spectrum.png)

![207초 기존 참조 원본 화면](../{Path(pic).relative_to(ROOT).as_posix()})

## 적용 상태와 다음 판단

0.2초와0.4초max출력을기존guitar_evidence.v1/harmony입력까지실제로연결했다. 결과는`dataset/audio_analysis/runs/barre_basic_pitch_pool_0_2_20261105_v1`와`barre_basic_pitch_pool_0_4_20261105_v1`이다. 개별음의시작·끝을임의로늘리지않고코드판단용시간근거만모았다. 손·지판·오디오모델가중치·기본코드채점은변경하지않았다.

개발용기본후보는짧은0.2초max로두고0.4초를비교경로로보관하는것이타당하다.0.2초는현재튜토리얼에서더안정적이고0.4초는전체GuitarSet에서더높았기때문이다. **아직확정최적값이나전체영상기본설정으로승격하지않았다.** 다음에는이미본9곳외의구간에서0.2/0.4초를검증하고코드변화감지와결합해야한다. 정답을보고매시점좋은폭을선택하는방식은사용하지않는다.

## 검증과 재현

152개테스트통과. 순차음수집, 창끝exclusive, 불완전창거절, 음역제한, 기존전체회귀를검사했다.184파일의기존순간결과전수재현과전체창의공통지원범위도확인했다. 신규보정학습이나참조정답주입은없다.

```powershell
python evaluate_temporal_audio.py
python report_temporal_audio.py
python export_temporal_audio.py --prediction dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz --source-id VIDEO_SOURCE_ID --offset 194 --width 0.2 --method max --output NEW_DIRECTORY
python -m unittest test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

완료평가출력은덮어쓰지않는다. 설정·소스해시는config.json, 시점별후보와경계교차는records, 코드종류별집계는quality_summary.json, 짝지은전환비교는audit.json에있다.
'''
    (ROOT/'docs/TEMPORAL_AUDIO_WINDOW_REVIEW_2026-11-05.md').write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 짧은 시간창 비교:'
    if marker not in old:
        head,rest=old.split('\n',1);log.write_text(head+'\n\n'+marker+' 주파수아닌시간범위를0.1/0.2/0.4/0.8초로고정해모델출력max/mean을비교했다.같은4,850시점상세코드26.72→max0.4초42.80%,튜토리얼5/9→max0.1/0.2초7/9.넓은창추가음누적과전환교차를별도검사했다.0.2/0.4초입력연결완료,152테스트통과. [보고서·원음·비교그림](TEMPORAL_AUDIO_WINDOW_REVIEW_2026-11-05.md).\n'+rest,encoding='utf-8')
    print(json.dumps(paired,indent=2));print('Temporal report generated',flush=True)

if __name__=='__main__':main()
