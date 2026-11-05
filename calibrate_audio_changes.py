"""Choose only a change-candidate threshold on pre-existing validation split."""
import json
import hashlib
from pathlib import Path
import numpy as np
from calibrated_audio_changes import detect_changes
from evaluate_change_aware_audio import match_changes,ROOT,PRED
from guitarset_benchmark import load_reference

OUT=ROOT/'dataset/integration_review/runs/change_aware_audio_20261105_v2'

def main():
    if (OUT/'detector_calibration.json').exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True,exist_ok=True)
    split=json.loads((ROOT/'dataset/audio_analysis/runs/note_calibrator_20261105_v1/split_manifest.json').read_text());ids=[r['id'] for r in split if r['split']=='validation']
    thresholds=[.05,.1,.15,.2,.25,.3,.4];counts={str(t):dict(tp=0,fp=0,fn=0) for t in thresholds}
    from scipy.signal import find_peaks
    for rid in ids:
        with np.load(PRED/(rid+'_raw.npz')) as d:grid=d['times'];frames=d['note']
        layers,_=load_reference(ROOT/'GuitarSet/annotation'/(rid+'.jams'));_,scores,_=detect_changes(grid,frames,.05)
        for t in thresholds:
            ix,_=find_peaks(scores,height=t,prominence=.08,distance=max(1,round(.2/np.median(np.diff(grid)))))
            result=match_changes(grid[ix],layers['performed'],grid[0]+.2,grid[-1]-.2)
            for key in ['tp','fp','fn']:counts[str(t)][key]+=result[key]
    for t,c in counts.items():
        p=c['tp']/max(1,c['tp']+c['fp']);r=c['tp']/max(1,c['tp']+c['fn']);c.update(precision=p,recall=r,f1=2*p*r/max(p+r,1e-12))
    best=max(thresholds,key=lambda t:(counts[str(t)]['f1'],counts[str(t)]['precision'],t))
    result=dict(selected_height=best,activation_floor=.3,context_each_side_s=.2,prominence=.08,min_distance_s=.2,
        validation_recording_ids=ids,threshold_grid=counts,selection='Validation transition F1 only; no new tutorial or IDMT selection',
        limitations='All corpora have prior development exposure; new4references were seen after v1 and are not a fresh blind test for this iteration',
        source_sha256=hashlib.sha256((ROOT/'calibrated_audio_changes.py').read_bytes()).hexdigest())
    (OUT/'detector_calibration.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
