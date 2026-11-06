"""Offline mixed-source diagnostics. Components are NOT vocal/guitar source stems."""
import argparse
import copy
import hashlib
import importlib.metadata
import importlib.util
import json
import shutil
import sys
import time
from pathlib import Path
import numpy as np
from scipy import signal, ndimage
from scipy.io import wavfile
from audio_analysis import analyze, time_local_evidence


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_listening_review(manifest, review):
    if review['source_id'] != manifest['source_id'] or review['timebase'] != manifest['timebase']:
        raise ValueError('Listening review source/timebase mismatch')
    tolerance=1/manifest['sample_rate']
    if review['start_s']>manifest['start_s']+tolerance or review['end_s']<manifest['end_s']-tolerance:
        raise ValueError('Listening review does not cover analysis interval')
    if review['instrument_mix']!='vocal_and_guitar' or review['listening_status']!='user_reported_performed':
        raise ValueError('Expected explicitly reviewed vocal/guitar mixture')


def hps_components(stereo, rate, nperseg=2048, hop=512, median_bins=31):
    """Median-filter soft masks; retain both outputs, with no instrument labels."""
    x=np.asarray(stereo,dtype=float)
    if x.ndim!=2 or x.shape[1]!=2 or not np.isfinite(x).all():
        raise ValueError('Finite stereo samples required')
    _,_,z=signal.stft(x,fs=rate,nperseg=nperseg,noverlap=nperseg-hop,axis=0,boundary='zeros',padded=True)
    mag=np.abs(z).mean(axis=1)  # frequency,time
    horizontal=ndimage.median_filter(mag,size=(1,median_bins),mode='reflect')
    vertical=ndimage.median_filter(mag,size=(median_bins,1),mode='reflect')
    denom=horizontal**2+vertical**2
    mask=np.divide(horizontal**2,denom,out=np.full_like(denom,.5),where=denom>1e-20)
    components=[]
    for weight in [mask,1-mask]:
        _,y=signal.istft(z*weight[:,None,:],fs=rate,nperseg=nperseg,noverlap=nperseg-hop,
                         time_axis=2,freq_axis=0,boundary=True)
        components.append(y.T[:len(x)])
    return components


def channel_diagnostics(stereo):
    x=np.asarray(stereo,dtype=float);left,right=x.T
    mid=(left+right)/2;side=(left-right)/2
    power=float(np.mean(x*x))
    return dict(channel_correlation=float(np.corrcoef(left,right)[0,1]) if np.std(left)*np.std(right)>0 else None,
        mid_energy_ratio=float(np.mean(mid*mid)/max(power,1e-20)),
        side_energy_ratio=float(np.mean(side*side)/max(power,1e-20)),
        interpretation='Spatial energy only; center content can contain vocals AND guitar. Side is not accompaniment.')


def inventory():
    modules=['torch','torchaudio','demucs','spleeter','librosa','soundfile','onnxruntime','audio_separator','openunmix']
    caches=[Path.home()/p for p in ['.cache/torch/hub/checkpoints','.cache/torch/hub','.cache/huggingface/hub','.cache/audio-separator-models']]
    result=dict(python=sys.version,executable=sys.executable,modules={m:bool(importlib.util.find_spec(m)) for m in modules},
        cache_search=[dict(path=str(p),exists=p.exists(),files=[str(x) for x in p.iterdir()] if p.exists() else []) for p in caches],
        repo_model_files=[str(p) for ext in ['*.pt','*.pth','*.th','*.ckpt','*.onnx'] for p in Path('.').rglob(ext)],
        scope='Active Python interpreter, repository model suffixes, standard Torch/HuggingFace/audio-separator cache roots; not all external disks/environments',
        learned_separation_status='unavailable_no_identified_package_and_weights',downloads=0,installations=0)
    if result['modules']['torch']:
        import torch
        result.update(torch_version=torch.__version__,cuda_available=torch.cuda.is_available(),cuda_build=torch.version.cuda)
    return result


def mark_mixture(record, provenance, component):
    record['source_identity']={'input_mix':'vocal_and_guitar','other_sources':'unknown',
        'component':component,'instrument_attribution':'unknown','guitar_isolation_verified':False}
    record['provenance']['listening_review']=copy.deepcopy(provenance)
    record['limitations']=[v for v in record['limitations'] if not v.startswith('Listening,')]
    record['limitations']+=['User confirmed vocals + guitar only at source-type level; onset/pitch/AV sync remain unreviewed',
        'Mixed-source or transformed spectral peaks cannot be attributed to guitar',
        'Harmonic/percussive and spatial components are not vocals/accompaniment separation']
    for key in ['onsets','legacy_long_window_onsets','pitch_candidates','pitch_tracks','pitch_class_salience','acoustic_events']:
        for event in record.get(key,[]):
            event['instrument_attribution']='unknown'
            event['source_component']=component
    return record


def run(manifest, review_path, output):
    started=time.perf_counter();parent=Path(manifest).resolve();m=json.loads(parent.read_text())
    review_path=Path(review_path).resolve();review=json.loads(review_path.read_text(encoding='utf-8-sig'))
    validate_listening_review(m,review)
    root=Path(output);root.mkdir(parents=True,exist_ok=False)
    local_inventory=inventory();(root/'local_environment.json').write_text(json.dumps(local_inventory,indent=2))
    rate,stereo=wavfile.read(parent.parent/m['files']['original'])
    if rate!=m['sample_rate'] or stereo.shape[1]!=2:raise ValueError('Unexpected input audio format')
    h,p=hps_components(stereo,rate)
    mid=stereo.mean(axis=1);side=(stereo[:,0]-stereo[:,1])/2
    wavfile.write(root/'mid_component.wav',rate,np.column_stack([mid,mid]).astype(np.float32))
    wavfile.write(root/'side_component.wav',rate,np.column_stack([side,-side]).astype(np.float32))
    proof=dict(path=str(review_path),sha256=digest(review_path),reviewer=review['reviewer'],
               listening_status=review['listening_status'],instrument_mix=review['instrument_mix'],
               scope=review['scope'],source_id=m['source_id'])
    branch_results={}
    for component,data in [('mixture',stereo),('harmonic_component',h),('percussive_component',p)]:
        folder=root/component;folder.mkdir()
        if component=='mixture':shutil.copyfile(parent.parent/m['files']['original'],folder/'original.wav')
        else:wavfile.write(folder/'original.wav',rate,data.astype(np.float32))
        wavfile.write(folder/'analysis.wav',rate,data.mean(axis=1).astype(np.float32))
        mm=copy.deepcopy(m);mm['run_id']=root.name+'_'+component
        mm['provenance_parent_manifest']=str(parent);mm['processing']['component']=component
        mm['processing']['source_separation']='not_instrument_separated'
        mm['processing']['hpss']=None if component=='mixture' else dict(window_samples=2048,hop_samples=512,median_bins=31,mask_power=2,phase='original mixture phase',boundary='zeros; matching padded ISTFT; cropped to original length')
        mm['source_identity']={'input_mix':'vocal_and_guitar','other_sources':'unknown','component':component,'instrument_attribution':'unknown','guitar_isolation_verified':False}
        mm['listening_review']=copy.deepcopy(proof)
        mm['original_file_sha256']=digest(folder/'original.wav');mm['parent_manifest_sha256']=digest(parent)
        (folder/'manifest.json').write_text(json.dumps(mm,indent=2))
        e=mark_mixture(analyze(folder/'manifest.json',split_windows=True),proof,component)
        (folder/'evidence.json').write_text(json.dumps(e,indent=2));branch_results[component]=e
        fixtures=folder/'fixtures';fixtures.mkdir()
        for lo,hi in [(5.05,5.35),(7.8,8.1),(8.75,9.05)]:
            local=time_local_evidence(e,lo,hi)
            local['source_identity']=copy.deepcopy(e['source_identity'])
            (fixtures/f'audio_{lo:.2f}_{hi:.2f}.json').write_text(json.dumps(local,indent=2))
    comparisons=[]
    for lo,hi in [(5.05,5.35),(7.8,8.1),(8.75,9.05)]:
        row=dict(start_s=lo,end_s=hi,source_identity='unknown',components={})
        baseline=None
        for component,e in branch_results.items():
            local=time_local_evidence(e,lo,hi)
            frames=np.array([f['salience'] for f in local['pitch_class_salience']])
            sal=frames.mean(axis=0) if len(frames) else np.zeros(12)
            if baseline is None:baseline=sal
            row['components'][component]=dict(pitch_class_salience=sal.tolist(),
                salience_total_variation_from_mixture=float(.5*np.abs(sal-baseline).sum()),
                peak_record_count=len(local['pitch_candidates']),
                top_pitch_classes=np.argsort(sal)[::-1][:3].tolist(),
                status='provisional_mixed_source_candidates_not_guitar_notes')
        comparisons.append(row)
    metrics=dict(schema_version='audio_mixture_diagnostics.v1',source_id=m['source_id'],
        run_id=root.name,start_s=m['start_s'],end_s=m['end_s'],timebase=m['timebase'],listening_review=proof,
        source_identity={'mix':'vocal_and_guitar','other_sources':'unknown','guitar_attribution':'unknown'},
        learned_separation_status=local_inventory['learned_separation_status'],vocals_stem=None,accompaniment_stem=None,
        spatial_diagnostics=channel_diagnostics(stereo),sample_rate=rate,sample_count=len(stereo),channels=2,
        local_to_source_offset_s=m['local_to_source_offset_s'],applied_av_correction_s=0.,
        hpss_reconstruction_max_abs_error=float(np.max(np.abs(h+p-stereo))),
        hpss_reconstruction_rms_error=float(np.sqrt(np.mean((h+p-stereo)**2))),
        harmonic_energy_ratio=float(np.mean(h*h)/max(np.mean(stereo.astype(float)**2),1e-20)),
        percussive_energy_ratio=float(np.mean(p*p)/max(np.mean(stereo.astype(float)**2),1e-20)),
        energy_ratio_note='Soft-mask component energies are not additive or source proportions',
        separation_quality={'residual_vocals':'unreviewed','guitar_loss':'unreviewed','audible_artifacts':'unreviewed',
            'reason':'No isolated reference stems or listening assessment; reconstruction checks cannot measure source quality'},
        comparisons=comparisons,elapsed_s=time.perf_counter()-started)
    (root/'diagnostics.json').write_text(json.dumps(metrics,indent=2))
    return metrics


def quality(root):
    root=Path(root);d=json.loads((root/'diagnostics.json').read_text())
    arrays={};manifests={}
    for name in ['mixture','harmonic_component','percussive_component']:
        folder=root/name
        sr,x=wavfile.read(folder/'original.wav');arrays[name]=x
        m=json.loads((folder/'manifest.json').read_text());manifests[name]=m
        if sr!=d['sample_rate'] or x.shape!=(d['sample_count'],2):
            raise ValueError('Component sample grid mismatch')
        if m['source_id']!=d['source_id'] or m['local_to_source_offset_s']!=d['local_to_source_offset_s']:
            raise ValueError('Component original source/time mapping mismatch')
    residual=arrays['harmonic_component'].astype(float)+arrays['percussive_component'].astype(float)-arrays['mixture']
    qa=dict(status='sample_grid_verified_not_source_separation_quality',
        source_id=d['source_id'],sample_rate=d['sample_rate'],sample_count=d['sample_count'],channels=2,
        all_same_source_and_time_mapping=True,saved_float32_reconstruction_max_abs_error=float(np.max(np.abs(residual))),
        residual_vocals='unreviewed',guitar_loss='unreviewed',audible_artifacts='unreviewed')
    (root/'quality_checks.json').write_text(json.dumps(qa,indent=2))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(10,8))
    for ax,row in zip(axes,d['comparisons']):
        image=np.array([c['pitch_class_salience'] for c in row['components'].values()])
        ax.imshow(image,aspect='auto',vmin=0,vmax=.5,cmap='magma')
        ax.set_yticks(range(3),['mixture','harmonic component','percussive component'])
        ax.set_xticks(range(12),['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'])
        ax.set_title(f"{row['start_s']:.2f}–{row['end_s']:.2f}s: mixed-source salience, not guitar notes")
    fig.tight_layout();fig.savefig(root/'component_chroma_comparison.png');plt.close(fig)
    html='<meta charset="utf-8"><title>Mixed-source diagnostic components</title><style>body{font:16px system-ui;max-width:950px;margin:30px auto}audio{width:90%}</style><h1>Vocals + guitar: diagnostic components</h1><p>User confirmed source types. No component is guitar-only or validated accompaniment. Source seconds = local seconds + 3. No AV correction.</p>'
    for name in ['mixture','harmonic_component','percussive_component']:
        html+=f'<h2>{name}</h2><audio controls src="{name}/original.wav"></audio>'
    html+='<h2>Spatial side component (not accompaniment)</h2><audio controls src="side_component.wav"></audio><p>Residual vocals, guitar loss and audible artifacts remain unreviewed.</p><img style="max-width:100%" src="component_chroma_comparison.png">'
    (root/'component_review.html').write_text(html,encoding='utf-8')
    return qa


if __name__=='__main__':
    cli=argparse.ArgumentParser();cli.add_argument('--manifest',required=True);cli.add_argument('--review',required=True);cli.add_argument('--output',required=True)
    args=cli.parse_args();run(args.manifest,args.review,args.output);quality(args.output)
