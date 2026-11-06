"""Pretrained model integration report with timing, training-overlap and failure caveats."""
import json
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from scipy.io import wavfile
from evaluate_basic_pitch import ROOT,OUT,BASE,BRANCHES
from idmt_chords_benchmark import pcm_float

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));summary=read(OUT/'summary.json');tutorial=read(OUT/'tutorial.json')
    cut=read(BASE/'summary.json');raw=read(ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1/summary.json');raw_t=read(ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1/audit.json')['tutorial']['summary']
    assets=OUT/'report';assets.mkdir(exist_ok=True);pct=lambda c,k='top1':100*c.get(k,0)/max(1,c['evaluated'])
    rows=[];metrics=[]
    for name,mode,b in [('기존 피크 / 컷 없음','raw','peak_legacy'),('기존 피크 / 컷 사용','cut','peak')]:
        d=(raw if mode=='raw' else cut);g=d['guitarset']['branches'][b];idmt=d['idmt']['branches'][b]['nominal'];t=raw_t[b]['exact_top1'] if mode=='raw' else read(BASE/'tutorial.json')['summary'][b]['exact_top1']
        metrics.append((name,g,idmt,t));rows.append(f"|{name}|{pct(g['nominal']['counts']):.2f}%|{pct(g['performed']['counts']):.2f}%|{pct(g['performed']['counts'],'top3'):.2f}%|{pct(idmt['counts']):.2f}%|{t}/9|")
    for b in BRANCHES:
        g=summary['guitarset']['branches'][b];idmt=summary['idmt']['branches'][b]['nominal'];t=tutorial['summary'][b]['exact_top1'];name='모델 / '+('컷 없음' if b.startswith('raw') else '컷 사용')+' / '+('프레임' if b.endswith('frames') else '디코딩 음')
        metrics.append((name,g,idmt,t));rows.append(f"|{name}|{pct(g['nominal']['counts']):.2f}%|{pct(g['performed']['counts']):.2f}%|{pct(g['performed']['counts'],'top3'):.2f}%|{pct(idmt['counts']):.2f}%|{t}/9|")
    labels=['Peak raw','Peak cut','Model raw/frame','Model raw/event','Model cut/frame','Model cut/event'];fig,axes=plt.subplots(1,3,figsize=(15,4.5))
    for ax,which in zip(axes,['performed','idmt','tutorial']):
        vals=[pct(g['performed']['counts']) if which=='performed' else pct(d['counts']) if which=='idmt' else 100*t/9 for _,g,d,t in metrics]
        bars=ax.bar(labels,vals,color=['#888888','#bbbbbb','#1b9e77','#66c2a5','#377eb8','#80b1d3']);ax.bar_label(bars,fmt='%.1f',fontsize=8);ax.tick_params(axis='x',rotation=50);ax.set_ylim(0,100);ax.set_ylabel('Exact chord top1 (%)');ax.set_title({'performed':'GuitarSet / training-corpus diagnostic','idmt':'IDMT synthetic guitar','tutorial':'Tutorial / 9 development references'}[which])
    fig.suptitle('Same evaluation timestamps + unchanged chord scoring; model has longer audio context');fig.tight_layout();fig.savefig(assets/'accuracy.png',dpi=145);plt.close(fig)
    qrows=[]
    for q in ['major','minor','7','maj7','m7','m7b5']:
        vals=[]
        for _,g,_,_ in metrics:
            c=g['performed']['per_quality'][q];vals.append(f"{pct(c):.2f}% ({c['top1']}/{c['evaluated']})")
        qrows.append('|'+q+'|'+'|'.join(vals)+'|')
    pcrows=[]
    for b in BRANCHES:
        p=summary['guitarset']['branches'][b]['note_pc'];pcrows.append('|'+b+'|'+'|'.join(f'{100*p[k]:.2f}%' for k in ['precision','recall','f1'])+'|')
    # Actual decoded notes are shown and rendered as explicitly synthetic sine tones.
    source=read(OUT/'predictions/tutorial_raw.json')['audio'];rate,a=wavfile.read(source);a=pcm_float(a).mean(axis=1)
    wavfile.write(assets/'tutorial_original_198_202.wav',rate,a[4*rate:8*rate].astype(np.float32))
    fig,axes=plt.subplots(3,1,figsize=(12,8),sharex=True);axes[0].plot(194+np.arange(len(a))/rate,a,lw=.4);axes[0].set_ylabel('Original amplitude')
    for ax,mode in zip(axes[1:],['raw','cut']):
        meta=read(OUT/f'predictions/tutorial_{mode}.json');events=meta['note_events'];synth=np.zeros(4*22050)
        for e in events:
            ax.plot([194+e['start_s'],194+e['end_s']],[e['midi'],e['midi']],color='#297fb8',lw=2)
            lo=max(4.,e['start_s']);hi=min(8.,e['end_s'])
            if lo>=hi:continue
            i=round((lo-4)*22050);j=min(len(synth),round((hi-4)*22050));t=np.arange(j-i)/22050
            if not len(t):continue
            ramp=min(220,len(t)//2);envelope=np.ones(len(t))
            if ramp:envelope[:ramp]=np.linspace(0,1,ramp);envelope[-ramp:]=np.linspace(1,0,ramp)
            synth[i:j]+=.07*e['amplitude']*np.sin(2*np.pi*440*2**((e['midi']-69)/12)*t)*envelope
        wavfile.write(assets/f'tutorial_{mode}_notes_sine_198_202.wav',22050,synth.astype(np.float32));ax.set_ylabel('Estimated MIDI');ax.set_ylim(36,90);ax.set_title('Basic Pitch decoded notes / '+mode+' input')
    axes[-1].set_xlabel('Source video time (s)');axes[-1].set_xlim(194,226);fig.tight_layout();fig.savefig(assets/'tutorial_notes.png',dpi=145);plt.close(fig)
    sf,sa=plt.subplots(figsize=(10,3));win=a[5*rate-4096:5*rate+4096];f=np.fft.rfftfreq(8192,1/rate);mag=np.abs(np.fft.rfft(win*np.hanning(8192)));sa.plot(f,20*np.log10(np.maximum(mag,1e-9)));sa.set_xlim(0,6000);sa.set_title('Original guitar estimate / 199s center window');sa.set_xlabel('Frequency (Hz)');sa.set_ylabel('Uncalibrated dB');sf.tight_layout();sf.savefig(assets/'spectrum.png',dpi=140);plt.close(sf)
    model=read(OUT/'predictions/model.json');audit=read(OUT/'audit.json');toprows=[]
    for r in tutorial['rows']:
        preds=[]
        for b in BRANCHES:
            top=r['branches'][b]['top3'];preds.append(top[0]['concert_symbol'] if top else '보류')
        toprows.append('|'+str(r['reference']['pts'])+'|'+r['reference']['concert_symbol']+'|'+'|'.join(preds)+'|')
    timings=[read(p)['elapsed_s'] for p in (OUT/'predictions').glob('*.json') if p.name!='model.json']
    text=f'''# 사전학습 Basic Pitch 오디오 모델 연결 — 2026-11-05

Spotify **Basic Pitch0.4.0의 사전학습 ONNX 모델**을 설치하고 실제 추론·코드 후보 연결·전체 비교까지 완료했다. 자체 학습은 하지 않았다. 손·지판·코드 채점·비전 가중치는 변경하지 않았다. 모델 출력은 음 후보이며 실제 현 접촉·뮤트·개방현 정답이 아니다.

## 설치와 모델

별도 `.venv-audio-model` 환경에 설치했다. ONNX Runtime {model['runtime']}를 CPU 4스레드로 실행하며 기존 환경은 변경하지 않았다. resampy 호환성을 위해 setuptools 80.9.0을 고정했다. 설치 버전 목록은 requirements.lock.txt에 있다.

모델은공식패키지에동봉된 `{Path(model['model']).name}`, {model['size_bytes']:,}바이트, SHA256 `{model['sha256']}`. [공식 프로젝트](https://github.com/spotify/basic-pitch)와 [공식 추론 구현](https://github.com/spotify/basic-pitch/blob/main/basic_pitch/inference.py)의 모델·전처리·기본 디코더를 사용했다. 패키지0.4.0의 출력 시간 문제는 입력 샘플 위치로 연결해 해결했고 패키지 자체는 수정하지 않았다. 패키지의Apache2.0 라이선스를 유지한다. 저장소상세와 연구설명은 공식 프로젝트 참조.

**GuitarSet은 이 모델의 학습 자료 중 하나다.** 아래 GuitarSet 성적은 연결과 오류 진단에만 사용한다. 독립 평가나 미지 연주자에 대한 정확도를 뜻하지 않는다. 여기서 재학습하거나 문턱을 최적화하지 않았다. IDMT는 합성 음색이고 튜토리얼은 기존의 작은 개발 표본이라는 한계도 있다.

## 입력·후처리·평가 조건

GuitarSet 반주 180파일, IDMT 기타 6음색, 현재 기타 추정 트랙 32초를 **컷 없음/컷 사용**으로 각각 추론했다. 총 187개 소스 × 2 = 374개 결과와 MIDI를 저장했다. 컷은 기존과 같은 전체 파일 FFT D2~E6 컷이며 모델 입력 전에 적용한다. **컷 없는 모델도 최종 음 후보는 D2~E6로 제한한다.** 높은 배음은 음을 추정하는 입력 근거로만 활용한다.

프레임 방식은 모델의 note activation이 기본 문턱 0.3 이상인 음을 피치클래스로 합친다. 디코딩 음 방식은 공식 onset 0.5 / frame 0.3 / 최소 11프레임 설정으로 얻은 음이 해당 시각에 활성인지 판단한다. 둘 다 기존 coverage 코드 채점을 사용한다. 활성 피치클래스가 3개 미만이면 기존 채점기가 보류하므로, 모델이 2음을 잘 찾아도 코드 후보가 없을 수 있다. 모델 점수는 보정된 확률이 아니다.

GuitarSet주결과는기존과같은178파일·안정창4,886개, IDMT1,638중심시점, 튜토리얼9시점이다. 주석과정답은추론작업파일에넣지않았다. 동일평가시각·동일코드사전·동일채점으로비교하지만 **모델은약2초문맥을보고기존피크는8192샘플창을보므로 순수 특징 하나만 바꾼 실험은 아니다.** 초기 v1은 공식 출력 시간 변환에서546초 음원의 마지막 시간이542.338초로 잘리는 문제가 확인돼 평가를 중단했다. v2는 입력 창의 실제 시작 샘플 위치·256샘플 홉·양쪽15프레임 제거로 시간을 연결하며 입력 길이만큼 출력도 유지한다. 정답에 맞춘 시간 늘이기나 오프셋 피팅은 하지 않았다. 이전 v1 결과는 보존하되 성적으로 사용하지 않는다.

## 결과

|방식|GuitarSet 기본 top1|상세 전체 top1|상세 전체 top3|IDMT 기타 top1|튜토리얼 top1|
|---|---:|---:|---:|---:|---:|
'''+ '\n'.join(rows)+f'''

![기존 방식과 모델 비교](../{assets.relative_to(ROOT).as_posix()}/accuracy.png)

다음 오디오 개발은 **컷 없는 입력 + 모델 프레임 출력 + D2~E6 음 후보 제한**을 우선 경로로 사용한다. 모델 입력까지 자르면 IDMT와 튜토리얼 양쪽에서 성적이 떨어졌다. 다만 튜토리얼은9곳뿐이므로 이 선택을 일반적인 최적 설정이라고 주장하지 않는다. 기존 FFT 경로와 컷 사용 경로는 비교용으로 보존했다.

모델이 모든 문제를 해결한 것은 아니다. GuitarSet 진단에서 장·단화음은 개선됐지만 maj7·m7·m7b5는 기존보다 낮고, 튜토리얼에서도7음 누락과 보류가 남았다. 따라서 모델 연결 완료와7화음 문제 해결을 구분한다. 다음 검증은 새 연주 구간에서 모델의 음 후보를 확인하고, 그 후보가 맞는데도 기존 채점이 잘못 고르는 사례를 분리하는 것이다. 새 모델을 재학습하거나 문턱을 바꾸기 전에 이 연결 결과를 기준선으로 삼는다.

|GuitarSet 상세 코드|기존/컷 없음|기존/컷 사용|모델 raw/frame|모델 raw/event|모델 cut/frame|모델 cut/event|
|---|---:|---:|---:|---:|---:|---:|
'''+ '\n'.join(qrows)+'''

GuitarSet note_midi 피치클래스 집합과5,421시점에서 비교했다. 프레임·디코딩음의음활성판정은위에고정한공식기본설정을사용한다. 단일음높이·현·온셋F1과는다르다.

|모델 입력/표현|PC 정밀도|PC 재현율|PC F1|
|---|---:|---:|---:|
'''+ '\n'.join(pcrows)+f'''

## 실제 튜토리얼의 성공·보류·실패

|영상초|기존 참조 정답|raw/frame|raw/event|cut/frame|cut/event|
|---|---|---|---|---|---|
'''+ '\n'.join(toprows)+f'''

참조는기존화면코드·TAB·운지대조및Capo.1을반영한개발용9곳이다. 독립청음전사·두번째사람검증이아니다. 모델도보류와7음누락이남으므로 ‘7화음/텐션해결’이라고표현하지않는다. 사전이9·11·13전체를표현하지못하는제약도그대로다.

![원본 파형과 모델의 실제 음 추정](../{assets.relative_to(ROOT).as_posix()}/tutorial_notes.png)

![199초 원음 스펙트럼](../{assets.relative_to(ROOT).as_posix()}/spectrum.png)

원본기타추정음198~202초: ![원본](../{assets.relative_to(ROOT).as_posix()}/tutorial_original_198_202.wav)

컷없는모델의음후보를사인파로재생: ![합성검수음](../{assets.relative_to(ROOT).as_posix()}/tutorial_raw_notes_sine_198_202.wav)

컷사용모델의음후보를사인파로재생: ![합성검수음](../{assets.relative_to(ROOT).as_posix()}/tutorial_cut_notes_sine_198_202.wav)

합성검수음은추정된음높이·시작·끝을들어보는도구이며 기타분리음이나 실제연주복원음이아니다. 음색과음량이원음과다르므로 소리가비슷하다는이유만으로정확도를판단하지않는다.

![195초 기존 참조 원본](../{Path(tutorial['rows'][0]['reference']['image']).relative_to(ROOT).as_posix()})

## 실제 파이프라인 연결

`basic_pitch_worker.py`는라벨없이모델추론만한다. `basic_pitch_adapter.py`는모델의88음출력을D2~E6피치클래스입력으로변환한다. `export_basic_pitch_evidence.py`로현재계약인`guitar_evidence.v1`을만들고 기존`provisional_audio_harmony`까지실제로실행했다.

현재튜토리얼의연결결과는`dataset/audio_analysis/runs/barre_basic_pitch_raw_20261105_v2`와`barre_basic_pitch_cut_20261105_v2`의evidence.json/harmony.json에있다. 원본영상source_id와194초오프셋을명시했고입력해시를검사했다. confirmed note·현번호·접촉판정을만들지않았다. 다른부분의기본실행경로는바꾸지않고모델경로를명시적으로사용할수있게했다.

## 검증과 재현

140개 테스트를 통과했다. 모델 그리드, 기본 문턱, D2/E6 경계, 옥타브 병합, 음 끝의 처리, 무음, 범위 밖 시각 거절, 영상 오프셋, 확정 음으로 승격하지 않는 조건을 확인했다. 기존 오디오·화성 회귀 검사도 통과했다.

374개 출력의 시간 증가·끝부분 보존·평가 시각의 근접성을 전수 검사했다. 최대 마지막 창 간격은{1000*audit['max_tail_gap_s']:.2f}ms, 평가 시각과 최근접 모델 프레임 차이는 최대{1000*audit['max_evaluation_frame_delta_s']:.2f}ms다. 합성 시험음의1·10·20초 시작점을 검증한 최대 오차는{1000*max(v['max_onset_abs_error_s'] for v in audit['clock_probe'].values()):.2f}ms였다. 이 시험으로 실제 음악의 모든 온셋 정확도를 보장하지는 않는다. 정답을 보고 시계를 보정하지 않았다.

추론 누적 처리 시간은{sum(timings):.1f}초다. 파일 입출력·필터·기본 후처리·첫 JIT 시간이 포함돼 반복 속도 벤치마크로 해석하지 않는다. `run_pretrained_audio.py`의 원음→모델→evidence.json→harmony.json 전체 명령도 실제 실행해 확인했다.

```powershell
.venv-audio-model/Scripts/python.exe basic_pitch_worker.py --tasks dataset/integration_review/runs/basic_pitch_20261105_v2/tasks_all.json --output dataset/integration_review/runs/basic_pitch_20261105_v2/predictions
python evaluate_basic_pitch.py
python audit_basic_pitch.py
python report_basic_pitch.py
python -m unittest test_basic_pitch_clock test_basic_pitch_adapter test_cut_audio_features test_harmonic_chord_features test_harmonic_chord_benchmark test_idmt_chords_benchmark test_chord_score_variants test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q
```

일반 오디오 파일에는 다음처럼 모델 경로를 명시적으로 실행한다. `--input-mode raw`는 파형 컷 없이 모델에 주되 출력 음 후보를 D2~E6로 제한한다. `cut`은 입력 파형도 자른다. 기존 FFT 경로를 자동으로 대체하지 않는다.

```powershell
python run_pretrained_audio.py --audio PATH_TO_WAV --source-id SOURCE_ID --offset VIDEO_START_SECONDS --input-mode raw --output NEW_OUTPUT_DIRECTORY
```

완료된 평가 파일은 덮어쓰지 않는다. inference는 모델·입력 해시가 일치하는 기존 추론만 재사용한다. 모델/버전/소스 해시는 predictions/model.json, 평가 조건은 evaluation_config.json, 입력/음 후보는 각 추론 JSON, 세부 성적은 records에 있다. 기존 자료는 보존했다. 시간 문제가 있던 v1에는 superseded 표시를 붙였고, 내보내기 명령에서도 해당 결과를 거절한다.
'''
    (ROOT/'docs/BASIC_PITCH_MODEL_REVIEW_2026-11-05.md').write_text(text,encoding='utf-8')
    log=ROOT/'docs/DEVLOG_2026-11-05_END_OF_DAY.md';old=log.read_text(encoding='utf-8');marker='후속 사전학습 오디오 모델:'
    if marker not in old:
        head,rest=old.split('\n',1);log.write_text(head+'\n\n'+marker+' BasicPitch0.4.0 ONNX를격리환경에설치해187소스×raw/cut추론및기존화성입력연결완료.140테스트통과. GuitarSet은학습자료중하나라독립성적이아님을명시했다. [원음·모델음후보·성적](BASIC_PITCH_MODEL_REVIEW_2026-11-05.md).\n'+rest,encoding='utf-8')
    print('Report generated',flush=True)

if __name__=='__main__':main()
