"""Experimental location-only audio candidate bonus, with strict source/time gates.

Unknown geometry/anatomy/contact stays unknown. Equal-PC root ties are not
resolved by generic location compatibility; existing validated-root gate remains.
"""
import copy
import numpy as np
from chord_presentation import prepare

CONFIG=dict(bonus_max=.06,max_raw_gap=.06,decision_margin=.025,
            minimum_compatibility_spread=.02,mode='provisional_location_only_positive_bonus_v1')


def with_vision(context,raw,observation,*,source_id,time_s,max_delta):
    result=copy.deepcopy(context)
    evidence=dict(status='unavailable',applied=False,geometry_verified=False,anatomy_verified=False,contact='unknown',root_voicing_validated=False)
    result['vision_evidence']=evidence
    if observation is None or observation.get('source_id')!=source_id:return result
    delta=float(observation['time_s']-time_s)
    evidence.update(observation_frame=observation['frame_index'],observation_time_s=observation['time_s'],time_delta_s=delta,
                    frame_pixel_sha256=observation.get('frame_pixel_sha256'),status=observation['status'])
    if abs(delta)>max_delta+1e-6:
        evidence['status']='time_mismatch';return result
    if observation['status']!='provisional_location_only' or not raw['top3']:return result
    spatial=observation['spatial'];mass=np.asarray(spatial['pc_support'],float)
    if mass.shape!=(12,) or not np.isfinite(mass).all() or (mass<0).any():raise ValueError('Invalid visual location support')
    if mass.sum()<.5 or spatial['supported_fingers']<2:return result
    quality=min(1.,mass.sum()/1.5)*observation['alignment']['inlier_fraction']
    pool={}
    for c in context['top3']+context['display_candidates']:
        key=(c['root_pc'],c['quality']);value=c.get('onset_adjusted_score',c.get('adjusted_score',c['score']))
        if key not in pool or value>pool[key].get('onset_adjusted_score',pool[key].get('adjusted_score',pool[key]['score'])):pool[key]=copy.deepcopy(c)
    best_audio=max(c['score'] for c in raw['top3'])
    for c in pool.values():
        fit=float(mass[c['pcs']].sum()/mass.sum());eligible=best_audio-c['score']<=CONFIG['max_raw_gap']+1e-10
        bonus=CONFIG['bonus_max']*quality*fit if eligible else 0.
        c.update(visual_compatibility=fit,visual_bonus=bonus,
                 vision_adjusted_score=c.get('onset_adjusted_score',c.get('adjusted_score',c['score']))+bonus)
    ranked=sorted(pool.values(),key=lambda c:-c['vision_adjusted_score'])
    if not ranked:return result
    result['top3']=ranked[:3];spread=max(c['visual_compatibility'] for c in ranked)-min(c['visual_compatibility'] for c in ranked)
    evidence.update(applied=True,compatibility_spread=float(spread),location_quality_factor=float(quality),score_type='uncalibrated_location_compatibility')
    gap=ranked[0]['vision_adjusted_score']-ranked[1]['vision_adjusted_score'] if len(ranked)>1 else 0.
    current=[(c['root_pc'],c['quality']) for c in context['display_candidates']];winner=(ranked[0]['root_pc'],ranked[0]['quality'])
    if gap>=CONFIG['decision_margin'] and spread>=CONFIG['minimum_compatibility_spread'] and current!=[winner] and ranked[0]['visual_bonus']>0:
        result['display_candidates']=[ranked[0]];result['status']='vision_position_preference'
    result['vision_adjusted_margin']=float(gap)
    return result


def add_layer(result,observations,*,source_id,fps):
    clock=np.asarray([o['time_s'] for o in observations],float)
    if not len(clock) or not np.isfinite(clock).all() or np.any(np.diff(clock)<=0):raise ValueError('Invalid visual clock')
    if any(o['source_id']!=source_id for o in observations):raise ValueError('Visual source mismatch')
    for rows in result['branches'].values():
        times=[r['time_s'] for r in rows];indices=np.searchsorted(clock,times)
        for onset in [False,True]:
            source='onset_context' if onset else 'context';dest='vision_onset_context' if onset else 'vision_context';pres='vision_onset_presentation' if onset else 'vision_presentation';working=[]
            for i,row in enumerate(rows):
                options=[j for j in [indices[i]-1,indices[i]] if 0<=j<len(clock)];j=min(options,key=lambda j:abs(clock[j]-row['time_s'])) if options else None
                row[dest]=with_vision(row.get(source,row['context']),row,observations[j] if j is not None else None,
                    source_id=source_id,time_s=row['time_s'],max_delta=.5/fps)
                working.append(dict(row,context=row[dest]))
            for row,p in zip(rows,prepare(times,working,tempo=result.get('tempo'))):row[pres]=p
    usable=sum(o['status']=='provisional_location_only' for o in observations)
    result['schema_version']='chord_web.v5';result['vision_connected']=bool(usable)
    result['analysis_mode']='audio_plus_provisional_vision' if usable else 'offline_audio_only'
    result['vision_config']=dict(CONFIG,source_id=source_id,fps=fps,usable_frames=usable,total_frames=len(observations),
                                 geometry_status='source_specific_manual_provisional',contact='unknown',root_voicing_validated=False)
    if usable:
        limitations=[s for s in result.get('limitations',[]) if s!='손·지판 비전은 아직 웹 분석에 연결하지 않았습니다.']
        limitations.append('비전은 영상별 수동 근사 지판·가상 현의 잠정 위치 가점입니다. 누름·뮤트·손가락 의미는 미확정입니다.')
        result['limitations']=list(dict.fromkeys(limitations))
    return result
