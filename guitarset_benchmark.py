"""Frozen audio baseline on all GuitarSet comp files, with distinct reference layers.

No training, hand simulation, parameter fitting, or modification of source data.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from collections import Counter
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import time
import numpy as np
from scipy.io import wavfile
from audio_analysis import features
from harmony_engine import QUALITIES,NAMES,SUFFIX
from sweep_bandcut_vision_weights import band_cut,LOW_HZ,HIGH_HZ
from joint_evidence_review import ROOT,read

KNOWN_TIMING={'04_BN3-154-E_comp':.409,'04_Jazz1-200-B_comp':.309}
KNOWN_DUPLICATE='02_Funk2-119-G_comp'
SHORTHANDS={'maj':(0,4,7),'min':(0,3,7),'dim':(0,3,6),'aug':(0,4,8),
 'sus2':(0,2,7),'sus4':(0,5,7),'7':(0,4,7,10),'maj7':(0,4,7,11),
 'min7':(0,3,7,10),'hdim7':(0,3,6,10),'dim7':(0,3,6,9),'maj6':(0,4,7,9),
 'min6':(0,3,7,9),'minmaj7':(0,3,7,11),'9':(0,4,7,10,2),'maj9':(0,4,7,11,2),
 'min9':(0,3,7,10,2),'11':(0,4,7,10,2,5),'min11':(0,3,7,10,2,5)}
TEMPLATES=sorted([dict(root_pc=root,quality=quality,pcs=sorted({(root+i)%12 for i in intervals}),
                          symbol=NAMES[root]+SUFFIX.get(quality,quality))
                  for root in range(12) for quality,intervals in QUALITIES.items()],key=lambda c:(c['root_pc'],c['quality']))


def degree(text):
    match=re.fullmatch(r'([b#]*)([1-9][0-9]*)',text)
    if match is None:raise ValueError('Unsupported degree: '+text)
    accidental,number=match.groups();n=int(number)-1
    return ([0,2,4,5,7,9,11][n%7]+12*(n//7)+accidental.count('#')-accidental.count('b'))%12


@lru_cache(None)
def parse_chord(label):
    if label in ('N','X'):return None
    match=re.fullmatch(r'([A-G])([#b]*)(?::([^/]*))?(?:/([^/]+))?',label)
    if match is None:raise ValueError('Unsupported chord label: '+label)
    letter,accidental,body,bass=match.groups()
    root=({'C':0,'D':2,'E':4,'F':5,'G':7,'A':9,'B':11}[letter]+accidental.count('#')-accidental.count('b'))%12
    body='maj' if body is None or body=='' else body
    parts=re.fullmatch(r'([^()]*)\(([^()]*)\)',body)
    mods=[]
    if parts:
        quality,extensions=parts.groups();mods=[x.strip() for x in extensions.split(',') if x.strip()]
    else:quality=body
    if quality=='':intervals={0}
    elif quality in SHORTHANDS:intervals=set(SHORTHANDS[quality])
    else:raise ValueError('Unsupported chord quality: '+label)
    # Root is explicit in Harte encodings; apply omissions/additions before adding bass.
    intervals.add(0)
    for extension in mods:
        if extension.startswith('*'):intervals.discard(degree(extension[1:]))
        else:intervals.add(degree(extension))
    intervals.add(degree(bass or '1'))
    pcs=tuple(sorted((root+i)%12 for i in intervals))
    representable=any(t['root_pc']==root and tuple(t['pcs'])==pcs for t in TEMPLATES)
    return dict(root_pc=root,pcs=pcs,representable=representable,bass_ignored_as_separate_metric=True)


def rank_saliences(saliences):
    """Vectorized existing coverage score, same dictionary and stable tie ordering."""
    sal=np.asarray(saliences,float);total=sum(sal[:,i] for i in range(12))
    active=(sal>0)&(sal>=.1*sal.max(axis=1)[:,None]);usable=(total>0)&(active.sum(axis=1)>=3)
    scores=np.full((len(sal),len(TEMPLATES)),-np.inf)
    for j,template in enumerate(TEMPLATES):
        target={(template['root_pc']+i)%12 for i in QUALITIES[template['quality']]}
        coverage=sum(sal[:,i] for i in target)/np.maximum(total,1e-300)
        missing=sum(~active[:,i] for i in target)
        scores[usable,j]=(coverage-.15*missing/len(target))[usable]
    order=np.argsort(-scores,axis=1,kind='stable')
    return scores,order,usable


def load_reference(path):
    data=read(path);layers={};notes=[]
    for annotation in data['annotations']:
        namespace=annotation['namespace'];source=annotation['annotation_metadata'].get('data_source')
        if namespace=='chord':
            layer='performed' if source=='Semi-automatic chord transcription with manual verification' else 'nominal' if not source else 'unknown'
            if layer in layers:raise ValueError('Duplicate chord layer')
            layers[layer]=annotation['data']
        elif namespace=='note_midi':
            if source not in list('012345'):raise ValueError('Unexpected string label')
            notes.extend(dict(start=e['time'],end=e['time']+e['duration'],midi=e['value'],string_source=source) for e in annotation['data'])
    if set(layers)!={'nominal','performed'}:raise ValueError('Expected distinct nominal/performed layers')
    return layers,notes


def evaluate_layer(time_s,rank,scores,usable,events):
    counts=Counter();traces=[];unknown=Counter();confusion=Counter()
    for i,t in enumerate(time_s):
        event=next((e for e in events if e['time']+.05+4096/44100<=t<e['time']+e['duration']-.05-4096/44100),None)
        if event is None:counts['boundary_or_unlabeled']+=1;continue
        try:reference=parse_chord(event['value'])
        except ValueError:unknown[event['value']]+=1;continue
        if reference is None:counts['no_chord_or_unknown_label']+=1;continue
        counts['evaluated']+=1
        if reference['representable']:counts['representable']+=1
        top=[TEMPLATES[j] for j in rank[i,:3]] if usable[i] else []
        matching=lambda c:c['root_pc']==reference['root_pc'] and tuple(c['pcs'])==reference['pcs']
        correct=bool(top and matching(top[0]));top3=any(matching(c) for c in top)
        counts['top1']+=int(correct);counts['top3']+=int(top3)
        counts['root_top1']+=int(bool(top and top[0]['root_pc']==reference['root_pc']))
        counts['abstain']+=int(not usable[i])
        if reference['representable']:
            counts['representable_top1']+=int(correct);counts['representable_top3']+=int(top3)
        if not correct and top:confusion[event['value']+' -> '+top[0]['symbol']]+=1
        traces.append(dict(time_s=float(t),reference=event['value'],reference_pcs=reference['pcs'],representable=reference['representable'],
            top3=[dict(symbol=c['symbol'],root_pc=c['root_pc'],quality=c['quality'],score=float(scores[i,j])) for c,j in zip(top,rank[i,:3])],
            correct_top1=correct,correct_top3=top3))
    return dict(counts=dict(counts),unparsed=dict(unknown),confusions=dict(confusion),frames=traces)


def evaluate_pitches(time_s,predictions,notes):
    counts=Counter();traces=[]
    for t,pred in zip(time_s,predictions):
        active=[n for n in notes if n['start']<=t<n['end']]
        reference={int(round(n['midi'])) for n in active};estimated={int(round(m)) for m in pred}
        tp=reference&estimated;fp=estimated-reference;fn=reference-estimated
        counts.update(dict(tp=len(tp),fp=len(fp),fn=len(fn),frames=1))
        refpcs={n%12 for n in reference};estpcs={n%12 for n in estimated}
        counts.update(dict(pc_tp=len(refpcs&estpcs),pc_fp=len(estpcs-refpcs),pc_fn=len(refpcs-estpcs)))
        harmonic=[]
        for midi in fp:
            if any(min(abs((midi-n['midi'])-12*np.log2(k))*100 for k in range(2,9))<=35 for n in active):harmonic.append(midi)
        counts['false_pitches_near_reference_harmonics']+=len(harmonic)
        if active:counts['reference_active_frames']+=1
        traces.append(dict(time_s=float(t),reference_midi=sorted(reference),predicted_midi=sorted(estimated),
                           false_positive_midi=sorted(fp),missing_midi=sorted(fn),possible_harmonic_false_midi=harmonic))
    return dict(counts=dict(counts),frames=traces)


def process_record(record):
    started=time.perf_counter()
    for field,sha in [('audio_file','audio_sha256'),('annotation_file','annotation_sha256')]:
        if hashlib.sha256(Path(record[field]).read_bytes()).hexdigest()!=record[sha]:raise ValueError('Input hash mismatch')
    rate,x=wavfile.read(record['audio_file'])
    if x.ndim!=1 or rate!=44100:raise ValueError('Expected mono 44.1kHz')
    x=x.astype(float)/32768
    layers,notes=load_reference(record['annotation_file']);branches={}
    for branch,pcm,kwargs in [('uncut',x,{}),('cut',band_cut(x,rate),dict(min_frequency=LOW_HZ,max_frequency=HIGH_HZ))]:
        evidence,_=features(pcm,rate,**kwargs)
        indices=np.arange(0,len(evidence['pitch_class_salience']),10)
        time_s=np.array([evidence['pitch_class_salience'][i]['time_s'] for i in indices])
        sal=np.array([evidence['pitch_class_salience'][i]['salience'] for i in indices])
        scores,rank,usable=rank_saliences(sal)
        peak_groups={}
        for p in evidence['pitch_candidates']:
            index=int(round(p['start_s']*rate/441))
            if index%10==0:peak_groups.setdefault(index,[]).append(p['midi'])
        predictions=[peak_groups.get(int(index),[]) for index in indices]
        branches[branch]=dict(nominal=evaluate_layer(time_s,rank,scores,usable,layers['nominal']),
                              performed=evaluate_layer(time_s,rank,scores,usable,layers['performed']),
                              pitch=evaluate_pitches(time_s,predictions,notes))
    return dict(recording_id=record['recording_id'],performer_id=record['performer_id'],style=record['style'],
                duration_s=record['duration_s'],audio_file=record['audio_file'],annotation_file=record['annotation_file'],
                audio_sha256=record['audio_sha256'],annotation_sha256=record['annotation_sha256'],
                known_timing_issue=record['recording_id'] in KNOWN_TIMING,
                known_duplicate_note=record['recording_id']==KNOWN_DUPLICATE,branches=branches,
                elapsed_s=time.perf_counter()-started)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--limit',type=int)
    parser.add_argument('--workers',type=int,default=2)
    args=parser.parse_args();out=args.output
    if (out/'summary.json').exists():raise FileExistsError(out)
    out.mkdir(parents=True,exist_ok=True);(out/'records').mkdir(exist_ok=True)
    manifest_path=ROOT/'dataset/integration_review/runs/guitarset_audio_ready_20261105_v1/manifest.json'
    manifest=read(manifest_path);records=[r for r in manifest['rows'] if r['performance']=='comp']
    if args.limit:records=records[:args.limit]
    config=dict(sampling='every10th STFT frame: 100ms, no temporal smoothing',window_samples=8192,hop_samples=441,
        stable_chord_margin_s=.05+4096/44100,pitch_reference='all active annotated notes at center; rounded MIDI sets, not note-event matching',
        methods=['uncut65to1600','D2toE6signal_and_candidates'],training=False,tuning_performed=False,
        primary_excluded_known_timing_files=KNOWN_TIMING,duplicate_note_handling='set-valued pitch metrics avoid duplicate counting; source not edited',
        chord_metric='root+pitch-class set exact, bass merged into set, inversion not separately scored; extensions reduced modulo12',
        parser='local explicit Harte adapter; unsupported labels counted',manifest_sha256=hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),workers=args.workers)
    config_path=out/'config.json'
    if config_path.exists() and read(config_path)!=config:raise ValueError('Cannot resume a changed benchmark')
    config_path.write_text(json.dumps(config,indent=2),encoding='utf-8')
    pending=[record for record in records if not (out/'records'/(record['recording_id']+'.json')).exists()]
    done=len(records)-len(pending)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(process_record,record):record for record in pending}
        for future in as_completed(futures):
            result=future.result();path=out/'records'/(result['recording_id']+'.json')
            temporary=path.with_suffix('.tmp');temporary.write_text(json.dumps(result,indent=2),encoding='utf-8');temporary.replace(path)
            done+=1;print(done,'/',len(records),result['recording_id'],flush=True)
    summary=aggregate([read(out/'records'/(r['recording_id']+'.json')) for r in records])
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print('Complete:',len(records),'files. See',out/'summary.json',flush=True)


def aggregate(records):
    result=dict(processed_files=len(records),known_timing_issue_files=[r['recording_id'] for r in records if r['known_timing_issue']],
                processed_duration_s=sum(r['duration_s'] for r in records),total_compute_s=sum(r['elapsed_s'] for r in records),scopes={})
    for scope,subset in [('primary_without_known_timing',[r for r in records if not r['known_timing_issue']]),('all_files',records)]:
        group=dict(files=len(subset),branches={})
        for branch in ['uncut','cut']:
            output={}
            for layer in ['nominal','performed']:
                counts=Counter();unparsed=Counter();confusion=Counter();macro=[]
                for r in subset:
                    data=r['branches'][branch][layer];counts.update(data['counts']);unparsed.update(data['unparsed']);confusion.update(data['confusions'])
                    if data['counts'].get('evaluated'):macro.append(data['counts'].get('top1',0)/data['counts']['evaluated'])
                denominator=counts.get('evaluated',0);covered=counts.get('representable',0)
                output[layer]=dict(counts=dict(counts),top1=counts.get('top1',0)/max(1,denominator),top3=counts.get('top3',0)/max(1,denominator),
                    root_top1=counts.get('root_top1',0)/max(1,denominator),dictionary_coverage=covered/max(1,denominator),
                    representable_top1=counts.get('representable_top1',0)/max(1,covered),representable_top3=counts.get('representable_top3',0)/max(1,covered),
                    file_macro_top1=float(np.mean(macro)) if macro else None,unparsed=dict(unparsed),top_confusions=confusion.most_common(20))
            counts=Counter()
            for r in subset:counts.update(r['branches'][branch]['pitch']['counts'])
            def metrics(prefix=''):
                tp,fp,fn=[counts.get(prefix+k,0) for k in ['tp','fp','fn']]
                return dict(precision=tp/max(1,tp+fp),recall=tp/max(1,tp+fn),f1=2*tp/max(1,2*tp+fp+fn))
            output['pitch']=dict(counts=dict(counts),midi=metrics(),pitch_class=metrics('pc_'),
                false_pitch_possible_harmonic_fraction=counts.get('false_pitches_near_reference_harmonics',0)/max(1,counts.get('fp',0)))
            group['branches'][branch]=output
        result['scopes'][scope]=group
    return result


if __name__=='__main__':main()
