"""Bounded, chronological display hysteresis. Never consults reference labels.

This stabilizes a provisional display, not acoustic notes or confidence scores.
Underlying centered audio evidence is still offline/noncausal.
"""
import copy

CONFIG=dict(confirm_s=.1,extension_confirm_s=.2,dropout_hold_s=.15,max_pending_hold_s=.25,tie_tolerance=1e-10)

def identity(c):return (c['root_pc'],c['quality']) if c else None

def stabilize(times,rows,config=None):
    cfg=dict(CONFIG,**(config or {}));state=None;pending=None;since=0.;last_seen=-float('inf');previous=-float('inf');out=[]
    for t,row in zip(times,rows):
        if t<=previous:raise ValueError('Display times must strictly increase')
        previous=t;top=row['top3'];raw=top[0] if top else None;status='insufficient_note_evidence';switched=False;delay=None
        if row.get('status')=='audio_edge_no_full_window':state=None;pending=None;status='audio_edge_no_full_window'
        elif not top:
            pending=None
            if state and t-last_seen<=cfg['dropout_hold_s']+1e-9:status='held_during_short_dropout'
            else:state=None
        else:
            tied=next((c for c in top if identity(c)==identity(state) and abs(c['score']-raw['score'])<=cfg['tie_tolerance']),None) if state else None
            if identity(raw)==identity(state):state=copy.deepcopy(raw);last_seen=t;pending=None;status='provisional'
            elif tied is not None:state=copy.deepcopy(tied);last_seen=t;pending=None;status='retained_top_score_tie'
            else:
                if identity(raw)!=identity(pending):pending=copy.deepcopy(raw);since=t
                required=cfg['confirm_s']
                if state and raw['root_pc']==state['root_pc'] and set(raw['pcs'])>set(state['pcs']):required=cfg['extension_confirm_s']
                if t-since+1e-9>=required:
                    state=copy.deepcopy(raw);last_seen=t;switched=True;delay=float(t-since);pending=None;status='provisional'
                else:
                    status='awaiting_candidate_persistence'
                    if state and t-last_seen>cfg['max_pending_hold_s']:state=None
        out.append(dict(display_candidate=copy.deepcopy(state),raw_top1=copy.deepcopy(raw),status=status,
            pending_candidate=copy.deepcopy(pending),switched=switched,confirmation_delay_s=delay,
            direct_current_support=bool(state and any(identity(c)==identity(state) for c in top))))
    return out
