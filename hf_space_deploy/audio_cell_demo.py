"""Reproducible real-audio/synthetic-cell demonstration; no grid/hand inference."""
import argparse
import copy
import json
from pathlib import Path
import numpy as np
from scipy.io import wavfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from audio_cell_compatibility import compare,STANDARD
from audio_mixture_diagnostics import digest

WINDOWS=[(5.05,5.35),(7.80,8.10),(8.75,9.05)]
SMALL={'s6_p1','s5_p3','s4_p1','s3_p1','s2_p1','s1_p3'}


def build(parent,output):
    parent=Path(parent).resolve();root=Path(output);root.mkdir(parents=True,exist_ok=False)
    (root/'fixtures').mkdir();records={n:json.loads((parent/n/'evidence.json').read_text()) for n in ['mixture','accompaniment','vocals']}
    summary=[];failure=None
    for lo,hi in WINDOWS:
        cells=dict(schema_version='audio_cell_hypotheses.v1',source_id=records['mixture']['source_id'],timebase='source_video_seconds',start_s=lo,end_s=hi,
            data_origin='synthetic_cell_hypotheses',grid_id='synthetic_frequency_hypotheses_72cells',grid_version='synthetic.v1',
            frame_index=None,frame_pts_s=None,frame_pixel_sha256=None,geometry_source='not_provided_synthetic_pitch_hypotheses_only',
            anchor_status='unknown',spacing_source='not_generated',numbering_status='synthetic_fret_labels',
            tuning=dict(midi_6_to_1=STANDARD,status='assumed',source='explicit_standard_tuning_for_frequency_comparison_not_verified'),capo=None,
            assumptions=['6→1 standard tuning is an explicit assumption; no verified capo','Cells are synthetic frequency hypotheses, not upstream grid measurements','All six strings × physical frets1..12 chosen before audio scoring'],
            cells=[dict(cell_id=f's{s}_p{f}',virtual_string_num=s,physical_fret_candidate=f,is_virtual=True,estimated=True,contact='unknown',sounding='unknown') for s in range(6,0,-1) for f in range(1,13)])
        (root/f'cells_{lo:.2f}_{hi:.2f}.json').write_text(json.dumps(cells,indent=2))
        for name,audio in records.items():
            result=compare(cells,audio);result['provenance']['audio_evidence_file']=str(parent/name/'evidence.json');result['provenance']['audio_evidence_sha256']=digest(parent/name/'evidence.json')
            (root/f'{name}_{lo:.2f}_{hi:.2f}.json').write_text(json.dumps(result,indent=2))
            small=copy.deepcopy(result);small['cells']=[c for c in small['cells'] if c['cell_id'] in SMALL]
            small['provenance']['fixture_selection']='six fixed cell IDs independent of audio scores; full72 result adjacent'
            (root/'fixtures'/f'{name}_{lo:.2f}_{hi:.2f}.json').write_text(json.dumps(small,indent=2))
            if name=='accompaniment':
                scores=np.array([r['exact_frequency_score'] for r in result['cells']]).reshape(6,12)
                fig,ax=plt.subplots(figsize=(12,4));im=ax.imshow(scores,aspect='auto',vmin=0,vmax=1,cmap='viridis')
                ax.set_yticks(range(6),list(range(6,0,-1)));ax.set_xticks(range(12),range(1,13));ax.set_ylabel('Synthetic virtual string');ax.set_xlabel('Synthetic physical fret hypothesis')
                ax.set_title(f'{lo:.2f}–{hi:.2f}s accompaniment: frequency compatibility, NOT contact probability')
                fig.colorbar(im,ax=ax);fig.tight_layout();fig.savefig(root/f'compatibility_{lo:.2f}_{hi:.2f}.png');plt.close(fig)
                supports=[c for c in result['cells'] if c['exact_frequency_score']>0]
                pc_only=[c for c in result['cells'] if c['status']=='pitch_class_only_support']
                summary.append(dict(start_s=lo,end_s=hi,synthetic_cells=72,exact_candidate_supported_cells=len(supports),pc_only_cells=len(pc_only),
                    max_exact_score=max(c['exact_frequency_score'] for c in result['cells']),
                    all_contacts_unknown=True,selection_bias='Synthetic set fixed independently; counts are coverage over that set, not accuracy'))
                if failure is None:
                    cases=[c for c in pc_only if c['octave_alternatives']]
                    if cases:failure=dict(start_s=lo,end_s=hi,cell=cases[0],source_id=result['source_id'],data_origin='synthetic_cell_hypothesis_on_real_accompaniment',selection='first enumerated octave-only cell for diagnostic illustration; not independent evaluation')
    # Exact same source-time windows, using actual samples for all plots.
    arrays={};sr=None
    for name in records:sr,arrays[name]=wavfile.read(parent/name/'analysis.wav')
    offset=records['mixture']['start_s'];fig,axes=plt.subplots(3,2,figsize=(15,10))
    colors={'mixture':'#2864aa','accompaniment':'#dd7d18','vocals':'#954fad'}
    for row,(lo,hi) in enumerate(WINDOWS):
        a=round((lo-offset)*sr);b=round((hi-offset)*sr)
        for name,x in arrays.items():
            y=x[a:b];t=offset+np.arange(a,b)/sr
            axes[row,0].plot(t,y,lw=.6,label=name,color=colors[name],alpha=.8)
            mag=np.abs(np.fft.rfft(y*np.hanning(len(y))))
            hz=np.fft.rfftfreq(len(y),1/sr)
            axes[row,1].plot(hz,20*np.log10(np.maximum(mag,1e-9)),lw=.8,label=name,color=colors[name])
        axes[row,0].set_title(f'Actual source seconds {lo:.2f}–{hi:.2f}');axes[row,0].set_ylabel('Mono PCM amplitude')
        axes[row,1].set_xlim(65,1400);axes[row,1].set_ylim(-65,55);axes[row,1].set_ylabel('FFT magnitude (dB, arbitrary ref)');axes[row,1].set_xlabel('Hz');axes[row,1].grid(alpha=.3)
    axes[0,0].legend();axes[0,1].legend();fig.tight_layout();fig.savefig(root/'waveform_spectrum_comparison.png');plt.close(fig)
    if failure:
        (root/'fixtures'/'octave_only_example.json').write_text(json.dumps(failure,indent=2))
        c=failure['cell'];a=round((failure['start_s']-offset)*sr);b=round((failure['end_s']-offset)*sr);y=arrays['accompaniment'][a:b]
        hz=np.fft.rfftfreq(len(y),1/sr);mag=np.abs(np.fft.rfft(y*np.hanning(len(y))))
        fig,ax=plt.subplots(figsize=(12,4));ax.plot(hz,20*np.log10(np.maximum(mag,1e-9)),c=colors['accompaniment'],label='actual accompaniment spectrum')
        target=c['expected_pitch']['frequency_hz'];alt=c['octave_alternatives'][0]['frequency_hz']
        ax.axvline(target,c='green',ls='--',label=f'synthetic cell {c["cell_id"]} target {target:.1f}Hz')
        ax.axvline(alt,c='red',ls=':',label=f'actual octave-alternative peak {alt:.1f}Hz')
        ax.set_xlim(50,max(600,alt*1.2));ax.set_ylim(-65,55);ax.set_title(f'Unresolved octave case: exact={c["exact_frequency_score"]:.3f}, PC={c["pitch_class_score"]:.3f}; instrument unknown');ax.legend();fig.tight_layout();fig.savefig(root/'octave_only_failure.png');plt.close(fig)
    report=dict(schema_version='audio_cell_demo.v1',source_id=records['mixture']['source_id'],audio_data='actual_existing_demucs_v5',cell_data='synthetic_cell_hypotheses',
        grid_result_available_at_build=False,tuning_assumed_not_verified=True,capo=None,windows=summary)
    (root/'summary.json').write_text(json.dumps(report,indent=2))
    html='<meta charset="utf-8"><title>Cell/audio compatibility review</title><style>body{font:16px system-ui;max-width:1100px;margin:25px auto}img{max-width:100%}audio{width:90%}</style><h1>Real audio + synthetic cell hypotheses</h1><p>No grid/hand/contact ground truth. Standard tuning assumed. Accompaniment contains piano. Source seconds = player seconds + 3. No AV correction.</p>'
    for name in records:
        shutil_path=root/f'{name}_review.wav'
        # Copies are local review artifacts; untouched parent audio remains authoritative.
        import shutil
        shutil.copyfile(parent/name/'original.wav',shutil_path)
        html+=f'<h2>{name}</h2><audio controls src="{shutil_path.name}"></audio>'
    html+='<img src="waveform_spectrum_comparison.png"><img src="compatibility_5.05_5.35.png"><img src="octave_only_failure.png">'
    (root/'review.html').write_text(html,encoding='utf-8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--audio-parent',required=True);p.add_argument('--output',required=True);a=p.parse_args();build(a.audio_parent,a.output)
