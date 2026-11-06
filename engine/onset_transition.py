"""Optional positive transition bonus from model onsets AND novel pitch classes.

No onset is not a veto. Repeated attacks on an unchanged PC set get no bonus.
Original raw/context/display records are retained for A/B review.
"""
import copy
import numpy as np
from chord_presentation import prepare

CONFIG=dict(onset_threshold=.5,activation_threshold=.3,min_novel_fraction=.15,
            bonus_max=.035,max_raw_gap=.06,decision_margin=.025,
            attack_window_s=[-.08,.08],before_window_s=[-.5,-.08],after_window_s=[.02,.20],
            mode='offline_onset_and_novel_pcs_positive_bonus_v1')


def evidence(grid,notes,onsets,times):
    grid=np.asarray(grid,float);notes=np.asarray(notes,float);times=np.asarray(times,float)
    if notes.shape!=(len(grid),88) or not len(grid) or np.any(np.diff(grid)<=0) or not np.isfinite(grid).all() or not np.isfinite(notes).all() or not np.isfinite(times).all():
        raise ValueError('Invalid onset evidence clock')
    if onsets is None:return [dict(active=False,status='onset_unavailable',novel_pc_weights=[0.]*12,onset_peak=0.,novel_fraction=0.) for _ in times]
    onsets=np.asarray(onsets,float)
    if onsets.shape!=notes.shape or not np.isfinite(onsets).all():raise ValueError('Invalid onset grid')
    midi=np.arange(38,89);pcs=midi%12;result=[]
    for t in times:
        empty=dict(active=False,status='incomplete_context',novel_pc_weights=[0.]*12,onset_peak=0.,novel_fraction=0.)
        if t-.5<grid[0] or t+.2>grid[-1]:result.append(empty);continue
        a,b=np.searchsorted(grid,[t-.5,t-.08]);c,d=np.searchsorted(grid,[t+.02,t+.20]);e,f=np.searchsorted(grid,[t-.08,t+.08])
        if min(b-a,d-c,f-e)<2:result.append(empty);continue
        before=np.max(notes[a:b,17:68],axis=0);after=np.mean(notes[c:d,17:68],axis=0)
        before_pc=np.zeros(12);after_pc=np.zeros(12)
        np.maximum.at(before_pc,pcs,before);np.maximum.at(after_pc,pcs,after)
        new=np.where((before_pc<.3)&(after_pc>=.3),after_pc,0.)
        total=float(np.where(after_pc>=.3,after_pc,0.).sum());fraction=float(new.sum()/max(total,1e-12))
        novel_bins=new[pcs]>0
        peak=float(onsets[e:f,17:68][:,novel_bins].max()) if novel_bins.any() else 0.
        active=bool(peak>=CONFIG['onset_threshold'] and fraction>=CONFIG['min_novel_fraction'])
        result.append(dict(active=active,status='attack_and_new_pcs' if active else 'no_joint_change',
                           novel_pc_weights=new.tolist(),onset_peak=peak,novel_fraction=fraction,
                           new_pcs=np.flatnonzero(new).tolist(),score_type='model_evidence_not_probability'))
    return result


def context_with_bonus(context,raw,e):
    result=copy.deepcopy(context);result['onset_evidence']=copy.deepcopy(e)
    if not e['active'] or not raw['top3']:return result
    # Keep each existing candidate's strongest pre-onset score; never invent a
    # chord or note. Include the existing shown alternatives as well as top3.
    pool={}
    for c in context['top3']+context['display_candidates']:
        key=(c['root_pc'],c['quality']);value=c.get('adjusted_score',c['score'])
        if key not in pool or value>pool[key].get('adjusted_score',pool[key]['score']):pool[key]=copy.deepcopy(c)
    if not pool:return result
    best_audio=max(c['score'] for c in raw['top3']);weights=np.asarray(e['novel_pc_weights']);total=weights.sum()
    for c in pool.values():
        fit=float(weights[c['pcs']].sum()/max(total,1e-12))
        bonus=CONFIG['bonus_max']*min(1.,e['onset_peak'])*fit if best_audio-c['score']<=CONFIG['max_raw_gap']+1e-10 else 0.
        c['onset_bonus']=bonus;c['onset_adjusted_score']=c.get('adjusted_score',c['score'])+bonus
    ranked=sorted(pool.values(),key=lambda c:-c['onset_adjusted_score']);result['top3']=ranked[:3]
    gap=ranked[0]['onset_adjusted_score']-ranked[1]['onset_adjusted_score'] if len(ranked)>1 else 0.
    current=context['display_candidates'];new_id=(ranked[0]['root_pc'],ranked[0]['quality'])
    current_ids=[(c['root_pc'],c['quality']) for c in current]
    if gap>=CONFIG['decision_margin'] and current_ids!=[new_id] and ranked[0]['onset_bonus']>0:
        result['display_candidates']=[ranked[0]];result['status']='onset_and_pitch_change_preference'
    result['onset_adjusted_margin']=float(gap)
    return result


def add_layer(result,grid,notes,onsets):
    first=next(iter(result['branches'].values()),[]);times=[r['time_s'] for r in first]
    observations=evidence(grid,notes,onsets,times)
    for rows in result['branches'].values():
        if [r['time_s'] for r in rows]!=times:raise ValueError('Branch clock mismatch')
        working=[]
        for row,e in zip(rows,observations):
            row['onset_context']=context_with_bonus(row['context'],row,e)
            # Presentation receives a separate view; original context is untouched.
            working.append(dict(row,context=row['onset_context']))
        shown=prepare(times,working,tempo=result.get('tempo'))
        for row,p in zip(rows,shown):row['onset_presentation']=p
    result['schema_version']='chord_web.v4';result['onset_transition_config']=copy.deepcopy(CONFIG)
    return result
