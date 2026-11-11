"""Generate the requested factual report from completed measurements only."""
import csv
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()


def pct(x):return '측정 불가' if x is None else f'{100*x:.2f}%'
def num(x):return f'{x:,}'


def main():
    summary=json.loads((RUN/'summary.json').read_text(encoding='utf-8'))
    if not summary['complete']:raise RuntimeError('Do not issue a final report while files remain pending')
    manifest=json.loads((RUN/'manifest.json').read_text(encoding='utf-8'))
    environment=json.loads((RUN/'environment.json').read_text())
    history=json.loads((RUN/'historical_comparison.json').read_text())
    post=json.loads((RUN/'posthoc.json').read_text(encoding='utf-8'))
    transition=json.loads((RUN/'transition_diagnosis.json').read_text(encoding='utf-8'))
    inventory=json.loads((RUN/'data_inventory.json').read_text())
    groups=summary['groups'];figures=RUN/'figures';figures.mkdir(exist_ok=True)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for ax,(key,title) in zip(axes,[('guitarset_performed_0.2','GuitarSet performed (178 files)'),('idmt_nominal_0.2','IDMT guitar (6 files)')]):
        vals=[groups[m][key]['views'][v]['exact_accuracy']*100 for m in ['github','patched'] for v in ['A','B']]
        bars=ax.bar(['Git A','Git B','Fixed A','Fixed B'],vals,color=['#7694af','#2e718c','#a9bca6','#498554']);ax.set_ylim(0,100);ax.set_title(title);ax.set_ylabel('Normalized exact: root + PC set (%)')
        for bar,value in zip(bars,vals):ax.text(bar.get_x()+bar.get_width()/2,value+1,f'{value:.2f}',ha='center',fontsize=9)
    fig.tight_layout();fig.savefig(figures/'accuracy.png',dpi=150);plt.close(fig)
    qnames=['major','minor','7','maj7','m7','m7b5','5','OOV']
    fig,axes=plt.subplots(2,1,figsize=(10,7))
    for ax,(key,title) in zip(axes,[('guitarset_performed_0.2','GuitarSet performed'),('idmt_nominal_0.2','IDMT guitar')]):
        names=[q for q in qnames if q in groups['github'][key]['per_quality']['A']];x=np.arange(len(names));width=.2
        for i,(mode,view) in enumerate([(m,v) for m in ['github','patched'] for v in ['A','B']]):
            values=[100*groups[mode][key]['per_quality'][view][q]['exact_accuracy'] for q in names];ax.bar(x+(i-1.5)*width,values,width,label=('Git' if mode=='github' else 'Fixed')+' '+view)
        ax.set_xticks(x,names);ax.set_ylim(0,105);ax.set_title(title);ax.set_ylabel('Exact by reference class (%)');ax.legend(ncol=4,fontsize=9)
    fig.tight_layout();fig.savefig(figures/'qualities.png',dpi=150);plt.close(fig)
    # Preserve all sampled target/prediction rows in one compressed CSV.
    with gzip.open(RUN/'all_predictions.csv.gz','wt',encoding='utf-8-sig',newline='') as out:
        writer=None
        for mode in ['github','patched']:
            for path in sorted((RUN/mode/'details').glob('*.csv')):
                with path.open(encoding='utf-8-sig',newline='') as f:
                    reader=csv.DictReader(f)
                    if writer is None:writer=csv.DictWriter(out,fieldnames=['mode']+reader.fieldnames);writer.writeheader()
                    for row in reader:writer.writerow(dict(mode=mode,**row))
    commit=manifest['git_remote_commit'];text=[]
    def add(s=''):text.append(s)
    add('# Guitar Chord Studio 현재 시스템 성능 재평가 — 2026-11-12\n')
    add('실행 시작: 2026-11-11(KST). 전수 실행 및 보고: 2026-11-12. 모델·가중치·알고리즘·문턱값의 변경, 학습 및 데이터별 파라미터 탐색은 하지 않았다. 주 결과는 **GitHub에 커밋된 상태**, 수정 분리 경로는 별도 보충 실험이다.\n')
    add('## ① 현재 시스템 구성\n')
    add(f'- 평가 GitHub 커밋: `{commit}`. 로컬 기준 HEAD: `{manifest["local_base_commit"]}`. GitHub 최신 변경은 README뿐이며, 핵심 알고리즘은 두 트리에서 줄바꿈/BOM을 정규화하면 같다. 로컬 분리 수정은 미커밋 상태이므로 커밋의 기능으로 포장하지 않는다.')
    add('- 실제 호출: Git 스냅샷 또는 로컬의 `chord_studio_v2/server_v2.py:analyze(job_id, demo=False, separate_guitar=True)` → FFmpeg 22050Hz mono PCM16 추출 → 분리 시도 → `basic_pitch_worker.run_basic_pitch_tasks` → `chord_web_analysis.write_result`/`make_timeline`. 각 녹음 전체를 분석했으며 정답 코드·평가 시각은 추론 함수에 넣지 않았다.')
    add('- **GitHub 원본**: 분리 스크립트가 프로젝트 루트를 `engine`으로 잘못 잡아 격리 환경 탐색에서 실패한다. 실제 로그와 모든 파일별 `separation_status`에 fallback이 기록된다. Demucs 추론은 실행되지 않았고, 원음의 Basic Pitch 추론은 실제 실행됐다.')
    add('- **로컬 수정 경로**: 분리 워커가 로컬 safetensors를 로드해 CPU Demucs 6-source 추론을 실제 실행한다. 생성된 guitar.wav와 원음에 Basic Pitch를 각각 적용하고, 기타 후보에 전체 믹스 앵커를 더한다. 이 측정은 배포 EXE와 같은 핵심 코드의 **소스 실행 경로**이며 GUI/EXE 시작 성능 재평가와는 구분한다.')
    add('- 모델: Basic Pitch **0.4.0**, ONNX Runtime **1.23.2**, `CPUExecutionProvider`, 4스레드. ONNX SHA-256 `2c3c1d144bfa61ad236e92e169c13535c880469a12a047d4e73451f2c059a0ec`. Demucs **4.1.0**, CPU PyTorch **2.14.1+cpu**, 4스레드, `htdemucs_6s`, shifts=0, 7초 분할, overlap=.25. safetensors SHA-256 `d2a1745f0744721f6b8ca5bf469b67c651ea5ed1b52998cab033b2158609d411`.')
    add('- Basic Pitch 사용 방식: 약 2초 입력창, 30프레임 중첩, 양쪽 15프레임 제거 및 입력 샘플 기반 시간축. note/onset/contour 및 MIDI를 실제 생성한다. 코드 분석은 MIDI 이벤트가 아니라 저장한 note activation을 쓴다. 입력 파형 FFT 컷은 하지 않는다. 공식 디코더 frame=.3/onset=.5/minimum11frames를 통과한 뒤 NPZ를 저장하며, 디코더의 음역 제한이 배열을 변경한다. 명목상 D2~E6 제한이지만 v0.4.0 max-frequency 슬라이스는 E6 경계를 제외한다. 이를 평가 중 고치지 않았다.')
    add('- 후보·채점: 0.2초 기본 / 0.4초 보조 최대값 pooling → activation .3 이상 음을 12-PC로 합산·정규화 → 활성 PC≥3 → 15종×12근음=180 템플릿. 점수는 `구성음 salience 합 / 전체 salience 합 − .15 × 누락 구성음 비율`이며 확률이 아니다. 사전 동점 순서를 그대로 유지한다.')
    add('- 후처리: 기존 짧은 A-B-A/드롭아웃 정리, 0.8초 아르페지오 회복, 지속 저음/전역 조성/앞뒤 진행의 가점, 원음 앵커, 온셋과 새로운 PC가 함께 있을 때의 가점, Look-Ahead confirm=.25초·같은 근음 확장음 통합, 보수적인 분수코드 표기, 자동 BPM/마디 정렬 및 16분음표 격자(4/4 한 마디 16칸). 두 음이 완전5도이면 현재 규칙은 파워코드가 아니라 장/단화음을 가정하는 회복 분기도 갖는다.')
    add('- A는 native `row.top3[0]`; B는 native `row.onset_presentation.display_candidates`. 모델과 특징 pooling은 동일하지만 **A/B는 전체 후처리 스택의 비교**다. Look-Ahead 단독 효과라고 주장하지 않는다. `U_context`와 `B_frame`은 각각 prepare 전/격자 전의 기존 기록을 그대로 읽는 진단층이다. UI 기본 표시 선택도 실제 app.js 실행으로 표본 대조했다. 수동 BPM·카포·코드 편집·비전은 적용하지 않았다.')
    add('- 과거 별도 음높이 보정 신경망(`audio_note_calibrator`)은 현재 실행 경로에 import/가중치 로드가 없으며 평가에 추가하지 않았다. 사용한 음높이 모델은 위 사전학습 Basic Pitch다.')
    add(f'- 환경: {environment["cpu"]["Name"].strip()}, 물리6코어/논리12스레드, RAM 약16GB, Windows, Python {environment["python"].split()[0]}. RTX3060이 있으나 **GPU는 사용하지 않았다**. 한 번에 한 녹음만 실행했다. 버전 잠금·환경·모델 출처·소스 원본/패치는 실행 폴더에 보존했다.\n')
    add('A는 원시 중간 기록을 읽는 출력 ablation이다. 프로그램에 후처리를 완전히 건너뛰는 실행 스위치가 없어 B 계산을 실제 생략한 별도 A 전체 실행은 하지 않았다. UI의 context 끄기도 기존 cleanup이 남으므로 완전한 안정화 OFF로 취급하지 않았다.\n')
    add('## ② 평가 데이터\n')
    add('| 데이터 | 실제 분석 | 주 평가 | 평가 시각/정답 |\n|---|---:|---:|---|')
    add('| GuitarSet | comp 180파일 | 178파일, 정답층별 4,886시점 | 과거 고정 1초 격자(.5초 시작); nominal/performed 별도 |')
    add('| IDMT-SMT-Chords | 기타 6음색 | 1,638구간 | 과거 273구간×6음색의 각 구간 중심 |\n')
    add(f'원본 길이는 GuitarSet {sum(r["duration_s"] for r in inventory if r["dataset"]=="guitarset"):.2f}초, IDMT 기타 {sum(r["duration_s"] for r in inventory if r["dataset"]=="idmt"):.2f}초다. 주석·오디오 SHA-256 및 평가 격자를 과거 실험과 대조했고, 분모는 전 파일에서 정확히 재현됐다. 코드 안정 구간 양끝에서 기존 `.05 + 4096/44100` ≈143ms를 제외한다. IDMT는 음색마다 같은 진행을 반복하므로 1,638개를 독립적인 곡으로 해석하지 않는다.\n')
    add('GuitarSet의 알려진 시간 오류 `04_BN3-154-E_comp`, `04_Jazz1-200-B_comp`는 실제 분석하되 주 집계에서 제외했다. 주석 이동은 하지 않았다. solo180파일은 기존 comp 평가와 맞추기 위해 제외했고, IDMT non_guitar10파일도 기존 Basic Pitch 기타 비교 범위와 맞추기 위해 제외했다. N/X, 미지원 문법, 경계/무주석은 제외·집계하며, 파싱 가능한 사전 밖(OOV) 코드는 오답으로 분모에 남겼다. 주석상 코드가 있는 시점에서 모델이 무음/근거 부족으로 보류해도 제거하지 않고 오답 처리한다.\n')
    add('이번 집합은 과거 FFT/초기 Basic Pitch 진단과 동일한 평가 파일·시각이며 새 train/test 분할은 만들지 않았다. 과거 별도 보정 신경망의 학습 분할을 재사용했다고 주장하지 않는다. 이미 열람한 6연주자 전체 comp 집합이므로 연주자 홀드아웃이나 독립 테스트라는 표현도 쓰지 않는다.\n')
    add('정규화 Exact는 과거와 같은 **근음+PC집합** 일치다. 이명동음·옥타브·확장도수는 PC로 정규화하고 베이스 음은 집합에 합치지만 전위 표기는 별도로 요구하지 않는다. 따라서 완전한 보이싱·분수코드 정확도가 아니다. 근음 정확도와 코드 종류(근음 기준 상대 PC집합) 정확도는 각각 독립적으로 계산한다. B의 복수 후보는 정답 후보가 포함돼도 strict top1 오답이다. 베이스 표기까지 요구한 추가 결과를 아래에 별도 제시한다.\n')
    add('발견한 주석 불확실성: IDMT Campfire 313초의 제공 주석은 D:5지만 실제 피크는 약82.5/122.5Hz(E/B 부근), 모델 출력도 MIDI40/47이었다. 주석을 변경하거나 이 사례를 분모에서 제거하지 않았다. 제공 주석 기준 결과와 주석 품질 의심을 구분한다. MIDI 원본/전문가 검증 없이 정답을 새로 확정하지 않았다.\n')
    add('## ③ 정량 평가 결과\n')
    for mode,title in [('github','GitHub 커밋 그대로 — 분리 실패 후 원음 경로'),('patched','보충: 로컬 분리 수정 경로 — 실제 Demucs + 전체 믹스 앵커')]:
        add('### '+title+'\n')
        add('| 데이터/정답층 | 구성 | 정규화 Exact | 근음 | 코드 종류 | 분모 | 처리 시간 |\n|---|---|---:|---:|---:|---:|---|')
        for key,label in [('guitarset_performed_0.2','GuitarSet 상세 연주'),('idmt_nominal_0.2','IDMT 기타')]:
            g=groups[mode][key]
            for view in ['A','B']:
                v=g['views'][view];timing=f'원시 후처리 {g["A_native_raw_postprocess_both_widths_s"]:.2f}s (두 창 합계); 단독 E2E 미측정' if view=='A' else f'{g["B_analyze_wall_s"]:.2f}s / 오디오 {g["duration_s"]:.2f}s; RTF {g["real_time_factor_B"]:.3f}'
                add(f'| {label} | {view} | {pct(v["exact_accuracy"])} | {pct(v["root_accuracy"])} | {pct(v["quality_accuracy"])} | {num(v["n"])} | {timing} |')
        nominal=groups[mode]['guitarset_nominal_0.2'];add(f'\nGuitarSet 기본 악보 정답층은 A {pct(nominal["views"]["A"]["exact_accuracy"])}, B {pct(nominal["views"]["B"]["exact_accuracy"])}다. 기본/상세 중 높은 쪽만 골라 제시하지 않는다.\n')
    add('처리 시간은 실제 analyze() 벽시계 합계이며 업로드 복사·평가 CSV/통계 작성 시간은 제외한다. 분리·모델·기본 후처리·result.json 저장은 포함한다. A는 B와 전처리/추론을 공유했으므로 독립적인 A 전체 처리 시간을 측정했다고 주장하지 않는다. A의 pooling/scorer 두 분기만 추가로 실제 계측했다. RTF는 각 데이터 안의 관측값이며 CPU 부하/초기화 영향이 있고 속도를 보장하지 않는다.\n')
    add('![실측 정규화 코드 일치율](runs/current_20261111_v1/figures/accuracy.png)\n')
    add('### 코드 종류별 정규화 Exact\n')
    add('| 데이터 | 정답 종류 | N | Git A | Git B | 수정 A | 수정 B |\n|---|---|---:|---:|---:|---:|---:|')
    for key,label in [('guitarset_performed_0.2','GuitarSet 상세'),('idmt_nominal_0.2','IDMT 기타')]:
        for q in qnames:
            ref=groups['github'][key]['per_quality']['A'].get(q)
            if not ref:continue
            values=[pct(groups[m][key]['per_quality'][v][q]['exact_accuracy']) for m in ['github','patched'] for v in ['A','B']]
            add(f'| {label} | {q} | {ref["n"]} | '+' | '.join(values)+' |')
    add('\n모든 코드 종류의 근음·종류 일치 수도 `per_quality.csv`에 저장했다. OOV는 표현 불가능해도 분모에 남겼다.\n')
    add('![코드 종류별 비교](runs/current_20261111_v1/figures/qualities.png)\n')
    add('### 같은 선행 문맥을 유지한 단계별 진단\n')
    add('| 경로/데이터 | prepare 전 U_context | Look-Ahead 표시 후·격자 전 | 최종 B |\n|---|---:|---:|---:|')
    for mode in ['github','patched']:
        for key in ['guitarset_performed_0.2','idmt_nominal_0.2']:
            values=[pct(groups[mode][key]['views'][v]['exact_accuracy']) for v in ['U_context','B_frame','B']]
            add('| '+mode+'/'+key+' | '+' | '.join(values)+' |')
    add('\nU_context에도 앞뒤 진행·기존 cleanup 등 시간 정보가 이미 들어 있다. 이 표는 선행 문맥을 고정한 뒤 prepare와 격자 단계에서 무엇이 바뀌는지 보는 것이며, 완전한 무시간 모델과 Look-Ahead만의 순수 비교는 아니다. 기본 0.2초 이외의 기존 0.4초 분기도 동일하게 실행·보존했으며 좋은 쪽을 고르지 않았다.\n')
    add('### 전위 베이스 표기까지 포함한 추가 Exact\n')
    add('| 데이터/정답층 | Git A | Git B | 수정 A | 수정 B |\n|---|---:|---:|---:|---:|')
    for suffix,label in [('guitarset_performed','GuitarSet 상세'),('idmt_nominal','IDMT 기타')]:
        values=[pct(post['bass_spelling'][m+'_'+suffix+'_'+v]['exact_with_bass_accuracy']) for m in ['github','patched'] for v in ['A','B']]
        add('| '+label+' | '+' | '.join(values)+' |')
    add('\n주석의 `/도수`를 bass PC로 해석하고, 분모 없는 예측은 근음 위치 표기로 읽었다. 이 표는 예측 코드의 표기 일치이며 물리적으로 어떤 현이 최저음인지 확인한 지표는 아니다. 과거의 전위 제외 Exact와 섞어 비교하지 않는다.\n')
    add('### 짧은 변동 및 정답 전환\n')
    add('| 경로/데이터 | A 0.2초 미만 코드 구간 | B 0.2초 미만 | A 정답 양측 재현 | B 정답 양측 재현 | 분모 |\n|---|---:|---:|---:|---:|---:|')
    for mode in ['github','patched']:
        for key,label in [('guitarset_performed_0.2','GuitarSet 상세'),('idmt_nominal_0.2','IDMT 기타')]:
            g=groups[mode][key];t=g['transitions'];add(f'| {mode}/{label} | {g["temporal"]["A"]["short_chord_runs_lt_02"]} | {g["temporal"]["B"]["short_chord_runs_lt_02"]} | {t.get("stable_detected_A",0)} | {t.get("stable_detected_B",0)} | {t.get("stable_labelled",0)} |')
    add('\n짧은 변동은 native24Hz의 비어 있지 않은 코드 run<.2초다. 전환 재현은 주석 경계 ±.5초 내 양측의 정확한 코드가 모두 등장하는지 확인한 별도 진단이며, 표준 전환 검출 F1이 아니다. OOV도 포함하는 전체 정답 전환의 재현 수다. 1초 샘플 Exact와 분모를 공유하지 않는다. 짧은 변동 감소를 정확도 향상과 동일시하지 않는다.\n')
    add('## ④ 과거 실험과 비교\n')
    add('| 결과 출처/방법 | GuitarSet 기본 | GuitarSet 상세 | IDMT 기타 |\n|---|---:|---:|---:|')
    methods=[('harmonic_ablation_20261105_v1','peak_legacy','2026-11-05 FFT 피크/coverage'),('harmonic_ablation_20261105_v1','peak_cosine','2026-11-05 FFT 피크/cosine'),('harmonic_ablation_20261105_v1','harmonic_legacy','2026-11-05 harmonic/coverage'),('harmonic_ablation_20261105_v1','harmonic_cosine','2026-11-05 harmonic/cosine'),('basic_pitch_20261105_v2','raw_frames','2026-11-05 초기 BP raw/instant frame')]
    for folder,branch,label in methods:
        values=[pct(history['groups'][folder+'/'+branch+'/'+domain+'/'+layer]['rates']['exact']) for domain,layer in [('guitarset','nominal'),('guitarset','performed'),('idmt','nominal')]];add('| '+label+' | '+' | '.join(values)+' |')
    for mode in ['github','patched']:
        for view in ['A','B']:
            values=[pct(groups[mode][key]['views'][view]['exact_accuracy']) for key in ['guitarset_nominal_0.2','guitarset_performed_0.2','idmt_nominal_0.2']];add('| 이번 실행 '+mode+' '+view+' | '+' | '.join(values)+' |')
    add('\n과거 행은 **기존 저장 예측을 동일 기준으로 다시 집계한 값**이며 신규 추론이 아니다. 동일 파일 SHA·주석·평가시각·정답 변환·분모를 확인했으므로 같은 데이터 내 시스템 출력은 비교할 수 있다. 다만 FFT의 약186ms 창, BP 약2초 문맥, 현재 최대값 pooling/FFmpeg 재표본화/후처리/분리·앵커 차이가 있어 순수 Basic Pitch 도입 효과나 Look-Ahead 단독 효과로 해석할 수 없다. 예전 100ms 표본 48,326시점 수치와 이 표의 1초 4,886시점 수치를 직접 이어 붙이지 않는다. 두 데이터셋의 절대 정확도를 비교해 일반화 성능을 판단하지 않는다.\n')
    add('## ⑤ 실패 사례\n')
    add('| 경로/데이터 | 가장 빈번한 B 오판 | 발생 시점 수 |\n|---|---|---:|')
    for mode in ['github','patched']:
        for key,label in [('guitarset_performed_0.2','GuitarSet 상세'),('idmt_nominal_0.2','IDMT 기타')]:
            for case,n in groups[mode][key]['confusion']['B'][:5]:add(f'| {mode}/{label} | {case} | {n} |')
    add('\n실제로 A가 맞았는데 B가 틀린 시점 수:\n')
    for mode in ['github','patched']:
        for key in ['guitarset_performed','idmt_nominal']:
            p=summary['paired_A_B'][mode+'_'+key];add(f'- {mode}/{key}: A만 정답 {p.get("A_only_correct",0)}, B만 정답 {p.get("B_only_correct",0)}, 둘 다 오답 {p.get("both_wrong",0)}.')
    add('\n확인된 사실: raw scorer는 PC≥3을 요구해 실제 2음 파워코드에서 보류할 수 있다. 현재 두 음 회복 규칙은 근음+완전5도에 장/단화음을 가정한다. 실제 IDMT Campfire313초 기록은 raw=[], context E(score=.85), final E였으며 정답은 D:5였다. 이는 파워코드 처리와 해당 주석의 음향 불일치 의심을 모두 포함하므로 어느 하나만 원인이라고 단정하지 않는다.\n')
    add('후처리로 새 코드가 주석 구간 전체에서 사라진 사례는 단순 .5초 지연과 구분했다. 아래는 양측 .5초 이상이며 사전으로 표현 가능한 정답 전환만의 단계별 진단이다. 두 손실 수는 서로 다른 단계 비교이며 합쳐 최종 누락 수라고 부를 수 없다.\n')
    add('| 경로/데이터 | 해당 정답 전환 | context→격자 전 새 코드 소실 | 격자 전→최종 소실 |\n|---|---:|---:|---:|')
    for mode in ['github','patched']:
        for key in ['guitarset_performed','idmt_nominal']:
            t=transition['groups'][mode+'_'+key];add(f'| {mode}/{key} | {t["stable_representable_transitions"]} | {t["confirmed_lookahead_interval_omission"]} | {t["confirmed_grid_interval_omission"]} |')
    add('\n모든 개별 시각·정답·예측은 CSV와 transition_diagnosis.json에 남겼다. 입력/모델/점수/최종 표시를 구분하며, 원인 후보(분리 중 음 근거 약화, 조성·이웃 우선, 격자 병합)는 인과적으로 분리한 실험이 아니므로 추정으로만 다룬다. 제공 주석 기준의 오답이 항상 실제 음악적으로 잘못된 해석이라는 뜻도 아니다.\n')
    add('![실제 native 기록의 코드 소실 사례](runs/current_20261111_v1/figures/observed_transition_omission.png)\n')
    add('그림은 사전순 첫 상세 주석 소실 사례를 선택한 진단용 예시다. 위에서부터 제공 정답, 원시 A, prepare 전 문맥, 격자 전, 최종 B다. Bmaj7 후보가 잠깐 등장했지만 최종 격자 단계에서 사라졌다. 이 한 예시를 전체 정확도나 모든 소실의 원인으로 일반화하지 않는다.\n')
    add('![IDMT 제공 주석과 관측 음향의 불일치 의심](runs/current_20261111_v1/figures/idmt_reference_uncertainty.png)\n')
    add('빨간 점선은 제공 D5의 D/A 음고류 주파수 위치, 초록은 관측/모델의 E/B 부근 위치다. 피크만으로 새 정답을 확정하지 않았다. [해당 원본 2초 소리](runs/current_20261111_v1/figures/idmt_power_312_314.wav).\n')
    add(f'최종 분석 종료 상태가 error인 파일: {len(summary["errors"])}건. GitHub 원본의 분리 단계 실패/fallback은 별도의 186건이며 정상 Demucs 실행으로 세지 않는다. 초기 평가 어댑터의 SHORTHANDS 누락은 실패 기록을 보존하고 원본 상수를 그대로 복원한 뒤 새 출력으로 재실행했다. 집계 열 이름 충돌 등 평가 도구 오류도 evaluator_incidents.json에 남겼다. 예측 알고리즘이나 문턱값은 고치지 않았다. GitHub의 분리 실패/fallback은 숨기지 않고 평가된 실제 실행 상태로 별도 집계했다.\n')
    add('## ⑥ 결론\n')
    add('- 현재 Basic Pitch 추론과 후처리의 실제 성적을 재현 가능한 실행물로 확보했다. 원시 후보·후처리 출력·상세 실패 기록이 분리돼 있어 어느 단계에서 오판이 생겼는지 추적할 수 있다.')
    add('- 단독 기타와 합성 기타에서의 관측값이며, 밴드/보컬이 있는 실제 영상·새 연주자·새 곡 전체에 대한 정확도로 확대하지 않는다. 파워코드/OOV/전위, 후처리의 실제 코드 소실은 남아 있는 한계다.')
    add('- GitHub의 Demucs fallback과 로컬 수정 경로를 구분해야 한다. 분리+전체 믹스 앵커의 결과 차이는 두 경로 전체의 비교이며 Demucs 단독 인과 효과가 아니다. 수치를 좋게 만들려고 어느 경로든 제거하거나 파라미터를 바꾸지 않았다.')
    add('- GuitarSet은 Basic Pitch 연구의 학습 자료에 포함되고 이 프로젝트에서도 이미 여러 번 열람한 자료다. 현재 평가는 독립적인 미열람 테스트가 아니다. 데이터셋 간 높은/낮은 절대 정확도로 일반화를 주장하지 않는다.')
    add('- 실험 C는 미실행: 두 데이터셋에 동기화된 영상/비전 정답이 없어 실제 비전 융합 성능을 검증할 수 없다. 가상 손/지판 후보는 넣지 않았다. 현 접촉·개방현·뮤트·타브·크롬 확장·전체 운지 시스템 정확도도 이번 수치로 확인할 수 없다.\n')
    add('## ⑦ 포트폴리오용 요약 (200~300자)\n')
    gg=groups['github']['guitarset_performed_0.2']['views'];ii=groups['github']['idmt_nominal_0.2']['views']
    portfolio=f'GitHub 커밋 {commit[:7]}의 실제 오디오 경로를 동결해 GuitarSet 178파일·4,886시점과 IDMT 기타 6음색·1,638구간을 평가했다. 근음·음고류 집합 일치율은 원시/후처리 각각 GuitarSet {pct(gg["A"]["exact_accuracy"])}/{pct(gg["B"]["exact_accuracy"])}, IDMT {pct(ii["A"]["exact_accuracy"])}/{pct(ii["B"]["exact_accuracy"])}였다. 분리 실패 후 원음 대체와 후처리의 정답 소실도 기록했다. 전위·학습 자료 중복·주석 불확실성을 별도 명시했으며 비전이나 전체 운지 정확도를 뜻하지 않는다.'
    assert 200<=len(portfolio)<=300,(len(portfolio),portfolio)
    add(portfolio+f'\n\n공백·기호 포함 {len(portfolio)}자.\n')
    add('## 재현 및 상세 기록\n')
    add('[재현 명령](current_20261111/README.md) · [고정 프로토콜](current_20261111/PROTOCOL.json) · [파일·시각별 정답과 예측 CSV.gz](runs/current_20261111_v1/all_predictions.csv.gz) · [집계 JSON](runs/current_20261111_v1/summary.json) · [종류별 CSV](runs/current_20261111_v1/per_quality.csv) · [오판 CSV](runs/current_20261111_v1/confusions.csv) · [파일별 시간](runs/current_20261111_v1/per_file.csv) · [전환 누락 상세](runs/current_20261111_v1/transition_diagnosis.json). 실행 폴더에 전체 생산 코드 스냅샷, Git 패치, 새 NPZ/MIDI/result.json 및 stderr 로그를 보존했다.\n')
    add('근거: [Basic Pitch 공식 구현](https://github.com/spotify/basic-pitch), [Basic Pitch 논문](https://arxiv.org/abs/2203.09893), [GuitarSet 공식 저장소·주석 오류 안내](https://github.com/marl/GuitarSet), [IDMT 공식 데이터 설명](https://www.idmt.fraunhofer.de/en/publications/datasets/chords.html). 과거 숫자의 근거는 archived source hash와 historical_comparison.json이며 신규 실험으로 표시하지 않았다.\n')
    path=ROOT/'evaluation/CURRENT_SYSTEM_EVALUATION_2026-11-12.md';path.write_text('\n'.join(text),encoding='utf-8')
    (RUN/'portfolio_summary.txt').write_text(portfolio,encoding='utf-8')
    print(path, 'portfolio chars',len(portfolio))


if __name__=='__main__':main()
