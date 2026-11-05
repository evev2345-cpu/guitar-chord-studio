"""Report change-aware pooling including detector failures and frozen new review."""
import json
import hashlib
from collections import Counter
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from evaluate_change_aware_audio import ROOT,METHODS
from calibrated_audio_changes import detect_changes
from audio_change_pool import clipped_pool

OUT=ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2'
FIRST=OUT.with_name('change_aware_audio_20261105_v1')
PRED=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions'

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));s=read(OUT/'summary.json');old=read(OUT/'old_tutorial.json');new=read(OUT/'new_tutorial.json');cal=read(OUT/'detector_calibration.json');refs=read(OUT/'new_references.json')
    assert hashlib.sha256((OUT/'new_references.json').read_bytes()).hexdigest()==read(OUT/'reference_freeze_sha256.json')['sha256']
    assets=OUT/'report';assets.mkdir(exist_ok=True);pct=lambda c:100*c['top1']/c['evaluated'];labels=['Instant','Fixed0.2s','Fixed0.4s','Clipped0.2s','Clipped0.4s']
    rows=[]
    for m,label in zip(METHODS,labels):
        g=s['guitarset']['branches'][m]['performed'];c=g['counts'];seven=g['seventh_diagnosis']
        rows.append(f"|{label}|{pct(c):.2f}%|{100*seven['correct']/seven['evaluated']:.2f}%|{c['false_added_extension']}|{c['abstain']}|{old['summary'][m]['exact_top1']}/9|{new['summary'][m]['exact_top1']}/4|")
    fig,axes=plt.subplots(1,3,figsize=(14,4.5));x=np.arange(5)
    values=[pct(s['guitarset']['branches'][m]['performed']['counts']) for m in METHODS];bars=axes[0].bar(labels,values,color=['#777777','#57a08c','#3c8ab8','#e8b36b','#df8b38']);axes[0].bar_label(bars,fmt='%.2f',fontsize=8);axes[0].set_ylim(0,60);axes[0].set_title('GuitarSet / same4850centers');axes[0].set_ylabel('Exact chord top1 (%)')
    for j,(review,title) in enumerate([(old,'Old9development references'),(new,'New4references; selected before v1')],start=1):
        denom=len(review['rows']);vals=[review['summary'][m]['exact_top1'] for m in METHODS];bars=axes[j].bar(labels,vals,color=['#777777','#57a08c','#3c8ab8','#e8b36b','#df8b38']);axes[j].bar_label(bars,labels=[f'{v}/{denom}' for v in vals],fontsize=8);axes[j].set_ylim(0,denom+1);axes[j].set_title(title)
    for ax in axes:ax.tick_params(axis='x',rotation=35)
    fig.suptitle('Audio-only boundary clipping: fewer false extensions, slight overall accuracy cost');fig.tight_layout();fig.savefig(assets/'comparison.png',dpi=145);plt.close(fig)
    # Held-out-for-threshold-selection patterns; pretrained and prior development overlap remains.
    split=read(ROOT/'dataset/audio_analysis/runs/note_calibrator_20261105_v1/split_manifest.json');test_ids={r['id'] for r in split if r['split']=='test'};holdout={m:Counter() for m in METHODS};tc=Counter();errs=[]
    for path in (OUT/'records').glob('*.json'):
        r=read(path)
        if r['id'] not in test_ids:continue
        for m in METHODS:holdout[m].update(r['branches'][m]['performed']['counts'])
        for k in ['tp','fp','fn']:tc[k]+=r['transition']['performed'][k]
        errs+=r['transition']['performed']['signed_errors_s']
    (OUT/'heldout_pattern_summary.json').write_text(json.dumps(dict(recordings=len(test_ids),code_counts={m:dict(c) for m,c in holdout.items()},transition=dict(counts=dict(tc),median_abs_error_s=float(np.median(np.abs(errs))))),indent=2),encoding='utf-8')
    # Four real examples; red lines are detected audio candidates, never reference boundaries.
    fig,axes=plt.subplots(4,1,figsize=(12,9));examples=[('old',211.),('old',223.),('new',257.),('new',253.)]
    for ax,(scope,pts) in zip(axes,examples):
        predpath=PRED/'tutorial_raw.npz' if scope=='old' else OUT/'new_predictions/new_tutorial_raw.npz';meta=read(predpath.with_suffix('.json'));offset=194 if scope=='old' else 250
        rate,a=wavfile.read(meta['audio']);mono=a.mean(axis=1);center=pts-offset;lo=round((center-.5)*rate);hi=round((center+.5)*rate);clip=mono[lo:hi]
        with np.load(predpath) as data:grid=data['times'];frames=data['note']
        boundaries,_,_=detect_changes(grid,frames,cal['selected_height']);_,support=clipped_pool(grid,frames,[center],.4,boundaries);support=support[0]
        ax.plot(pts-.5+np.arange(len(clip))/rate,clip,lw=.5,color='#444444');ax.axvspan(pts-.2,pts+.2,color='gray',alpha=.15,label='Fixed0.4s')
        ax.axvspan(support['start_s']+offset,support['end_s']+offset,color='green',alpha=.16,label='Actual clipped support')
        for t in boundaries+offset:
            if abs(t-pts)<.5:ax.axvline(t,color='red',ls='--',lw=1)
        ax.axvline(pts,color='black',ls=':',lw=.8);ax.set_title(f'{scope} tutorial PTS{pts:.0f}s / red = detected audio change, not reference');ax.legend(fontsize=7)
        if scope=='new':wavfile.write(assets/f'new_pts_{pts:.0f}_original.wav',rate,clip.astype(np.float32))
    axes[-1].set_xlabel('Video time (s)');fig.tight_layout();fig.savefig(assets/'supports.png',dpi=145);plt.close(fig)
    # New stem and original mixture listening aid, same252..256s, with spectrum.
    mix=ROOT/'dataset/audio_analysis/runs/new_250_266_mix_20261105_v1/original.wav';guitar=ROOT/'dataset/audio_analysis/runs/new_250_266_guitar_20261105_v1/htdemucs_6s/original/guitar.wav';fig,axes=plt.subplots(2,2,figsize=(12,6))
    for i,(name,path) in enumerate([('Mixture',mix),('Guitar estimate',guitar)]):
        rate,a=wavfile.read(path);a=a.mean(axis=1);clip=a[2*rate:6*rate];wavfile.write(assets/(name.replace(' ','_')+'_252_256.wav'),rate,clip.astype(np.float32));axes[i,0].plot(252+np.arange(len(clip))/rate,clip,lw=.4);axes[i,0].set_title(name+' /252-256s')
        win=a[3*rate-4096:3*rate+4096];freq=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));axes[i,1].plot(freq,20*np.log10(np.maximum(mag,1e-9)));axes[i,1].set_xlim(0,6000);axes[i,1].set_title(name+' /253s spectrum');axes[i,1].set_xlabel('Hz')
    fig.tight_layout();fig.savefig(assets/'new_audio.png',dpi=140);plt.close(fig)
    newrows=[]
    for r in new['rows']:
        preds=[]
        for m in METHODS:
            top=r['branches'][m]['top3'];preds.append(top[0]['concert_symbol'] if top else '보류')
        newrows.append('|'+str(r['reference']['pts'])+'|'+r['reference']['shape']+' → '+r['reference']['concert_symbol']+'|'+'|'.join(preds)+'|')
    tr=s['guitarset']['transition']['performed'];idmt=s['idmt']['transition']['nominal'];first=read(FIRST/'summary.json')['guitarset']['transition']['performed'];hrows=['|'+m+'|'+f'{pct(c):.2f}%'+'|' for m,c in holdout.items()]
    text=f'''# 코드 변화 후보로 시간창을 제한한 오디오 실험 — 2026-11-05

**기능 구현·검증과 새 영상 구간 확인을 완료했다.** 코드 전환 후보를 감지해0.2/0.4초 음 수집 창이 그 후보를 넘지 않게 했다.0.4초고정창대비잘못붙인확장코드는202→143건으로줄었지만전체정확도는42.80→41.88%로소폭하락했다. **변화 감지의 오탐이 많아 기본 경로로 승격하지 않았다.** 기존 고정창 경로는 보존했다.

## 구현한 방법

Basic Pitch 원음 입력·출력D2~E6·음활성문턱0.3·기존코드채점은고정했다. 활성음의PC분포를시점앞뒤각0.2초에서평균하고코사인거리의봉우리를변화후보로잡았다. 최소후보간격0.2초, prominence0.08, 양쪽활성합0.3 조건이다. 변화후보의양쪽을다른구간으로간주해기존max0.2/0.4초창만줄였다. 강제로코드를고르거나보류시키지는않았다.

추론 함수는 오디오 모델의 활성값·시각만 받는다. 정답 코드 경계는 평가에만 사용하며, 지판·손·화면 코드가 감지나 창 선택에 들어가지 않는다. 모델 자체가 보는 약2초문맥은 그대로라 시간창 제한으로 모든 전환 혼합이 사라지는 것은 아니다. 오프라인 중심창이므로 미래오디오도 사용한다.

첫버전(v1)은약한배경활성까지분포에합쳐서실제GuitarSet전환1,960개중3개만찾았다. 그결과를숨기지않고보존했다. v2는기존0.3음활성문턱미만을제외한뒤변화를계산했다. 감지높이만고정된7개값에서 **기존검증용BN3/Funk3곡23파일의전환F1**로선택했고{cal['selected_height']}가선택됐다. 새영상과IDMT성적으로문턱을고르지않았다. 추가신경망학습은없었다.

## 같은 시점·같은 채점 비교

GuitarSet178파일의같은4,850시점,IDMT기타6음색1,638시점을사용했다. 순간/고정창은이전결과와파일별집계가정확히일치했다. 아래7화음은7·maj7·m7·m7b5묶음이다. ‘잘못붙인확장코드’는참조가장/단화음일때근음은같지만사전에있는7·maj7·m7·m7b5·dim7·add9·6·m6등으로불필요한PC를추가한경우다. 모든종류의오답이나9/11/13전체의정밀도를뜻하지않는다.

|방식|상세 코드 top1|7화음 top1|잘못 붙인 확장코드|보류|기존9곳|새4곳|
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![같은 시점 비교와 새 구간 결과](../{assets.relative_to(ROOT).as_posix()}/comparison.png)

검증문턱조절에사용하지않은Jazz3/Rock3/SS3패턴36파일만분리한상세코드성적도보관했다. 이곡들은과거개발에서이미보았고기본Basic Pitch의GuitarSet학습이력도있으므로완전독립평가라고부르지않는다.

|방식|36파일 상세 top1|
|---|---:|
'''+ '\n'.join(hrows)+f'''

## 전환 후보 감지 성적

참조의근음/PC집합이바뀌는시각과예측후보를±0.2초안에서1:1대응시켰다. 같은코드의반복기호나같은음집합의베이스표기차이만으로전환을늘리지않았다. 아래오차는맞게대응된후보에한정한중앙절대오차이며실제코드출력의지연시간이나전체전환오차를뜻하지않는다.

- 실제GuitarSet: 정밀도{100*tr['precision']:.2f}%, 재현율{100*tr['recall']:.2f}%, 대응된후보중앙오차{1000*tr['median_abs_error_s']:.1f}ms. TP{tr['counts']['tp']}, FP{tr['counts']['fp']}, FN{tr['counts']['fn']}.
- IDMT합성기타: 정밀도{100*idmt['precision']:.2f}%, 재현율{100*idmt['recall']:.2f}%, 대응된후보중앙오차{1000*idmt['median_abs_error_s']:.1f}ms.

IDMT의분명한블록전환은잘찾지만실제연주의스트로크·아르페지오에따른음구성변화도경계로오인한다. 경계를너무많이만들면모아야할음을잘라보류가늘어날수있다. 이런상충이전체정확도하락과맞물리지만각오류의청음원인까지전수확정한것은아니다.

## 새 구간 선정과 참조 검수

**처음모델결과와원본프레임을보기전에250~266초,251/253/255/257/259/261/263/265초를고정했다.** 이후원본과앞뒤약0.208초를보고251·255초는전환중,263·265초는지속표시코드와다른끝부분멜로디/잔향이라제외했다. 제외를포함한계획·참조해시를첫새구간추론전에저장했다. 유효참조는4곳뿐이다. 좋은결과를얻으려고다른시점으로교체하지않았다.

새원음은같은영상에서샘플정합으로추출하고캐시된Demucs6소스모델로기타추정음을분리했다. 새분리음은아직사용자의별도청음검수를받지않았고다른악기누출가능성이있다. 참조는화면코드/TAB/다이어그램·보이는운지를대조한분석자판독이며표준튜닝과Capo.1을가정했다. 실제현접촉정답이나독립청음전사정답은아니다.

v1결과를본뒤검증곡으로v2문턱을보정했으므로 **새4곳은v1에는새평가였지만v2에는완전한블라인드테스트가아니다.** v2설정을그4곳의점수로선택하지는않았다. 세곳이Dm7인작고편중된표본이라는한계도있다.

|영상초|화면 운지 → 실음 참조|순간|고정0.2|고정0.4|경계0.2|경계0.4|
|---|---|---|---|---|---|---|
'''+ '\n'.join(newrows)+f'''

![미리 선정한 새8시점의 원본 — 제외점도 포함](../{FIRST.relative_to(ROOT).as_posix()}/new_interval_contact.png)

![새 구간 앞뒤 검수 —253초 포함](../{FIRST.relative_to(ROOT).as_posix()}/new_stability_0.png)

![259·261초 앞뒤 검수](../{FIRST.relative_to(ROOT).as_posix()}/new_stability_2.png)

## 원본과 실제 처리 창

![원음 파형과 실제 사용 창](../{assets.relative_to(ROOT).as_posix()}/supports.png)

회색은0.4초고정창,초록은실제경계제한창,빨간점선은 **검출한오디오변화후보**다. 정답코드경계선이아니다. 기존211초는Amaj7오류가A로개선됐지만223초Bbadd9오류는남았다. 새253초Dm7은모든방식이Dm으로판정해7음누락이해결되지않았다.

![새 원음·기타 추정음 파형과 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/new_audio.png)

새252~256초원음: ![혼합 원음](../{assets.relative_to(ROOT).as_posix()}/Mixture_252_256.wav)

같은구간기타추정음: ![기타 추정음](../{assets.relative_to(ROOT).as_posix()}/Guitar_estimate_252_256.wav)

257초중심원음: ![257초 원음](../{assets.relative_to(ROOT).as_posix()}/new_pts_257_original.wav)

253초중심원음: ![253초 원음](../{assets.relative_to(ROOT).as_posix()}/new_pts_253_original.wav)

새사진·음원은실제파일에서추출했으며생성형이미지나합성음으로검증근거를대체하지않았다.

## 연결·검증·결정

`export_temporal_audio.py --clip-at-changes --change-detector-config ...`로선택실행가능하게연결했다. 새250~266초의evidence.json/harmony.json을`dataset/audio_analysis/runs/new_250_266_change_pool_20261105_v2`에실제로생성했다. 원본영상source_id·250초오프셋·입력해시를유지했다. 원래개별음의지속시간을늘리거나confirmed음/현접촉을만들지않았다.

157개테스트통과. 변화검출·같은코드반복무변화·약한배경활성제외·반대코드차단·경계없을때기존max와동일·오디오/화성기존회귀를검사했다. 모델가중치와손·지판·기본채점은그대로다.

**고정0.2/0.4초를유지하고경계제한은선택적인비교경로로둔다.** 다음우선과제는추가모델학습보다스트로크/개별음변화와코드변화를구분해경계후보정밀도를높이는것이다. 고정창보다정확도와보류율까지함께좋아지기전에는기본으로적용하지않는다. 이미본새4곳을재튜닝용독립시험처럼반복해서쓰지않는다.

```powershell
python calibrate_audio_changes.py
python evaluate_change_aware_audio_v2.py
python report_change_aware_audio.py
python -m unittest test_audio_change_pool test_temporal_audio_pool test_oracle_chord_audit test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

기존완료결과는덮어쓰지않으며재실행은새출력경로가필요하다. v1/v2둘다보존했다. 검증곡문턱탐색은detector_calibration.json,시점별후보/실제창/평가는records, 새구간선정과제외는frozen_review_plan.json/new_references.json, 원본사진은v1/reference_frames에있다.
'''
    (ROOT/'docs/CHANGE_AWARE_AUDIO_REVIEW_2026-11-05.md').write_text(text,encoding='utf-8')
    (OUT/'deployment_decision.json').write_text(json.dumps(dict(status='comparison_only_not_default',reason='False extensions decrease but total accuracy and seventh accuracy regress; low real-performance boundary precision',fixed_paths_retained=True),indent=2),encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';previous=log.read_text(encoding='utf-8');marker='후속 코드 변화 경계 실험:'
    if marker not in previous:
        head,rest=previous.split('\n',1);log.write_text(head+'\n\n'+marker+' 오디오변화후보로0.2/0.4초창을제한하는기능을구현했다.새250~266초8곳사전선정후4곳참조확정.경계0.4초는가짜확장202→143건,전체42.80→41.88%로상충해미승격.새4곳은고정/경계0.4초모두3/4.검출정밀도30.64%가병목.157테스트통과. [원음·원본사진·새구간보고서](CHANGE_AWARE_AUDIO_REVIEW_2026-11-05.md).\n'+rest,encoding='utf-8')
    print('Change-aware audio report generated',flush=True)

if __name__=='__main__':main()
