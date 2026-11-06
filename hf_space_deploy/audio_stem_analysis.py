"""Compare existing local separation stems; never performs inference or downloads."""
import argparse
import copy
import json
import shutil
import time
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from audio_analysis import analyze, time_local_evidence
from audio_mixture_diagnostics import digest

WINDOWS=[(5.05,5.35),(7.80,8.10),(8.75,9.05)]


def validate_upstream(m, separation, review, parent_audio, accompaniment):
    if review['source_id']!=m['source_id'] or review['timebase']!=m['timebase']:
        raise ValueError('Review source mismatch')
    if review['audio_sha256']!=digest(accompaniment) or separation['input_sha256']!=digest(parent_audio):
        raise ValueError('Audio hash mismatch')
    tolerance=1/m['sample_rate']
    if abs(review['start_s']-m['start_s'])>tolerance or abs(review['end_s']-m['end_s'])>tolerance:
        raise ValueError('Review time interval mismatch')
    if not review['derived_from_separation'] or review['guitar_isolation_verified']:
        raise ValueError('Expected unverified-guitar separation review')


def namespace_events(record, component):
    mapping={}
    for key in ['onsets','legacy_long_window_onsets','pitch_candidates','pitch_tracks','acoustic_events','pitch_class_salience']:
        for i,event in enumerate(record.get(key,[])):
            old=event.get('event_id',f'chroma_{i}')
            event['event_id']=f'{component}:{old}';mapping[old]=event['event_id']
            event.update(instrument_attribution='unknown',source_component=component,
                         derived_from_separation=component!='mixture')
    for track in record.get('pitch_tracks',[]):
        track['evidence_ids']=[mapping[x] for x in track['evidence_ids']]
        for item in track['harmonic_ambiguities']:
            item['lower_event_id']=mapping[item['lower_event_id']]
    return record


def vocal_coincidences(record, vocals, cents=35.):
    """Compare same STFT frame peaks; coincidence is NOT measured leakage."""
    hop=record['provenance']['hop_samples']/record['provenance']['window_samples']*record['provenance']['window_support_s']
    frame=lambda p:int(round((p['start_s']-record['start_s'])/hop))
    lookup={}
    for p in vocals['pitch_candidates']:lookup.setdefault(frame(p),[]).append(p)
    for p in record['pitch_candidates']:
        p['coincident_vocal_stem_evidence_ids']=[v['event_id'] for v in lookup.get(frame(p),[]) if abs(1200*np.log2(p['frequency_hz']/v['frequency_hz']))<=cents]
        p['vocal_coincidence_interpretation']='shared pitch or model leakage or harmonic coincidence; not instrument attribution'


def comparison_candidates(local):
    groups={}
    for p in local['pitch_candidates']:groups.setdefault(round(p['midi']),[]).append(p)
    return [dict(candidate_id=f"{local['run_id']}:window_{local['start_s']:.2f}_{local['end_s']:.2f}:midi_{midi}",
        midi_candidate=midi,median_frequency_hz=float(np.median([x['frequency_hz'] for x in items])),
        median_cents_from_midi=float(np.median([(x['midi']-midi)*100 for x in items])),
        score=float(np.median([x['score'] for x in items])),score_type='median_relative_spectral_peak_amplitude',
        peak_record_count=len(items),distinct_analysis_frame_count=len({x['start_s'] for x in items}),
        start_s=local['start_s'],end_s=local['end_s'],
        evidence_ids=[x['event_id'] for x in items],
        coincident_vocal_stem_evidence_ids=sorted({v for x in items for v in x.get('coincident_vocal_stem_evidence_ids',[])}),
        pitch_status='spectral_peak_candidate',instrument_attribution='unknown',string_num=None,contact='unknown',
        interpretation='Frequency matching aid only; fingering compatibility is not confirmed guitar sound')
        for midi,items in sorted(groups.items())]


def run(parent_manifest, separation_manifest, review_path, output):
    started=time.perf_counter();parent=Path(parent_manifest).resolve();sep_path=Path(separation_manifest).resolve();review_path=Path(review_path).resolve()
    m=json.loads(parent.read_text());sep=json.loads(sep_path.read_text());review=json.loads(review_path.read_text(encoding='utf-8-sig'))
    stems=sep_path.parent/'htdemucs'/'original';paths={'mixture':parent.parent/m['files']['original'],'accompaniment':stems/'no_vocals.wav','vocals':stems/'vocals.wav'}
    validate_upstream(m,sep,review,paths['mixture'],paths['accompaniment'])
    upstream_qa_path=sep_path.parent/'quality_checks.json'
    upstream_qa=json.loads(upstream_qa_path.read_text())
    if upstream_qa['source_id']!=m['source_id']:
        raise ValueError('Separation QA original source mismatch')
    for component,key in [('accompaniment','no_vocals'),('vocals','vocals')]:
        if digest(paths[component])!=upstream_qa['outputs'][key]['sha256']:
            raise ValueError('Stem differs from upstream QA hash')
    arrays={}
    for name,path in paths.items():
        sr,x=wavfile.read(path)
        if sr!=m['sample_rate'] or x.shape!=(m['clip_end_sample']-m['clip_first_sample'],2) or not np.isfinite(x).all():
            raise ValueError('Stem sample grid mismatch or nonfinite data')
        arrays[name]=x
    root=Path(output);root.mkdir(parents=True,exist_ok=False);records={}
    provenance={'source_manifest':str(parent),'source_manifest_sha256':digest(parent),
        'separation_qa':str(upstream_qa_path),'separation_qa_sha256':digest(upstream_qa_path),
        'separation_manifest':str(sep_path),'separation_manifest_sha256':digest(sep_path),
        'model_manifest':str(Path('docs/audio-separation-model-manifest.json').resolve()),
        'model_manifest_sha256':digest('docs/audio-separation-model-manifest.json'),
        'user_listening_review':str(review_path),'user_listening_review_sha256':digest(review_path),
        'user_scope':review['scope'],'vocal_removal_quality':review['vocal_removal_quality'],
        'no_new_inference_or_download':True,'model_timing_validation':'sample_grid_only; internal latency/AV sync unverified'}
    for name,path in paths.items():
        folder=root/name;folder.mkdir();shutil.copyfile(path,folder/'original.wav')
        wavfile.write(folder/'analysis.wav',sr,arrays[name].mean(axis=1).astype(np.float32))
        mm=copy.deepcopy(m);mm['run_id']=root.name+'_'+name;mm['analysis_parent_audio']=str(path);mm['analysis_parent_sha256']=digest(path)
        mm['source_identity']={'component':name,'derived_from_separation':name!='mixture','guitar_isolation_verified':False,
            'instrument_attribution':'unknown','piano_audible_in_reviewed_accompaniment':True,
            'component_status':'original_mixture' if name=='mixture' else 'model_estimate'}
        mm['processing']['component']=name;mm['separation_provenance']=provenance
        (folder/'manifest.json').write_text(json.dumps(mm,indent=2))
        e=namespace_events(analyze(folder/'manifest.json',split_windows=True),name)
        e['source_identity']=copy.deepcopy(mm['source_identity']);e['provenance']['separation']=copy.deepcopy(provenance)
        e['limitations']=[x for x in e['limitations'] if not x.startswith('Listening,')]
        e['limitations']+=['User reports good vocal reduction and audible piano in accompaniment; no quantitative quality claim',
            'Accompaniment contains piano; spectral peaks are not verified guitar notes',
            'Vocal-stem peak coincidence may reflect shared notes, harmonics or model leakage; not a residual-vocal measurement',
            'No isolated guitar labels, contact labels or AV synchronization ground truth']
        records[name]=e
    vocal_coincidences(records['accompaniment'],records['vocals'])
    summaries=[];indexes=[]
    for name,e in records.items():
        folder=root/name;(folder/'evidence.json').write_text(json.dumps(e,indent=2));(folder/'fixtures').mkdir()
        for lo,hi in WINDOWS:
            local=time_local_evidence(e,lo,hi);local['fingering_comparison_candidates']=comparison_candidates(local)
            for c in local['fingering_comparison_candidates']:
                c['persistence_context']=[dict(event_id=t['event_id'],overlap_start_s=max(t['start_s'],lo),overlap_end_s=min(t['end_s'],hi),status='persistent_spectral_peak_candidate',parent_evidence='../evidence.json') for t in e['pitch_tracks'] if set(c['evidence_ids']).intersection(t['evidence_ids'])]
            (folder/'fixtures'/f'audio_{lo:.2f}_{hi:.2f}.json').write_text(json.dumps(local,indent=2))
            indexes.append(dict(component=name,start_s=lo,end_s=hi,candidates=local['fingering_comparison_candidates']))
    for lo,hi in WINDOWS:
        row=dict(start_s=lo,end_s=hi,components={});baseline=None
        for name,e in records.items():
            local=time_local_evidence(e,lo,hi);frames=np.array([x['salience'] for x in local['pitch_class_salience']]);sal=frames.mean(axis=0)
            if baseline is None:baseline=sal
            a=round((lo-m['start_s'])*sr);b=round((hi-m['start_s'])*sr)
            energy=float(np.mean(arrays[name][a:b].astype(float)**2));mixenergy=float(np.mean(arrays['mixture'][a:b].astype(float)**2))
            row['components'][name]=dict(pitch_class_salience=sal.tolist(),salience_total_variation_from_mixture=float(.5*np.abs(sal-baseline).sum()),
                pitch_peak_records=len(local['pitch_candidates']),fully_contained_tracks=len(local['pitch_tracks']),
                overlapping_tracks=sum(t['start_s']<hi and t['end_s']>lo for t in e['pitch_tracks']),
                rms=float(np.sqrt(energy)),energy_ratio_to_mixture=energy/mixenergy,
                vocal_stem_coincident_peak_records=sum(bool(x.get('coincident_vocal_stem_evidence_ids')) for x in local['pitch_candidates']) if name=='accompaniment' else None)
        summaries.append(row)
    residual=arrays['accompaniment'].astype(float)+arrays['vocals'].astype(float)-arrays['mixture']
    result=dict(schema_version='audio_stem_comparison.v1',source_id=m['source_id'],run_id=root.name,
        start_s=m['start_s'],end_s=m['end_s'],timebase=m['timebase'],sample_rate=sr,sample_count=len(residual),channels=2,
        local_to_source_offset_s=m['local_to_source_offset_s'],applied_av_correction_s=0.,sample_grid_verified=True,
        reconstruction_max_abs_error=float(np.max(np.abs(residual))),reconstruction_rms_error=float(np.sqrt(np.mean(residual**2))),
        provenance=provenance,components={name:dict(onsets=len(e['onsets']),pitch_peak_records=len(e['pitch_candidates']),
            persistent_peak_tracks=len(e['pitch_tracks']),harmonic_ambiguous_tracks=sum(bool(t['harmonic_ambiguities']) for t in e['pitch_tracks']),
            pcm_sha256=digest(root/name/'original.wav')) for name,e in records.items()},
        comparisons=summaries,vocal_peak_coincidence_tolerance_cents=35.,
        quality={'vocal_reduction':'user_reports_good_not_quantified','piano_in_accompaniment':'user_confirmed_audible',
            'residual_vocal_amount':'unmeasured','guitar_loss':'unreviewed','audible_artifacts':'unreviewed','guitar_isolation_verified':False},
        elapsed_s=time.perf_counter()-started)
    (root/'comparison.json').write_text(json.dumps(result,indent=2))
    (root/'fingering_comparison_index.json').write_text(json.dumps({'source_id':m['source_id'],'status':'provisional_frequency_matching_only','no_fingering_labels_consumed':True,'windows':indexes},indent=2))
    plot(root,result)
    return result


def plot(root,result):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(11,8))
    for ax,row in zip(axes,result['comparisons']):
        ax.imshow([v['pitch_class_salience'] for v in row['components'].values()],aspect='auto',vmin=0,vmax=.5,cmap='magma')
        ax.set_yticks(range(3),list(row['components']));ax.set_xticks(range(12),['C','C#','D','D#','E','F','F#','G','G#','A','A#','B'])
        ax.set_title(f"{row['start_s']:.2f}–{row['end_s']:.2f}s: source attribution unknown")
    fig.tight_layout();fig.savefig(root/'stem_chroma_comparison.png');plt.close(fig)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--separation-manifest',required=True);p.add_argument('--review',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();run(a.manifest,a.separation_manifest,a.review,a.output)
