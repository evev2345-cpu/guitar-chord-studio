"""Change only the audio component on the existing frozen nine-reference comparison."""
import json
import numpy as np
from scipy.io import wavfile
from scipy import signal
from joint_evidence_review import ROOT,read
from fretboard_frame_identity import sha256_file
from harmony_engine import provisional_audio_harmony
from compare_new_hand_harmony import rerank
from evaluate_tutorial_reference import evaluate


def score_interval(evidence,interval,half):
    frames=[f for f in evidence['pitch_class_salience'] if interval[0]<=f['time_s']-half and f['time_s']+half<=interval[1]]
    if not frames:raise ValueError('No complete analysis support')
    result=provisional_audio_harmony(dict(start_s=interval[0],end_s=interval[1],pitch_class_salience=frames),top_k=192)
    grouped={}
    for frame in result['salience_frames']:
        for c in frame['chord_candidates']:grouped.setdefault((c['root_pc'],c['quality']),[]).append(c)
    candidates=[dict(items[0],score=float(np.mean([c['score'] for c in items]))) for items in grouped.values()]
    candidates.sort(key=lambda c:(-c['score'],c['root_pc'],c['quality']))
    return candidates,frames


def safe_evaluate(candidates,reference):
    if candidates:return evaluate(candidates,reference)
    return dict(exact_top1=False,exact_top3=False,tied_top1_contains_reference=False,top1_tie_count=0,root_top1=False,reference_rank=None,abstain=True)


def main():
    out=ROOT/'dataset/integration_review/runs/guitar_stem_accuracy_20261105_v1'
    if (out/'result.json').exists():raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True)
    baseline_path=ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/result.json'
    baseline=read(baseline_path)
    old_path=ROOT/'dataset/audio_analysis/runs/barre_194_226_accompaniment_20261104_v1/evidence.json'
    new_path=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_analysis_20261105_v1/evidence.json'
    old,new=read(old_path),read(new_path)
    if old['source_id']!=new['source_id'] or old['start_s']!=new['start_s'] or old['end_s']!=new['end_s']:raise ValueError('Audio timeline/source mismatch')
    sep_dir=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1'
    sep=read(sep_dir/'separation_manifest.json')
    if sep['status']!='completed' or sha256_file(sep['input'])!=sep['input_sha256']:raise ValueError('Separation input/status mismatch')
    paths=dict(mixture=sep['input'],accompaniment=str(ROOT/'dataset/audio_analysis/runs/barre_194_226_separation_20261104_v1/htdemucs/original/no_vocals.wav'),
               guitar=str(sep_dir/'htdemucs_6s/original/guitar.wav'),no_guitar=str(sep_dir/'htdemucs_6s/original/no_guitar.wav'))
    arrays={};qa={}
    for name,path in paths.items():
        rate,x=wavfile.read(path)
        if rate!=44100 or x.shape!=(1411200,2) or not np.isfinite(x).all():raise ValueError('Stem grid or data mismatch')
        arrays[name]=x
        qa[name]=dict(path=path,sha256=sha256_file(path),sample_rate=rate,shape=list(x.shape),
                      rms=float(np.sqrt(np.mean(x.astype(float)**2))),peak=float(np.max(np.abs(x))),finite=True)
    residual=arrays['mixture'].astype(float)-arrays['guitar']-arrays['no_guitar']
    qa['reconstruction_error_rms']=float(np.sqrt(np.mean(residual**2)))
    qa['listening_review']='not_human_reviewed; model instrument attribution not verified'
    rows=[]
    for old_row in baseline['frames']:
        interval=old_row['audio_support_s'];ref=old_row['reference'];half=4096/44100
        replay,_=score_interval(old,interval,half)
        if [(c['root_pc'],c['quality'],c['score']) for c in replay]!=[(c['root_pc'],c['quality'],c['score']) for c in old_row['audio_only']]:raise ValueError('Baseline scoring changed')
        candidates,frames=score_interval(new,interval,half)
        combined=rerank(candidates,np.array(old_row['visual_pc_mass']),.2) if old_row['visual_used'] else candidates
        rows.append(dict(frame_index=old_row['frame_index'],frame_pts_s=old_row['frame_pts_s'],image_file=old_row['image_file'],reference=ref,
            accompaniment_audio=old_row['audio_only'],accompaniment_combined=old_row['combined'],
            guitar_audio=candidates,guitar_combined=combined,
            evaluation={branch:safe_evaluate(cs,ref) for branch,cs in [('accompaniment_audio',old_row['audio_only']),('accompaniment_combined',old_row['combined']),('guitar_audio',candidates),('guitar_combined',combined)]},
            audio_analysis_frame_count=len(frames),audio_support_s=interval,visual_used=old_row['visual_used'],visual_pc_mass=old_row['visual_pc_mass']))
        print(ref['time'],ref['concert_symbol'],'old',old_row['audio_only'][0]['concert_symbol'],'guitar',candidates[0]['concert_symbol'] if candidates else 'abstain','combined',combined[0]['concert_symbol'] if combined else 'abstain',flush=True)
    branches=['accompaniment_audio','accompaniment_combined','guitar_audio','guitar_combined']
    metrics={branch:{key:sum(r['evaluation'][branch][key] for r in rows) for key in ['exact_top1','exact_top3','root_top1','tied_top1_contains_reference']} for branch in branches}
    metrics['sample_count']=len(rows)
    metrics['audio_improved']=[r['frame_pts_s'] for r in rows if not r['evaluation']['accompaniment_audio']['exact_top1'] and r['evaluation']['guitar_audio']['exact_top1']]
    metrics['audio_worsened']=[r['frame_pts_s'] for r in rows if r['evaluation']['accompaniment_audio']['exact_top1'] and not r['evaluation']['guitar_audio']['exact_top1']]
    result=dict(frames=rows,metrics=metrics,quality_checks=qa,baseline_replay_exact=True,
        provenance=dict(baseline_path=str(baseline_path),baseline_sha256=sha256_file(baseline_path),
                        reference_sha256=baseline['reference_sha256'],old_evidence_sha256=sha256_file(old_path),new_evidence_sha256=sha256_file(new_path),
                        model_manifest=read(ROOT/'docs/guitar-separation-model-manifest.json'),separation_manifest=sep),
        frozen_parameters=baseline['frozen_model'],guitar_isolation_verified=False,
        limitations=baseline['limitations']+['Different separation models and target stems; no claim of guitar-only ground truth','No alignment correction beyond source sample grid'])
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'metrics.json').write_text(json.dumps(metrics,indent=2),encoding='utf-8')
    for name in ['mixture','accompaniment','guitar']:
        wavfile.write(out/f'{name}_198_202.wav',44100,arrays[name][4*44100:8*44100])
    render(rows,arrays,out)
    print(json.dumps(metrics,indent=2))


def render(rows,arrays,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,2,figsize=(14,9))
    for row,name in enumerate(['mixture','accompaniment','guitar']):
        x=arrays[name][4*44100:8*44100].mean(axis=1);times=198+np.arange(len(x))/44100
        axes[row,0].plot(times,x,lw=.4);axes[row,0].set(title=name+' | 198-202s',ylim=(-.6,.6))
        f,t,z=signal.stft(x,fs=44100,nperseg=4096,noverlap=3072)
        axes[row,1].pcolormesh(198+t,f,20*np.log10(np.maximum(abs(z),1e-7)),vmin=-90,vmax=-20,shading='auto',cmap='magma')
        axes[row,1].set(ylim=(60,2000),title=name+' | identical dB scale')
    fig.suptitle('Model guitar estimate vs accompaniment; no loudness normalization, no human isolation verification')
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(out/'audio_comparison.png',dpi=125);plt.close(fig)
    import cv2
    fig,axes=plt.subplots(3,2,figsize=(14,12))
    for pair,row in zip(axes,[rows[i] for i in [2,4,7]]):
        pair[0].imshow(cv2.cvtColor(cv2.imread(row['image_file']),cv2.COLOR_BGR2RGB));pair[0].axis('off')
        pair[0].set_title(f"PTS {row['frame_pts_s']:.6f}s | reference {row['reference']['concert_symbol']}")
        pair[1].axis('off');text=''
        for name in ['accompaniment_audio','guitar_audio','guitar_combined']:
            text+=name+':\n'+' / '.join(c['concert_symbol'] for c in row[name][:3])+f"\nExact top1: {row['evaluation'][name]['exact_top1']}\n\n"
        pair[1].text(.02,.95,text,va='top',fontsize=12)
    fig.suptitle('Same reference intervals and scoring; only audio component changes')
    fig.tight_layout(rect=[0,0,1,.97]);fig.savefig(out/'chord_comparison.png',dpi=125);plt.close(fig)


if __name__=='__main__':main()
