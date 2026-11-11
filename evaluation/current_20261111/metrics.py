"""Evaluation-only metrics. No inference or prediction modification."""
import bisect
from collections import Counter,defaultdict
from labels import parse_chord,degree
from harmony_engine import TEMPLATES

MARGIN=.05+4096/44100
QUALITY={tuple(sorted((pc-t['root_pc'])%12 for pc in t['pcs'])):t['quality'] for t in TEMPLATES}


def reference(label):
    parsed=parse_chord(label.replace(':5',':(1,5)'))
    if parsed is None:return None
    intervals=tuple(sorted((pc-parsed['root_pc'])%12 for pc in parsed['pcs']))
    return dict(parsed,intervals=intervals,quality=QUALITY.get(intervals,'OOV'))


def identity(c):
    if not c:return None
    return c['root_pc'],tuple(sorted(c['pcs']))


def choices(row,view):
    if view=='A':return row.get('top3',[])[:1]
    if view=='U_context':return row.get('onset_context',{}).get('display_candidates',[])
    p=row.get('onset_presentation',{})
    if view=='B_frame':return p.get('frame_display_candidates',p.get('display_candidates',[]))
    return p.get('display_candidates',[])


def score(ref,candidates):
    pred=candidates[0] if len(candidates)==1 else None
    exact=bool(pred and pred['root_pc']==ref['root_pc'] and tuple(sorted(pred['pcs']))==tuple(ref['pcs']))
    root=bool(pred and pred['root_pc']==ref['root_pc'])
    quality=bool(pred and tuple(sorted((pc-pred['root_pc'])%12 for pc in pred['pcs']))==ref['intervals'])
    return dict(n=1,exact=int(exact),root=int(root),quality=int(quality),abstain=int(not candidates),
                ambiguous=int(len(candidates)>1),oov=int(not ref['representable']))


def collect(rows,times,events,dataset):
    views=['A','B','U_context','B_frame'];counts={v:Counter() for v in views}
    perq={v:defaultdict(Counter) for v in views};conf={v:Counter() for v in views};detail=[];excluded=Counter()
    clock=[r['time_s'] for r in rows]
    for t in times:
        event=next((e for e in events if e['time']+MARGIN<=t<e['time']+e['duration']-MARGIN),None)
        if event is None:excluded['boundary_or_unlabelled']+=1;continue
        try:ref=reference(event['value'])
        except ValueError:excluded['unsupported_label']+=1;continue
        if ref is None:excluded['N_or_X']+=1;continue
        idx=bisect.bisect_right(clock,t+1e-8)-1
        row=rows[idx] if rows and idx>=0 and t<clock[-1]+1/24+1e-8 else {}
        for view in views:
            c=choices(row,view);s=score(ref,c);counts[view].update(s);perq[view][ref['quality']].update(s)
            symbol=c[0]['symbol'] if len(c)==1 else '<ambiguous>' if c else '<abstain>'
            if not s['exact']:conf[view][event['value']+' -> '+symbol]+=1
            detail.append(dict(time_s=t,reference=event['value'],reference_root=ref['root_pc'],reference_quality=ref['quality'],
                reference_pcs=list(ref['pcs']),view=view,predictions=c,**s))
    return dict(counts={v:dict(c) for v,c in counts.items()},per_quality={v:{q:dict(c) for q,c in qs.items()} for v,qs in perq.items()},
        confusion={v:dict(c) for v,c in conf.items()},excluded=dict(excluded)),detail


def temporal(rows,events):
    times=[r['time_s'] for r in rows];sequences={}
    for view in ['A','B','U_context','B_frame']:
        sequences[view]=[identity(c[0]) if len(c:=choices(r,view))==1 else None for r in rows]
    runs={}
    for view,seq in sequences.items():
        groups=[];start=0
        for i in range(1,len(seq)+1):
            if i==len(seq) or seq[i]!=seq[start]:groups.append((start,i,seq[start]));start=i
        runs[view]=dict(state_transitions=max(0,len(groups)-1),nonempty_runs=sum(k is not None for _,_,k in groups),
            short_chord_runs_lt_02=sum(k is not None and (b-a)/24<.2-1e-9 for a,b,k in groups),
            chord_to_chord_transitions=sum(a[2] is not None and b[2] is not None for a,b in zip(groups,groups[1:])))
    transitions=[]
    for left,right in zip(events,events[1:]):
        if abs(left['time']+left['duration']-right['time'])>1/24:continue
        try:a=reference(left['value']);b=reference(right['value'])
        except ValueError:continue
        if a is None or b is None or (a['root_pc'],tuple(a['pcs']))==(b['root_pc'],tuple(b['pcs'])):continue
        t=right['time'];old=(a['root_pc'],tuple(a['pcs']));new=(b['root_pc'],tuple(b['pcs']))
        lo=bisect.bisect_left(times,max(left['time'],t-.5));mid=bisect.bisect_left(times,t);hi=bisect.bisect_left(times,min(t+.5,right['time']+right['duration']))
        hit={v:(old in seq[lo:mid] and new in seq[mid:hi]) for v,seq in sequences.items()}
        transitions.append(dict(time_s=t,before=left['value'],after=right['value'],stable_intervals=left['duration']>=.5 and right['duration']>=.5,
            representable=a['representable'] and b['representable'],detected=hit,
            B_lost_A=hit['A'] and not hit['B'],lookahead_loss=hit['U_context'] and not hit['B_frame'],grid_loss=hit['B_frame'] and not hit['B']))
    return dict(runs=runs,transitions=transitions)
