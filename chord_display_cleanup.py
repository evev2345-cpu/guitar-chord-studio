"""Conservative offline cleanup of isolated display spikes, not general delay.

Only replace bracketed A-B-A glitches when A is also a close current candidate.
Never use visual references. Original predictions are retained alongside display.
"""
import copy
from chord_display_stabilizer import identity

CONFIG=dict(spike_max_frames=2,extension_spike_max_frames=3,dropout_max_frames=2,alternative_score_gap=.08,tie_tolerance=1e-10,mode='offline_bracketed_cleanup')

def stabilize(times,rows,config=None):
    cfg=dict(CONFIG,**(config or {}))
    if len(times)!=len(rows) or any(b<=a for a,b in zip(times,times[1:])):raise ValueError('Invalid display timeline')
    values=[];status=[];state=None
    for row in rows:
        top=row['top3'];raw=top[0] if top else None
        tied=next((c for c in top if identity(c)==identity(state) and abs(c['score']-raw['score'])<=cfg['tie_tolerance']),None) if state and top else None
        if tied is not None and identity(tied)!=identity(raw):state=copy.deepcopy(tied);status.append('retained_top_score_tie')
        else:state=copy.deepcopy(raw);status.append('provisional' if raw else row.get('status','insufficient_note_evidence'))
        values.append(copy.deepcopy(state))
    # One pass over original runs: avoid repeatedly eroding actual short changes.
    runs=[];start=0
    for i in range(1,len(values)+1):
        if i==len(values) or identity(values[i])!=identity(values[start]):runs.append((start,i));start=i
    output=copy.deepcopy(values)
    for a,b in runs:
        if a==0 or b==len(values):continue
        left,right=values[a-1],values[b]
        if left is None or identity(left)!=identity(right):continue
        if values[a] is None:
            if b-a<=cfg['dropout_max_frames'] and all(rows[j].get('status')!='audio_edge_no_full_window' for j in range(a,b)):
                for j in range(a,b):output[j]=copy.deepcopy(left);status[j]='bridged_short_dropout'
            continue
        extension=values[a]['root_pc']==left['root_pc'] and set(values[a]['pcs'])>set(left['pcs'])
        limit=cfg['extension_spike_max_frames'] if extension else cfg['spike_max_frames']
        alternatives=[next((c for c in rows[j]['top3'] if identity(c)==identity(left) and rows[j]['top3'][0]['score']-c['score']<=cfg['alternative_score_gap']),None) for j in range(a,b)]
        if b-a<=limit and all(c is not None for c in alternatives):
            for j,c in zip(range(a,b),alternatives):output[j]=copy.deepcopy(c);status[j]='removed_isolated_extension' if extension else 'removed_isolated_spike'
    return [dict(display_candidate=c,raw_top1=copy.deepcopy(r['top3'][0]) if r['top3'] else None,status=s,
        pending_candidate=None,switched=bool(i and identity(c)!=identity(output[i-1])),confirmation_delay_s=None,
        direct_current_support=bool(c and any(identity(v)==identity(c) for v in r['top3']))) for i,(c,r,s) in enumerate(zip(output,rows,status))]
