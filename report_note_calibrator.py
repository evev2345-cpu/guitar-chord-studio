"""Training review with held-out composition results and negative external tests."""
import json
import hashlib
from collections import Counter
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from train_audio_note_calibrator import ROOT,OUT,PRED
from audio_note_calibrator import corrected_probabilities

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));train=read(OUT/'training_result.json');summary=read(OUT/'evaluation_summary.json');tutorial=read(OUT/'tutorial.json');manifest=read(OUT/'split_manifest.json')
    assert hashlib.sha256((OUT/'weights.npz').read_bytes()).hexdigest()==train['weights_sha256']
    assets=OUT/'report';assets.mkdir(exist_ok=True);names=['baseline_default','baseline_calibrated','corrected_calibrated'];labels=['Original .30','Original val threshold','Trained correction']
    pct=lambda c:100*c['top1']/c['evaluated'];fig,axes=plt.subplots(1,3,figsize=(14,4.5))
    for ax,scope in zip(axes,['test','idmt_external','tutorial']):
        if scope=='tutorial':values=[100*tutorial['summary'][n]['exact_top1']/9 for n in names]
        else:values=[pct(summary[scope]['branches'][n]['performed' if scope=='test' else 'nominal']['counts']) for n in names]
        bars=ax.bar(labels,values,color=['#777777','#7db6cf','#e4933d']);ax.bar_label(bars,fmt='%.2f%%',fontsize=8);ax.tick_params(axis='x',rotation=25);ax.set_ylim(0,80);ax.set_title({'test':'Unseen compositions for correction training','idmt_external':'IDMT synthetic guitar / never trained','tutorial':'Tutorial / never trained, n=9'}[scope]);ax.set_ylabel('Exact chord top1 (%)')
    fig.suptitle('Training completed; correction is not promoted because chord accuracy regressed');fig.tight_layout();fig.savefig(assets/'comparison.png',dpi=145);plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(11,4));history=train['history'];axes[0].plot([h['epoch'] for h in history],[h['train_loss'] for h in history],label='Train loss + regularizer');axes[0].plot([h['epoch'] for h in history],[h['validation_bce'] for h in history],label='Validation BCE');axes[0].legend();axes[0].set_xlabel('Epoch');axes[0].set_title('Training/validation only; test not used for selection')
    metrics=train['splits']['test']
    for j,k in enumerate(['precision','recall','f1']):axes[1].bar(np.arange(3)+(j-1)*.25,[100*metrics[n][k] for n in names],.25,label=k)
    axes[1].set_xticks(np.arange(3),labels,rotation=15);axes[1].legend();axes[1].set_ylim(0,100);axes[1].set_title('Held-out compositions / exact MIDI note sets');fig.tight_layout();fig.savefig(assets/'training.png',dpi=145);plt.close(fig)
    with np.load(OUT/'weights.npz') as d:weights={k:d[k] for k in d.files}
    with np.load(PRED/'tutorial_raw.npz') as d:times=d['times'];original=d['note'][:,17:68]
    corrected=corrected_probabilities(original,weights);fig,axes=plt.subplots(2,1,figsize=(12,5),sharex=True)
    for ax,title,values,threshold in zip(axes,['Original pretrained note activations','Trained correction; validation threshold'],[original,corrected],[.3,train['selected_thresholds']['corrected']]):
        ax.imshow(np.where(values>=threshold,values,0).T,origin='lower',aspect='auto',extent=[194+times[0],194+times[-1],37.5,88.5],vmin=0,vmax=1,cmap='magma');ax.set_title(title);ax.set_ylabel('MIDI candidate')
    axes[-1].set_xlim(198,202);axes[-1].set_xlabel('Source video time (s)');fig.tight_layout();fig.savefig(assets/'tutorial_candidates.png',dpi=145);plt.close(fig)
    source=read(PRED/'tutorial_raw.json')['audio'];rate,x=wavfile.read(source);x=x.mean(axis=1);wavfile.write(assets/'original_198_202.wav',rate,x[4*rate:8*rate].astype(np.float32))
    # Listening aid for thresholded frame estimates, explicitly synthetic and not a restored guitar.
    sr=22050;t=np.arange(4*sr)/sr+4;index=np.searchsorted(times,t).clip(0,len(times)-1)
    for name,values,threshold in [('before',original,.3),('after',corrected,train['selected_thresholds']['corrected'])]:
        synth=np.zeros(len(t))
        for col,midi in enumerate(range(38,89)):
            activation=values[index,col];amp=np.where(activation>=threshold,activation,0.)
            synth+=.035*amp*np.sin(2*np.pi*440*2**((midi-69)/12)*(t-4))
        wavfile.write(assets/f'{name}_candidate_sine.wav',sr,synth.astype(np.float32))
    # Original waveform/spectrum from actual pixels/audio, no generated evidence.
    fig,axes=plt.subplots(1,2,figsize=(12,3.5));axes[0].plot(198+np.arange(4*rate)/rate,x[4*rate:8*rate],lw=.4);axes[0].set_title('Original guitar estimate /198-202s');win=x[5*rate-4096:5*rate+4096];f=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));axes[1].plot(f,20*np.log10(np.maximum(mag,1e-9)));axes[1].set_xlim(0,6000);axes[1].set_title('199s original spectrum');axes[1].set_xlabel('Hz');fig.tight_layout();fig.savefig(assets/'original.png',dpi=140);plt.close(fig)
    splitcounts=Counter(r['split'] for r in manifest);rows=[];chordrows=[]
    for name in names:
        m=metrics[name];rows.append('|'+name+'|'+'|'.join(f'{100*m[k]:.2f}%' for k in ['precision','recall','f1'])+'|')
        chordrows.append('|'+name+'|'+ '|'.join([f"{pct(summary['test']['branches'][name]['performed']['counts']):.2f}%",f"{pct(summary['idmt_external']['branches'][name]['nominal']['counts']):.2f}%",f"{tutorial['summary'][name]['exact_top1']}/9"])+'|')
    text=f'''# 오디오 음 후보 보정 모델 학습·보정 결과 — 2026-11-05

**실제 학습과 보정을 완료했지만, 이번 보정 모델은 기본 경로에 채택하지 않았다.** 학습에서 뺀 곡 패턴의 음높이 F1은81.42→81.57%로 소폭 개선됐으나 코드 정확도와 IDMT·튜토리얼에서 퇴보했다. 원래 Basic Pitch 모델은 그대로 유지한다. 결과를 좋게 보이게 하려고 평가 뒤 설정을 다시 바꾸지 않았다.

## 학습한 대상

Basic Pitch ONNX 가중치는 동결했다. 그 출력 중D2~E6의51개 음 활성값을 받아 보정하는 **51→32ReLU→51 잔차 신경망,3,347개 파라미터**를 새로 학습했다. 원 모델 전체의 미세조정과는 다르다. 보정된 음 확률값을 기존 피치클래스 입력으로 바꾸며 코드 채점은 그대로다. 손·지판·현 접촉 판정은 변경하지 않았다.

GuitarSet의6현 note_midi를 합쳐 시간별 실제 음높이 집합을 정답으로 썼다. 코드명·IDMT·튜토리얼 정답은 학습에 넣지 않았다. 기본 모델의 약104ms 간격 출력, 각 파일 처음/끝0.2초 제외, 알려진 시간 오류2파일 제외 조건이다. Adam 학습률0.001, 최대40epoch, validation BCE 체크포인트 선택, 과적합 억제항과6epoch patience를 미리 고정했다. 이번 실행은40epoch에서 종료했고 최선 체크포인트도{train['best_epoch']}epoch였다. CPU에서 학습했고 패키지를 추가 설치하지 않았다.

## 분할과 누수 한계

같은 진행의 다른 조·속도·연주자를 분리하지 않고 **곡 패턴 전체를 한 분할에 묶었다.** 학습{splitcounts['train']}파일, 보정/검증{splitcounts['validation']}파일, 최종 평가{splitcounts['test']}파일이다. 학습은각장르패턴1·2, 검증은BN3/Funk3, 평가는Jazz3/Rock3/SS3이다. 패턴 집합이 서로 겹치지 않는 것을 검사했다. 연주자 자체는 분할 사이에 겹친다.

**원래 Basic Pitch가 GuitarSet을 학습에 사용했다는 한계는 그대로다.** ‘평가에서 뺀 곡’은 이번 보정 학습에서만 뺐다는 뜻이며, 원 모델까지 포함한 완전히 새로운 자료라는 주장은 하지 않는다. 과거 개발에서 GuitarSet·IDMT·튜토리얼 성적도 이미 본 상태다. IDMT와튜토리얼은이번학습·문턱선택에는사용하지않았다.

문턱은검증셋에서만0.15~0.50의고정8개값을비교해선택했다. 원 모델에는{train['selected_thresholds']['baseline']}, 보정 모델에는{train['selected_thresholds']['corrected']}가선택됐다. ‘원모델문턱만보정’ 대조군을 두어학습효과와문턱효과를구분했다. 테스트결과를보고문턱이나체크포인트를재선택하지않았다.

## 학습에서 뺀 곡의 음높이 성적

아래는11,256시점의 **정확한 MIDI 음높이 집합** 비교이며, 옥타브를 합친 피치클래스F1이나온셋F1이아니다. 앞선보고서의PC F1과직접비교하면안된다.

|방식|정밀도|재현율|F1|
|---|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![학습 곡선과 음높이 성적](../{assets.relative_to(ROOT).as_posix()}/training.png)

정밀도는79.77→83.24%로올랐지만재현율은83.14→79.97%로낮아졌다. 전체음높이F1의이득은약0.15%p다. 부드럽고약한실제음도더제거하는보수적인보정이됐다는근거다.

## 기존 코드 채점까지 연결한 결과

|방식|보정 학습 미사용곡 상세코드 top1|IDMT 기타 top1|튜토리얼9곳|
|---|---:|---:|---:|
'''+ '\n'.join(chordrows)+f'''

![코드 정확도 — 실패 포함](../{assets.relative_to(ROOT).as_posix()}/comparison.png)

코드 평가는 이전과 같은 시점·같은 사전·같은 기존 coverage 채점이다. 보정 전 기본 모델의 파일별 집계가 이전 결과와 정확히 재현되는지도 검사했다. 평가 패턴의 상세 코드1위는38.46→35.11%, IDMT는65.14→50.55%, 튜토리얼은5/9→4/9로 하락했다. IDMT에서 음색이 달라지면 보정이 크게 퇴보하므로 이번 가중치를 기본으로 적용할 근거가 없다.

**음높이 F1을 조금 높이는 것과 코드 구성음을 잘 보존하는 것은 같은 목표가 아니었다.** 약한 구성음을 줄이면 후보 과검출은 줄지만 7음 등 실제 구성음을 함께 잃을 수 있다. 이는 현재 결과의 해석이며 모든 오류의 원인을 확정한 것은 아니다.

## 실제 튜토리얼 비교와 듣기

![같은 원음에서 보정 전후 음 활성 후보](../{assets.relative_to(ROOT).as_posix()}/tutorial_candidates.png)

밝은 칸은기본문턱을넘은모델후보이며사람검수정답이아니다. 입력은동일한컷없는기타추정트랙이고출력음역만D2~E6이다.

![원본 파형과 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/original.png)

원본198~202초: ![원음](../{assets.relative_to(ROOT).as_posix()}/original_198_202.wav)

보정 전 후보 사인파: ![보정전 합성](../{assets.relative_to(ROOT).as_posix()}/before_candidate_sine.wav)

보정 후 후보 사인파: ![보정후 합성](../{assets.relative_to(ROOT).as_posix()}/after_candidate_sine.wav)

사인파는모델후보의음높이를들을수있게만든검수도구다. 실제기타소리복원이나새분리음이아니다. 같은원음을분석했고보정모델이원본파형을변형하지않는다.

## 보관·검증·결정

weights.npz에실제학습가중치를저장했다. SHA256 `{train['weights_sha256']}`. 설정·분할파일·예측및주석해시·epoch별손실·검증문턱탐색·분할별성적을같은실행폴더에보관했다. inference는PyTorch없이NumPy로도실행할수있게했다. **기존모델을덮어쓰지않았고이보정을기본경로에연결하지않았다.**

144개회귀/신규테스트통과. 초기잔차0일때원모델값보존, 옥타브병합, 무음, 패턴별분할, 문턱선택을검사했다. 실제평가에서기존모델성적전수재현도통과했다.

```powershell
python train_audio_note_calibrator.py
python evaluate_note_calibrator.py
python report_note_calibrator.py
python -m unittest test_audio_note_calibrator test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

실행기는기존결과덮어쓰기를거절한다. 새학습은새OUT경로로실행해야한다. 테스트를여러번보고좋은설정을고르면더이상최종평가가아니므로이번테스트결과를새하이퍼파라미터선택에사용하지않는다.

다음 학습을 진행한다면 모델 출력값만 만지는 보정보다 원래 음향 특징을 보는 모델을 검토할 필요가 있다. 코드 구성음 보존과 음색 일반화를 평가 목표로 넣고 새로운 검증 자료를 확보해야 한다. 이번 결과만으로 전체 모델 미세조정이 성공할 것이라고 단정하지 않는다.
'''
    (ROOT/'docs/AUDIO_NOTE_CALIBRATION_TRAINING_2026-11-05.md').write_text(text,encoding='utf-8')
    (OUT/'deployment_decision.json').write_text(json.dumps(dict(status='not_promoted',active_path='Unmodified pretrained Basic Pitch raw-input frames',
        reason='Held-out correction compositions chord accuracy and external IDMT/tutorial regressions despite tiny note-F1 gain',weights_sha256=train['weights_sha256']),indent=2),encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 보정 모델 학습:'
    if marker not in old:
        head,rest=old.split('\n',1);log.write_text(head+'\n\n'+marker+' 3,347파라미터 음후보잔차모델을GuitarSet곡패턴분할로40epoch학습했다. 평가음높이F1은81.42→81.57%였으나상세코드38.46→35.11%,IDMT65.14→50.55%,튜토리얼5/9→4/9로퇴보해미채택.144테스트통과. [학습·실패·원음비교](AUDIO_NOTE_CALIBRATION_TRAINING_2026-11-05.md).\n'+rest,encoding='utf-8')
    print('Training review generated',flush=True)

if __name__=='__main__':main()
