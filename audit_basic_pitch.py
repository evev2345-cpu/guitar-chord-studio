"""Audit sample-clock coverage and generated onset probe without fitting offsets."""
import json
from pathlib import Path
import numpy as np
from evaluate_basic_pitch import OUT,ROOT,BASE

def main():
    read=lambda p:json.loads(p.read_text(encoding='utf-8'));verified=0;max_tail=0.;max_delta=0.
    for p in sorted((OUT/'predictions').glob('*.npz')):
        meta=read(p.with_suffix('.json'))
        with np.load(p) as d:
            times=d['times'];note=d['note']
        if not np.all(np.diff(times)>0) or len(times)!=len(note):raise ValueError('Nonmonotonic or mismatched output')
        tail=meta['duration_s']-times[-1]
        if not 0<tail<=256/22050+.0001:raise ValueError('Model lost audio tail')
        max_tail=max(max_tail,float(tail));verified+=1
        if meta['id']!='tutorial':
            baseline=read(BASE/'records'/(meta['id']+'.json'))
            if meta['source_sha256']!=baseline['audio_sha256']:raise ValueError('Wrong source')
            for t in baseline['times']:
                delta=float(np.min(abs(times-t)));max_delta=max(max_delta,delta)
                if delta>.03:raise ValueError('Evaluation outside model support')
    assert verified==374
    probe=ROOT/'dataset/integration_review/runs/basic_pitch_clock_probe_20261105_v1';reference=read(probe/'reference.json');checks={}
    for mode in ['raw','cut']:
        notes=read(probe/f'predictions/probe_{mode}.json')['note_events'];notes=[e for e in notes if e['midi']==reference['midi']]
        if not notes:raise ValueError('Probe note not found')
        errors=[min(abs(e['start_s']-t) for e in notes) for t in reference['onsets_s']]
        if max(errors)>.1:raise ValueError('Probe onset timing drift')
        checks[mode]=dict(onset_abs_error_s=errors,max_onset_abs_error_s=max(errors))
    result=dict(verified_outputs=verified,max_tail_gap_s=max_tail,max_evaluation_frame_delta_s=max_delta,
                clock_probe=checks,reference_offset_fitting=False,training=False)
    (OUT/'audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
