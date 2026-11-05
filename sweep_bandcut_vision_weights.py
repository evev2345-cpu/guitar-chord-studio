"""User-requested D2-E6 signal cut and vision:audio 0:10..10:0 frozen-sample sweep."""
import json
import csv
import numpy as np
from scipy.io import wavfile
from scipy import signal
from joint_evidence_review import ROOT,read
from fretboard_frame_identity import sha256_file
from audio_analysis import features
from compare_guitar_stem_accuracy import score_interval,safe_evaluate
from compare_new_hand_harmony import rerank

LOW_HZ=440*2**((38-69)/12)
HIGH_HZ=440*2**((88-69)/12)


def band_cut(samples,rate,low=LOW_HZ,high=HIGH_HZ):
    x=np.asarray(samples,float)
    if x.ndim not in (1,2) or not np.isfinite(x).all() or not 0<low<high<rate/2:raise ValueError('Invalid signal or band')
    freq=np.fft.rfftfreq(len(x),1/rate);spectrum=np.fft.rfft(x,axis=0)
    keep=(freq>=low)&(freq<=high);spectrum[~keep]=0
    return np.fft.irfft(spectrum,n=len(x),axis=0)


def main():
    out=ROOT/'dataset/integration_review/runs/bandcut_weight_sweep_20261105_v1'
    if (out/'result.json').exists():raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True)
    baseline_path=ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/result.json'
    baseline=read(baseline_path)
    guitar_manifest=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_analysis_20261105_v1/manifest.json'
    manifest=read(guitar_manifest);source=manifest['analysis_parent_audio']
    rate,stereo=wavfile.read(source)
    if rate!=44100 or stereo.shape!=(1411200,2):raise ValueError('Input sample grid mismatch')
    filtered=band_cut(stereo,rate)
    wavfile.write(out/'guitar_D2_E6.wav',rate,filtered.astype(np.float32))
    wavfile.write(out/'guitar_D2_E6_198_202.wav',rate,filtered[4*rate:8*rate].astype(np.float32))
    wavfile.write(out/'guitar_uncut_198_202.wav',rate,stereo[4*rate:8*rate])
    # Hard-cut signal AND constrain interpolated peak candidates to the requested band.
    evidence,_=features(filtered.mean(axis=1),rate,manifest['start_s'],min_frequency=LOW_HZ,max_frequency=HIGH_HZ)
    evidence.update(source_id=manifest['source_id'],start_s=manifest['start_s'],end_s=manifest['end_s'],
                    timebase='source_video_seconds',candidate_frequency_bounds_hz=[LOW_HZ,HIGH_HZ])
    (out/'cut_evidence.json').write_text(json.dumps(evidence,indent=2),encoding='utf-8')
    uncut=read(ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_analysis_20261105_v1/evidence.json')
    rows=[]
    for base in baseline['frames']:
        if base['source_id']!=evidence['source_id']:raise ValueError('Source identity mismatch')
        cuts,cut_frames=score_interval(evidence,base['audio_support_s'],4096/rate)
        originals,original_frames=score_interval(uncut,base['audio_support_s'],4096/rate)
        if [f['time_s'] for f in cut_frames]!=[f['time_s'] for f in original_frames]:raise ValueError('Analysis timing mismatch')
        row=dict(frame_index=base['frame_index'],frame_pts_s=base['frame_pts_s'],image_file=base['image_file'],reference=base['reference'],
                 visual_pc_mass=base['visual_pc_mass'],visual_used=base['visual_used'],cut_audio=cuts,uncut_audio=originals,
                 ratios={},audio_analysis_frame_count=len(cut_frames),audio_support_s=base['audio_support_s'])
        for vision in range(11):
            weight=vision/10;key=f'{vision}:{10-vision}'
            record={}
            for branch,candidates in [('uncut',originals),('cut',cuts)]:
                ranked=rerank(candidates,np.asarray(base['visual_pc_mass']),weight) if base['visual_used'] else candidates
                record[branch]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,base['reference']))
            row['ratios'][key]=record
        rows.append(row)
    summaries=[]
    for vision in range(11):
        key=f'{vision}:{10-vision}';summary=dict(vision_to_audio=key,vision_weight=vision/10,audio_weight=(10-vision)/10,count=len(rows))
        for branch in ['uncut','cut']:
            summary[branch]={metric:sum(r['ratios'][key][branch]['evaluation'][metric] for r in rows) for metric in ['exact_top1','exact_top3','root_top1','tied_top1_contains_reference']}
            summary[branch]['tied_samples']=sum(r['ratios'][key][branch]['evaluation']['top1_tie_count']>1 for r in rows)
            summary[branch]['mean_top_tie_count']=float(np.mean([r['ratios'][key][branch]['evaluation']['top1_tie_count'] for r in rows]))
        summaries.append(summary)
    original_spectrum=np.fft.rfft(stereo.astype(float),axis=0);frequencies=np.fft.rfftfreq(len(stereo),1/rate)
    outside=(frequencies<LOW_HZ)|(frequencies>HIGH_HZ)
    result=dict(frames=rows,summary=summaries,band=dict(low_hz=LOW_HZ,high_hz=HIGH_HZ,low_note='D2',high_note='E6',
        method='full32s offline real-FFT rectangular mask per channel; zero phase but noncausal and ringing possible',
        energy_removed_fraction=float(np.mean((stereo-filtered)**2)/np.mean(stereo.astype(float)**2)),
        candidate_bounds_also_applied=True),
        provenance=dict(input_guitar=str(source),input_sha256=sha256_file(source),references_sha256=baseline['reference_sha256'],
            baseline_path=str(baseline_path),baseline_sha256=sha256_file(baseline_path),
            output_sha256=sha256_file(out/'guitar_D2_E6.wav')),
        tuning='standard EADGBE retained; lower D2 cutoff is NOT a retuning assumption',
        unchanged=['same9 reference intervals','same cached vision masses','middle excluded','same chord dictionary/scoring'],
        interpretation='exploratory final chord-score mixture, not new vision-guided fundamental/harmonic extraction',
        production_gates_modified=False,limitations=['Single-video development sweep, not held-out accuracy','Band-internal harmonics remain',
            'Scores not calibrated probabilities','Vision-only may have large ties; sorted-first and tie-inclusive metrics both reported'])
    (out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    (out/'summary.json').write_text(json.dumps(summaries,indent=2),encoding='utf-8')
    with (out/'summary.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.writer(handle);writer.writerow(['vision:audio','uncut_top1','cut_top1','uncut_top3','cut_top3','uncut_root','cut_root','cut_top_tie_samples'])
        for s in summaries:writer.writerow([s['vision_to_audio'],s['uncut']['exact_top1'],s['cut']['exact_top1'],s['uncut']['exact_top3'],s['cut']['exact_top3'],s['uncut']['root_top1'],s['cut']['root_top1'],s['cut']['tied_samples']])
    render(rows,summaries,stereo,filtered,rate,out)
    print(json.dumps(dict(band=result['band'],summary=summaries),indent=2))


def render(rows,summaries,original,filtered,rate,out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(14,5));weights=np.arange(11)
    for ax,metric in zip(axes,['exact_top1','exact_top3']):
        ax.plot(weights,[s['uncut'][metric] for s in summaries],'o--',label='Uncut guitar')
        ax.plot(weights,[s['cut'][metric] for s in summaries],'o-',label='D2-E6 cut guitar')
        ax.set(xticks=weights,xticklabels=[s['vision_to_audio'] for s in summaries],yticks=range(10),ylim=(-.2,9.2),
               xlabel='Vision : audio',ylabel='Correct / 9',title=metric);ax.legend();ax.grid(alpha=.2)
    fig.suptitle('Same nine reference intervals; deterministic top1; development sweep, not held-out test')
    fig.tight_layout();fig.savefig(out/'weight_sweep.png',dpi=135);plt.close(fig)
    fig,axes=plt.subplots(2,2,figsize=(14,7))
    for i,(name,pcm) in enumerate([('Uncut guitar',original),('D2-E6 cut guitar',filtered)]):
        x=pcm[4*rate:8*rate].mean(axis=1);axes[i,0].plot(198+np.arange(len(x))/rate,x,lw=.4);axes[i,0].set(title=name,ylim=(-.5,.5))
        f,t,z=signal.stft(x,fs=rate,nperseg=8192,noverlap=6144)
        axes[i,1].pcolormesh(198+t,f,20*np.log10(np.maximum(abs(z),1e-8)),vmin=-100,vmax=-25,shading='auto',cmap='magma')
        axes[i,1].set(ylim=(30,2200),title=name+' | same dB scale');axes[i,1].axhline(LOW_HZ,color='cyan',lw=1);axes[i,1].axhline(HIGH_HZ,color='cyan',lw=1)
    fig.suptitle('198-202s; no volume normalization; cyan = requested band edges')
    fig.tight_layout();fig.savefig(out/'audio_comparison.png',dpi=125);plt.close(fig)
    import cv2
    fig,axes=plt.subplots(2,2,figsize=(14,9))
    for pair,row in zip(axes,[rows[2],rows[4]]):
        pair[0].imshow(cv2.cvtColor(cv2.imread(row['image_file']),cv2.COLOR_BGR2RGB));pair[0].axis('off')
        pair[0].set_title(f"PTS {row['frame_pts_s']:.6f}s | reference {row['reference']['concert_symbol']}")
        pair[1].axis('off');text='Cut-guitar top1 by V:A\n'
        for key in ['0:10','1:9','2:8','3:7','4:6','5:5','6:4','7:3','8:2','9:1','10:0']:
            record=row['ratios'][key]['cut'];cs=record['top3'];label=cs[0]['concert_symbol'] if cs else 'abstain'
            text+=f"{key}: {label} | ties {record['evaluation']['top1_tie_count']}\n"
        pair[1].text(.05,.95,text,va='top',fontsize=12)
    fig.suptitle('Reference photos and ratio outcomes; no references fed into ranking')
    fig.tight_layout();fig.savefig(out/'examples.png',dpi=125);plt.close(fig)


if __name__=='__main__':main()
