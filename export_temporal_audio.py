"""Export short pooled model evidence to the current provisional chord pipeline."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
from basic_pitch_adapter import build_evidence
from temporal_audio_pool import pooled_chroma
from harmony_engine import provisional_audio_harmony

def main():
    p=argparse.ArgumentParser();p.add_argument('--prediction',type=Path,required=True);p.add_argument('--source-id',required=True)
    p.add_argument('--offset',type=float,required=True);p.add_argument('--width',type=float,required=True);p.add_argument('--method',choices=['max','mean'],default='max');p.add_argument('--clip-at-changes',action='store_true');p.add_argument('--change-detector-config',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.output.exists():raise FileExistsError(a.output)
    if (a.prediction.parent.parent/'superseded.json').exists():raise ValueError('Superseded clock')
    if not 0<a.width<=.8:raise ValueError('Supported width0..0.8s')
    meta=json.loads(a.prediction.with_suffix('.json').read_text())
    if hashlib.sha256(Path(meta['audio']).read_bytes()).hexdigest()!=meta['source_sha256']:raise ValueError('Source changed')
    with np.load(a.prediction) as data:
        grid=data['times'];frames=data['note'];e=build_evidence(grid,frames,meta['note_events'],source_id=a.source_id,start_s=a.offset,duration_s=meta['duration_s'])
        query=grid[(grid-a.width/2>=grid[0])&(grid+a.width/2<=grid[-1])][::10]
        if a.clip_at_changes:
            if a.method!='max':raise ValueError('Change clipping uses max pooling')
            from audio_change_pool import detect_changes,clipped_pool
            if a.change_detector_config:
                from calibrated_audio_changes import detect_changes as gated
                detector=json.loads(a.change_detector_config.read_text());boundaries,_,_=gated(grid,frames,detector['selected_height'])
            else:boundaries,_,_=detect_changes(grid,frames)
            sal,supports=clipped_pool(grid,frames,query,a.width,boundaries)
        else:sal=pooled_chroma(grid,frames,query,a.width,a.method)
    e['run_id']='basic_pitch_temporal_pool';e['pitch_class_salience']=[dict(event_id=f'pooled_{i}',time_s=float(t+a.offset),
        start_s=float(t+a.offset-a.width/2),end_s=float(t+a.offset+a.width/2),salience=s.tolist(),
        score_type='normalized_temporally_pooled_model_activation') for i,(t,s) in enumerate(zip(query,sal))]
    e['provenance']=dict(prediction=str(a.prediction.resolve()),prediction_sha256=hashlib.sha256(a.prediction.read_bytes()).hexdigest(),
        pooling_width_s=a.width,pooling_method=a.method,frame_threshold=.3,source_audio_sha256=meta['source_sha256'])
    if a.clip_at_changes:
        e['provenance']['audio_change_candidates_source_s']=(boundaries+a.offset).tolist()
        if a.change_detector_config:e['provenance']['change_detector_config_sha256']=hashlib.sha256(a.change_detector_config.read_bytes()).hexdigest()
        for row,support in zip(e['pitch_class_salience'],supports):
            row.update(start_s=support['start_s']+a.offset,end_s=support['end_s']+a.offset,near_audio_change=support['near_change'],window_clipped=support['clipped'])
    e['limitations']+=['Centered pooling uses future audio. Underlying model context is still about2s.',
                       'Decoded individual note durations are unchanged; pooled chord evidence spans a short interval.']
    a.output.mkdir(parents=True);(a.output/'evidence.json').write_text(json.dumps(e,indent=2),encoding='utf-8');(a.output/'harmony.json').write_text(json.dumps(provisional_audio_harmony(e),indent=2),encoding='utf-8')
    print('Exported',len(query),'pooled chord frames',flush=True)

if __name__=='__main__':main()
