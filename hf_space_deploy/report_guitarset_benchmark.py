"""Summarize the completed frozen GuitarSet run and render real error evidence."""
from collections import Counter
import json
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy import signal
from guitarset_benchmark import TEMPLATES,parse_chord
from joint_evidence_review import ROOT,read

FOLDER=ROOT/'dataset/integration_review/runs/guitarset_benchmark_20261105_v1'


def main():
    summary=read(FOLDER/'summary.json');records=[read(p) for p in sorted((FOLDER/'records').glob('*.json'))]
    records=[r for r in records if not r['known_timing_issue']]
    errors={}
    for branch in ['uncut','cut']:
        count=Counter()
        for record in records:
            for frame in record['branches'][branch]['nominal']['frames']:
                if frame['correct_top1']:continue
                top=frame['top3']
                if not top:count['abstained']+=1;continue
                pred=top[0];target=parse_chord(frame['reference'])
                if pred['root_pc']!=target['root_pc']:count['wrong_root']+=1;continue
                template=next(t for t in TEMPLATES if t['root_pc']==pred['root_pc'] and t['quality']==pred['quality'])
                pcs=set(template['pcs']);ref=set(frame['reference_pcs'])
                if pcs>ref:count['same_root_extra_pitch_classes']+=1
                elif pcs<ref:count['same_root_missing_pitch_classes']+=1
                else:count['same_root_other_pitch_class_difference']+=1
        errors[branch]=dict(count)
    (FOLDER/'error_categories.json').write_text(json.dumps(errors,indent=2),encoding='utf-8')
    primary=summary['scopes']['primary_without_known_timing']
    render(summary,records)
    record=records[0];rate,x=wavfile.read(record['audio_file'])
    wavfile.write(FOLDER/'example_original_0_8.wav',rate,x[:rate*8])
    from sweep_bandcut_vision_weights import band_cut
    cut=band_cut(x.astype(float)/32768,rate)
    wavfile.write(FOLDER/'example_cut_0_8.wav',rate,cut[:rate*8].astype(np.float32))
    pct=lambda value:f'{value*100:.2f}%'
    lines=['# GuitarSet 반주180개 오디오 기준 성적표 — 2026-11-05','',
        f"전체{summary['processed_files']}개/약{summary['processed_duration_s']/3600:.2f}시간을 실행했다. 주 성적표는 공식 시간오류2개를 제외한{primary['files']}개다. 학습·튜닝·비전 합성은 하지 않았다.",'',
        '## 코드 결과','',
        '| 기준 | 컷 전1위 | D2~E6 컷1위 | 컷 전상위3 | 컷 후상위3 |','|---|---:|---:|---:|---:|']
    for layer,label in [('nominal','악보상 기본 코드'),('performed','상세 연주 코드: 전체 정답'),('representable','상세 연주 코드: 사전 표현 가능만')]:
        a=primary['branches']['uncut']['performed' if layer=='representable' else layer]
        b=primary['branches']['cut']['performed' if layer=='representable' else layer]
        k1='representable_top1' if layer=='representable' else 'top1';k3='representable_top3' if layer=='representable' else 'top3'
        lines.append(f'|{label}|{pct(a[k1])}|{pct(b[k1])}|{pct(a[k3])}|{pct(b[k3])}|')
    a,b=[primary['branches'][name] for name in ['uncut','cut']]
    lines += ['',f"컷으로 기본 코드1위가 오른 폭은{(b['nominal']['top1']-a['nominal']['top1'])*100:.2f}%p다. 컷 후 상세 코드의 사전 표현 가능 정답만 봐도1위{pct(b['performed']['representable_top1'])}이므로, 표현 불가 코드만이 낮은 점수의 원인은 아니다. 현재 단순 피크/coverage 점수의 기준 성능은 낮고, 대역 컷만으로 크게 개선되지 않았다.",'',
        f"기본 코드 채점 시점 수는 컷 전{a['nominal']['counts']['evaluated']:,}개, 컷 후{b['nominal']['counts']['evaluated']:,}개다. 상세 코드 중 현 사전으로 정확히 표현 가능한 비율은{pct(a['performed']['dictionary_coverage'])}다. 표현 불가 정답도 전체 상세 정확도 분모에 남겼고, 표현 가능 정답만의 결과는 별도로 표시했다. 모르는 라벨은 단순화하지 않고 unparsed로 기록했다.",'',
        f"기본 코드 근음1위 일치는 컷 전{pct(a['nominal']['root_top1'])}, 컷 후{pct(b['nominal']['root_top1'])}다. 녹음별 정확도를 동일 가중 평균한 기본 코드1위는{pct(a['nominal']['file_macro_top1'])} / {pct(b['nominal']['file_macro_top1'])}다. 위 주 표는0.1초 샘플 시점 수 기준의 micro 집계다.",'',
        '## 음표 대조 진단','',
        '피크를 기본음 후보로 해석했을 때, 주석의 해당 중심시각 활성 음표와 비교했다. 음표 이벤트 전사/onset F1이나 실제로 울린 모든 잔향의 정답 검증은 아니다. 같은 MIDI가 여러 줄에 있어도 한 번만 센다. 소수 MIDI 피치는 반올림하고 옥타브를 구분했다. 코드 전환을 제외하는 코드 평가와 달리 음표 비교에는 중심시각 전체를 사용했다.','',
        '| 지표 | 컷 전 | D2~E6 컷 |','|---|---:|---:|']
    for metric,label in [('precision','음높이 후보 정밀도'),('recall','음높이 후보 재현율'),('f1','음높이 후보 F1')]:
        lines.append(f"|{label}|{pct(a['pitch']['midi'][metric])}|{pct(b['pitch']['midi'][metric])}|")
    lines += ['',f"검출했지만 정답 활성 MIDI 집합에 없는 후보 중, 정답음의2~8차 배음에35cent 이내로 가까운 비율은 컷 전{pct(a['pitch']['false_pitch_possible_harmonic_fraction'])}, 컷 후{pct(b['pitch']['false_pitch_possible_harmonic_fraction'])}다. 이는 배음 의심 위치 관계이며 실제 배음임을 위상/청음으로 확정한 것이 아니다. 잔향·주석 offset·오차도 가짜 양성에 영향을 줄 수 있다.",'',
        '## 실제 원본과 오류 예시','',
        '아래는 첫 반주 녹음의 원본 파형/스펙트럼과 컷 후 피크 후보 대 실제 MIDI 정답이다. 초록은 해당 시점 주석 MIDI, 주황은 피크 후보다. 주석에 없는 주황을 모두 실제 배음이라고 확정하지 않는다. 별도 합성 데이터나 생성 이미지가 아니다.','',
        '![원본 녹음과 정답/피크 비교](../dataset/integration_review/runs/guitarset_benchmark_20261105_v1/error_example.png)','',
        '원본0~8초:','',
        '![GuitarSet 원본 재생](../dataset/integration_review/runs/guitarset_benchmark_20261105_v1/example_original_0_8.wav)','',
        'D2~E6 컷0~8초:','',
        '![GuitarSet 컷 재생](../dataset/integration_review/runs/guitarset_benchmark_20261105_v1/example_cut_0_8.wav)','',
        '![기본/상세 코드 정확도와 피크 후보 정밀도·재현율](../dataset/integration_review/runs/guitarset_benchmark_20261105_v1/summary.png)','',
        '## 평가 정의와 제한','',
        '- GuitarSet 마이크 모노 원음이며 보컬/기타 분리를 추가 적용하지 않았다. int16을32768로 나눠 기존 float 입력과 같은 진폭 척도로 분석했다.',
        '- 기존8192샘플 Hann STFT,441샘플 hop, 최대12개 상대 피크와 같은 화성 점수를 사용했다. 매10번째 분석 프레임(0.1초)을 평가했다. 시간 평활화는 없었다.',
        '- 코드 경계는 분석창 반길이+50ms, 약143ms를 양쪽에서 제외했다. 정답으로 음을 필터하거나 점수를 튜닝하지 않았다.',
        '- 기본 코드와 상세 코드를 출처별로 분리했다. 코드는 근음+12음고류 집합이 모두 같아야 정답이다. 베이스는 구성음에 포함하지만 역위 종류를 따로 맞히는 지표는 아니다. 확장도수는 mod12로 비교했다.',
        '- 공식 시간문제 파일 `04_BN3-154-E_comp`, `04_Jazz1-200-B_comp`는 주 집계에서 제외하고 all_files 집계/개별 추론은 보존했다. 원본 주석을 이동시키지 않았다. [공식 시간 오류 이슈](https://github.com/marl/GuitarSet/issues/5).',
        '- `02_Funk2-119-G_comp`의 알려진 중복 음표는 원본을 유지했고 MIDI 집합 평가에서 중복 계산되지 않는다. [공식 중복 이슈](https://github.com/marl/GuitarSet/issues/4).',
        '- Harte 어댑터의 출처는 [공식 mir_eval 코드/규약](https://github.com/mir-evaluation/mir_eval/blob/main/mir_eval/chord.py)다. 설치/학습 없이 필요한 도수·생략음·베이스를 명시적으로 해석했고 지원하지 않는 라벨은 별도 집계했다.',
        '- 비전 영상이 없어2:8 비율의 실제 시각 성능을 평가하지 않았다. 기존 영상9개의 점수와 이 데이터셋 점수를 직접 비교해 일반화 향상률이라고 부르지 않는다.',
        '- 이번에는 고정 알고리즘의 전체 기준 측정이다. 여러 프레임은 상관돼 있고 곡 진행/연주자도 반복되므로 수만 시점을 독립 표본으로 보지 않는다. 후속 튜닝은 연주자·진행 분리 검증이 필요하며, 이미 전체 결과를 봤으므로 이 자료를 완전히 미열람한 테스트셋이라고 주장하지 않는다.','',
        '## 오류 집계와 다음 단계','',
        '기본 코드 오답을 근음 오류·같은 근음의 추가 구성음·누락 구성음·보류로 나눈 수는 `error_categories.json`에 있다. 대표 혼동은 아래와 같다.','',
        '| 컷 후 기본 코드 혼동 | 시점 수 |','|---|---:|']
    for pair,count in b['nominal']['top_confusions'][:10]:lines.append(f'|{pair}|{count:,}|')
    lines += ['',
        '다음 작업은 단순 가중치 조정보다 이 기준 성적표를 기준으로 기본음/배음 후보 억제와 코드 추가음 채점을 각각 바꾸는 실험이다. 상세 정답이 사전 밖인 문제와 검출 자체 오류를 분리하고 실제7코드가 잘못 단순화되는지 함께 본다. 이번 실행에서 판별기 점수/사전을 개선했다고 주장하지 않는다.','',
        '재현: `python guitarset_benchmark.py --output dataset/integration_review/runs/guitarset_benchmark_20261105_v1 --workers 2`, 완료 후 `python report_guitarset_benchmark.py`. 최종summary가 있으면 덮어쓰지 않는다. 설정/스크립트 해시/입력 음원·주석SHA256/180개 녹음별 타임라인/두 코드층/음높이 TP·FP·FN/전체·제외 집계는 실행폴더에 보관했다.','',
        '검증 명령: `python -m unittest test_guitarset_benchmark test_bandcut_weight_sweep test_audio_analysis test_guitar_stem_comparison test_tutorial_reference_evaluation test_new_hand_harmony test_harmony_engine test_cell_audio_fusion test_hand_cell_distribution test_virtual_string_grid test_global_fretting_hand -q` —114개 통과. 벡터화 점수가 기존 화성 엔진과 일치하는지, 코드 추가음/생략음/베이스 해석, 두 참조층 분리, 표현 불가 정답 분모 유지, 중복 MIDI 집합 처리, 전체180/주178개 집계 등을 검사했다.']
    (ROOT/'docs/GUITARSET_BASELINE_BENCHMARK_2026-11-05.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps(dict(primary_files=primary['files'],errors=errors,metrics={branch:{layer:primary['branches'][branch][layer].get('top1') for layer in ['nominal','performed']} for branch in ['uncut','cut']}),indent=2))


def render(summary,records):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    data=summary['scopes']['primary_without_known_timing']['branches']
    fig,axes=plt.subplots(1,2,figsize=(13,5))
    labels=['Nominal top1','Nominal top3','Performed top1','Performed top3'];x=np.arange(4)
    for shift,branch in [(-.18,'uncut'),(.18,'cut')]:
        values=[data[branch][layer][metric]*100 for layer,metric in [('nominal','top1'),('nominal','top3'),('performed','top1'),('performed','top3')]]
        axes[0].bar(x+shift,values,.36,label=branch)
        axes[1].bar(np.arange(3)+shift,[data[branch]['pitch']['midi'][k]*100 for k in ['precision','recall','f1']],.36,label=branch)
    axes[0].set(xticks=x,xticklabels=labels,ylabel='Percent',ylim=(0,100));axes[0].tick_params(axis='x',rotation=15)
    axes[1].set(xticks=range(3),xticklabels=['Pitch precision','Pitch recall','Pitch F1'],ylim=(0,100))
    for ax in axes:ax.legend();ax.grid(axis='y',alpha=.2)
    fig.suptitle('178 recordings; frozen spectral baseline; reference layers evaluated separately')
    fig.tight_layout();fig.savefig(FOLDER/'summary.png',dpi=130);plt.close(fig)
    record=records[0];rate,x=wavfile.read(record['audio_file']);audio=x.astype(float)/32768
    fig,axes=plt.subplots(3,1,figsize=(14,10),sharex=True)
    axes[0].plot(np.arange(min(len(audio),12*rate))/rate,audio[:12*rate],lw=.4);axes[0].set_ylabel('Original mic')
    f,t,z=signal.stft(audio[:12*rate],fs=rate,nperseg=8192,noverlap=6144)
    axes[1].pcolormesh(t,f,20*np.log10(np.maximum(abs(z),1e-8)),shading='auto',vmin=-100,vmax=-25,cmap='magma');axes[1].set(ylim=(65,1600),ylabel='Hz')
    traces=[p for p in record['branches']['cut']['pitch']['frames'] if p['time_s']<12]
    for i,frame in enumerate(traces):
        axes[2].scatter([frame['time_s']]*len(frame['reference_midi']),frame['reference_midi'],c='green',s=9,label='Reference MIDI' if i==0 else None)
        axes[2].scatter([frame['time_s']]*len(frame['predicted_midi']),frame['predicted_midi'],c='orange',marker='x',s=13,label='Spectral peak candidate' if i==0 else None)
    axes[2].set(xlim=(0,12),ylabel='MIDI',xlabel='Recording seconds');axes[2].legend()
    fig.suptitle(record['recording_id']+' | real waveform/spectrum and reference vs peak candidates')
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(FOLDER/'error_example.png',dpi=125);plt.close(fig)


if __name__=='__main__':main()
