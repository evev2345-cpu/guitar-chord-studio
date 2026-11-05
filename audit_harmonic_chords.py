"""Independent input replay, note-PC evaluation, and small tutorial check."""
import json
import hashlib
from collections import Counter
import numpy as np
from scipy.io import wavfile
from benchmark_harmonic_chords import ROOT,BRANCHES
from guitarset_benchmark import KNOWN_TIMING,load_reference,TEMPLATES
from harmonic_chord_features import harmonic_salience,WINDOW
from audio_analysis import features
from idmt_chords_benchmark import pcm_float
from chord_score_variants import score_variants
from compare_guitar_stem_accuracy import safe_evaluate

OUT=ROOT/'dataset/integration_review/runs/harmonic_ablation_20261105_v1'

def main():
    target=OUT/'audit.json'
    if target.exists():raise FileExistsError(target)
    read=lambda p:json.loads(p.read_text(encoding='utf-8'))
    manifest=read(ROOT/'dataset/integration_review/runs/guitarset_audio_ready_20261105_v1/manifest.json')
    sha={r['recording_id']:r['audio_sha256'] for r in manifest['rows']}
    counts={k:Counter() for k in ['peak','harmonic']};verified=0;annotation_hashes={}
    for p in sorted((OUT/'records').glob('*.json')):
        rec=read(p);annotation_hashes[rec['annotation']]=hashlib.sha256(__import__('pathlib').Path(rec['annotation']).read_bytes()).hexdigest()
        if rec['domain']=='idmt':
            old=read(ROOT/'dataset/integration_review/runs/idmt_chords_scores_20261105_v2'/(rec['id']+'.json'))
            for new_branch,old_branch in [('peak_legacy','legacy'),('peak_cosine','cosine')]:
                rows=rec['branches'][new_branch]['nominal']['frames']
                assert len(rows)==len(old['rows'])
                assert all(a['correct_top1']==b['variants'][old_branch]['top1'] and a['correct_top3']==b['variants'][old_branch]['top3'] for a,b in zip(rows,old['rows']))
            assert rec['sha256']==old['sha256'];verified+=1;continue
        assert rec['sha256']==sha[rec['id']];verified+=1
        if rec['id'] in KNOWN_TIMING:continue
        _,notes=load_reference(rec['annotation'])
        for i,t in enumerate(rec['times']):
            truth={round(n['midi'])%12 for n in notes if n['start']<=t<n['end']}
            for key in counts:
                sal=np.array(rec[key+'_salience'][i]);pred=set(np.where((sal>0)&(sal>=.1*sal.max()))[0])
                counts[key].update(tp=len(truth&pred),fp=len(pred-truth),fn=len(truth-pred),windows=1)
    note_metrics={}
    for key,c in counts.items():
        precision=c['tp']/max(1,c['tp']+c['fp']);recall=c['tp']/max(1,c['tp']+c['fn'])
        note_metrics[key]=dict(counts=dict(c),precision=precision,recall=recall,f1=2*precision*recall/max(precision+recall,1e-12))
    audio=ROOT/'dataset/audio_analysis/runs/barre_194_226_guitar_6s_20261105_v1/htdemucs_6s/original/guitar.wav'
    rate,x=wavfile.read(audio);x=pcm_float(x)
    if x.ndim==2:x=x.mean(axis=1)
    references=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/references.json')['references'];rows=[]
    for ref in references:
        start=round((ref['pts']-194)*rate)-WINDOW//2;win=x[start:start+WINDOW]
        evidence,_=features(win,rate);h,_,residual=harmonic_salience(win,rate);branches={}
        for feature,sal in [('peak',evidence['pitch_class_salience'][0]['salience']),('harmonic',h)]:
            for scorer,(scores,rank,usable) in score_variants(np.array([sal])).items():
                if scorer not in ('legacy','cosine'):continue
                ranked=[dict(root_pc=TEMPLATES[j]['root_pc'],quality=TEMPLATES[j]['quality'],concert_symbol=TEMPLATES[j]['symbol'],score=float(scores[0,j])) for j in rank[0]] if usable[0] else []
                branches[feature+'_'+scorer]=dict(top3=ranked[:3],evaluation=safe_evaluate(ranked,ref))
        rows.append(dict(reference=ref,branches=branches,residual=residual))
    tutorial=dict(rows=rows,summary={b:{k:sum(r['branches'][b]['evaluation'][k] for r in rows) for k in ['exact_top1','exact_top3','root_top1']} for b in BRANCHES},
                  source_sha256=hashlib.sha256(audio.read_bytes()).hexdigest(),protocol='single8192 window centered exact video PTS; raw mono guitar estimate; no temporal smoothing; source offset194s')
    result=dict(verified_audio_files=verified,idmt_baseline_replay_exact=True,annotation_sha256=annotation_hashes,note_pc_metrics=note_metrics,tutorial=tutorial)
    target.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(dict(verified=verified,note_metrics=note_metrics,tutorial=tutorial['summary']),indent=2))

if __name__=='__main__':main()
