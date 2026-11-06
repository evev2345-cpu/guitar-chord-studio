"""Compare fixed scoring variants on GuitarSet without using labels in prediction."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import hashlib
import json
from pathlib import Path
import time
import numpy as np
from scipy.io import wavfile
from joint_evidence_review import ROOT,read
from guitarset_benchmark import KNOWN_TIMING,load_reference,evaluate_layer,TEMPLATES,parse_chord
from chord_score_variants import score_variants
from audio_analysis import features
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ


def process(record):
    start=time.perf_counter();cache=ROOT/'dataset/audio_analysis/runs/guitarset_cut_chroma_20261105_v1';cache.mkdir(parents=True,exist_ok=True)
    path=cache/(record['recording_id']+'.npz');meta=path.with_suffix('.json')
    provenance=dict(audio_sha256=record['audio_sha256'],window_samples=8192,hop_samples=441,stride=10,band=[LOW_HZ,HIGH_HZ])
    if path.exists():
        if read(meta)!=provenance:raise ValueError('Cache provenance mismatch')
        with np.load(path) as data:sal=data['salience'];times=data['times']
    else:
        if hashlib.sha256(Path(record['audio_file']).read_bytes()).hexdigest()!=record['audio_sha256']:raise ValueError('Audio hash mismatch')
        rate,x=wavfile.read(record['audio_file']);x=x.astype(float)/32768
        evidence,_=features(band_cut(x,rate),rate,min_frequency=LOW_HZ,max_frequency=HIGH_HZ)
        rows=evidence['pitch_class_salience'][::10];sal=np.array([r['salience'] for r in rows]);times=np.array([r['time_s'] for r in rows])
        np.savez_compressed(path,salience=sal,times=times);meta.write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    layers,_=load_reference(record['annotation_file']);variants={}
    for name,(scores,rank,usable) in score_variants(sal).items():
        variants[name]={layer:evaluate_layer(times,rank,scores,usable,events) for layer,events in layers.items()}
    frozen=read(ROOT/'dataset/integration_review/runs/guitarset_benchmark_20261105_v1/records'/(record['recording_id']+'.json'))
    for layer in layers:
        if variants['legacy'][layer]['counts']!=frozen['branches']['cut'][layer]['counts']:raise ValueError('Frozen baseline replay mismatch')
    return dict(recording_id=record['recording_id'],audio_file=record['audio_file'],annotation_file=record['annotation_file'],
                variants=variants,baseline_replay_exact=True,elapsed_s=time.perf_counter()-start)


def aggregate(records):
    result={}
    for scope,items in [('primary',[r for r in records if r['recording_id'] not in KNOWN_TIMING]),('all',records)]:
        group=dict(files=len(items),variants={})
        for name in ['legacy','cosine','cosine_context']:
            variant={}
            for layer in ['nominal','performed']:
                counts=Counter();qualities={}
                for record in items:
                    counts.update(record['variants'][name][layer]['counts'])
                    for f in record['variants'][name][layer]['frames']:
                        ref=parse_chord(f['reference']);quality=next((t['quality'] for t in TEMPLATES if t['root_pc']==ref['root_pc'] and tuple(t['pcs'])==ref['pcs']),'outside_dictionary')
                        q=qualities.setdefault(quality,Counter());q['evaluated']+=1;q['top1']+=int(f['correct_top1'])
                denominator=counts['evaluated'];covered=counts['representable']
                variant[layer]=dict(counts=dict(counts),top1=counts['top1']/denominator,top3=counts['top3']/denominator,
                    root_top1=counts['root_top1']/denominator,representable_top1=counts['representable_top1']/max(1,covered),
                    per_quality={k:dict(v) for k,v in qualities.items()})
            group['variants'][name]=variant
        result[scope]=group
    return result


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--limit',type=int);a=p.parse_args()
    out=a.output
    if (out/'summary.json').exists():raise FileExistsError(out)
    (out/'records').mkdir(parents=True,exist_ok=True)
    records=[r for r in read(ROOT/'dataset/integration_review/runs/guitarset_audio_ready_20261105_v1/manifest.json')['rows'] if r['performance']=='comp']
    if a.limit:records=records[:a.limit]
    config=dict(variants=['legacy','cosine','cosine_context'],training=False,parameter_fitting=False,
        context='3 sampled score frames, centered +-100ms; no reference boundaries used in predictions',
        changes='L2 cosine template normalization; allow >=2 active PCs; optional temporal score average',
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scorer_sha256=hashlib.sha256((ROOT/'chord_score_variants.py').read_bytes()).hexdigest())
    if (out/'config.json').exists() and read(out/'config.json')!=config:raise ValueError('Configuration changed')
    (out/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8')
    todo=[r for r in records if not (out/'records'/(r['recording_id']+'.json')).exists()];done=len(records)-len(todo)
    with ProcessPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(process,r) for r in todo]):
            result=future.result();path=out/'records'/(result['recording_id']+'.json');path.write_text(json.dumps(result,indent=2),encoding='utf-8')
            done+=1;print(done,'/',len(records),result['recording_id'],flush=True)
    results=[read(out/'records'/(r['recording_id']+'.json')) for r in records]
    summary=aggregate(results);(out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Completed',len(records),flush=True)


if __name__=='__main__':main()
