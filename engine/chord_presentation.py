"""Conservative offline display policy; preserve all underlying observations."""
import copy
import numpy as np
from harmony_engine import NAMES
from beat_grid import align_tempo_to_chords, quantize_to_16beat_grid

CONFIG=dict(short_return_s=.25,same_root_return_s=.50,weak_change_s=.22,
            confirm_s=.25,retained_audio_gap=.10,bridge_audio_gap=.18,
            immediate_audio_margin=.12,slash_window_s=.5,slash_presence=.9,
            slash_activation=.65,low_inversion_activation=.55,
            slash_min_run_s=.35,low_inversion_min_run_s=.20,
            mode='offline_lookahead_confirmed_display_v2')

EXT_QUALITIES={'6','add9','sus2','sus4','maj7'}
BASE_QUALITIES={'major','minor','7','m7'}


def identity(candidate):
    return candidate['root_pc'],candidate['quality']


def group_key(candidates):
    return tuple(sorted(identity(c) for c in candidates))


def runs(values):
    output=[];start=0
    for i in range(1,len(values)+1):
        if i==len(values) or group_key(values[i])!=group_key(values[start]):
            output.append((start,i));start=i
    return output


def supported(candidates,row,gap=None):
    """Each retained interpretation needs close CURRENT audio support."""
    available=row['top3']+row['context']['top3']
    if not candidates or not available:return None
    limit=CONFIG['retained_audio_gap'] if gap is None else gap
    best=max(c['score'] for c in available)
    chosen=[]
    for previous in candidates:
        matches=[c for c in available if identity(c)==identity(previous) and best-c['score']<=limit+1e-10]
        if not matches:return None
        # Reuse a complete current-frame candidate, with this frame's bass metadata.
        chosen.append(copy.deepcopy(max(matches,key=lambda c:c['score'])))
    return chosen


def same_root_base_supported(candidates,row):
    """Consolidate transient same-root extensions (6/add9/sus/maj7) into a confirmed base chord."""
    available=row['top3']+row['context']['top3']
    if len(candidates)!=1 or not available:return None
    target=candidates[0]
    if target['quality'] not in BASE_QUALITIES:return None
    if not any(c['root_pc']==target['root_pc'] and (c['quality']==target['quality'] or c['quality'] in EXT_QUALITIES) for c in row['context']['display_candidates']+available[:1]):
        return None
    direct=[c for c in available if identity(c)==identity(target)]
    if direct:return [copy.deepcopy(max(direct,key=lambda c:c['score']))]
    if any(c['root_pc']==target['root_pc'] and c['quality'] in EXT_QUALITIES for c in available):
        return [copy.deepcopy(target)]
    return None


def strong_change(row):
    top=row['top3'] or row['context']['top3']
    return bool(top and (len(top)==1 or top[0]['score']-top[1]['score']>=CONFIG['immediate_audio_margin']))


def is_low_below_root_inversion(candidate,bass_pc,bass_midi):
    """True when bass_midi is on the 6th/low-5th string physically below the chord's lowest guitar root."""
    if bass_pc is None or bass_midi is None or bass_pc==candidate['root_pc'] or bass_pc not in candidate['pcs']:
        return False
    lowest_root_midi=40+((candidate['root_pc']-40)%12)
    return bool(40<=bass_midi<lowest_root_midi)


def plain(candidate,reason):
    c=copy.deepcopy(candidate);c['observed_bass_pc']=c.get('bass_pc');c['bass_pc']=None
    c['symbol']=c.get('base_symbol',c['symbol'].split('/')[0]);c['bass_display_status']=reason
    return c


def prepare(times,rows,tempo=None):
    times=np.asarray(times,float)
    if len(times)!=len(rows) or np.any(~np.isfinite(times)) or np.any(np.diff(times)<=0):raise ValueError('Invalid presentation clock')
    if not len(rows):return []
    step=float(np.median(np.diff(times))) if len(times)>1 else 1/24
    original=[copy.deepcopy(row['context']['display_candidates']) for row in rows]
    values=copy.deepcopy(original);status=['unchanged']*len(rows)
    # 1. Ambiguous tie retention (forward and look-ahead backward when adjacent to single interpretation)
    for i in range(1,len(rows)):
        if len(original[i])>1 and len(values[i-1])==1:
            match=next((c for c in original[i] if identity(c)==identity(values[i-1][0])),None)
            if match is not None:
                values[i]=[copy.deepcopy(match)];status[i]='retained_previous_among_ambiguous'
    for i in range(len(rows)-2,-1,-1):
        if len(values[i])>1 and len(values[i+1])==1:
            match=next((c for c in values[i] if identity(c)==identity(values[i+1][0])),None)
            if match is not None:
                values[i]=[copy.deepcopy(match)];status[i]='retained_previous_among_ambiguous'
    # 2. Multi-step bracketed return A -> B1..Bk -> A (offline non-causal consolidation)
    rlist=runs(values)
    for idx_a in range(len(rlist)):
        for idx_b in range(idx_a+2,min(len(rlist),idx_a+6)):
            a_start,a_end=rlist[idx_a];b_start,_=rlist[idx_b]
            if not values[a_start] or group_key(values[a_start])!=group_key(values[b_start]):continue
            span=(b_start-a_end)*step;target=values[a_start]
            same_root_ext=(
                len(target)==1 and target[0]['quality'] in BASE_QUALITIES and
                span<=CONFIG['same_root_return_s']+1e-9 and
                all(rows[j]['top3'] and same_root_base_supported(target,rows[j]) is not None for j in range(a_end,b_start))
            )
            if same_root_ext:
                for j in range(a_end,b_start):
                    values[j]=same_root_base_supported(target,rows[j]);status[j]='consolidated_same_root_extension'
                break
            if span<=CONFIG['short_return_s']+1e-9:
                options=[supported(target,rows[j]) for j in range(a_end,b_start)]
                if all(c is not None for c in options) and not any(strong_change(rows[j]) for j in range(a_end,b_start)):
                    for j,candidates in zip(range(a_end,b_start),options):
                        values[j]=candidates;status[j]='removed_supported_short_return'
                    break
    # 3. Offline look-ahead confirmation: unconfirmed short runs absorb into confirmed neighbors
    for _ in range(2):
        snapshot=copy.deepcopy(values);rlist=runs(snapshot)
        for idx,(a,b) in enumerate(rlist):
            dur=(b-a)*step
            if dur>=CONFIG['confirm_s']-1e-9 or not snapshot[a]:continue
            left_cand=values[a-1] if a>0 else None
            right_cand=snapshot[b] if b<len(rows) else None
            left_dur=(rlist[idx-1][1]-rlist[idx-1][0])*step if idx>0 else 0.
            right_dur=(rlist[idx+1][1]-rlist[idx+1][0])*step if idx+1<len(rlist) else 0.
            if left_cand and left_dur>=CONFIG['confirm_s']-1e-9 and len(left_cand)==1 and left_cand[0]['quality'] in BASE_QUALITIES:
                opts=[same_root_base_supported(left_cand,rows[j]) for j in range(a,b)]
                if all(c is not None for c in opts) and all(any(c['root_pc']==left_cand[0]['root_pc'] and c['quality'] in EXT_QUALITIES for c in snapshot[j]) for j in range(a,b)):
                    for j,candidates in zip(range(a,b),opts):values[j]=candidates;status[j]='consolidated_same_root_extension'
                    continue
            if right_cand and right_dur>=CONFIG['confirm_s']-1e-9 and len(right_cand)==1 and right_cand[0]['quality'] in BASE_QUALITIES:
                opts=[same_root_base_supported(right_cand,rows[j]) for j in range(a,b)]
                if all(c is not None for c in opts) and all(any(c['root_pc']==right_cand[0]['root_pc'] and c['quality'] in EXT_QUALITIES for c in snapshot[j]) for j in range(a,b)):
                    for j,candidates in zip(range(a,b),opts):values[j]=candidates;status[j]='consolidated_same_root_extension'
                    continue
            if dur<CONFIG['weak_change_s']-1e-9 and not any(strong_change(rows[j]) for j in range(a,b)):
                if left_cand:
                    options=[supported(left_cand,rows[j]) for j in range(a,b)]
                    if all(c is not None for c in options):
                        for j,candidates in zip(range(a,b),options):values[j]=candidates;status[j]='retained_supported_weak_change'
                        continue
                if right_cand and right_dur>=CONFIG['confirm_s']-1e-9:
                    options=[supported(right_cand,rows[j]) for j in range(a,b)]
                    if all(c is not None for c in options):
                        for j,candidates in zip(range(a,b),options):values[j]=candidates;status[j]='confirmed_lookahead_neighbor'
                        continue
            if dur<=.17+1e-9 and left_cand and right_cand and group_key(left_cand)!=group_key(right_cand) and (left_dur>=CONFIG['confirm_s']-1e-9 or right_dur>=CONFIG['confirm_s']-1e-9):
                bridged=[]
                for j in range(a,b):
                    r_opt=supported(right_cand,rows[j],gap=CONFIG['bridge_audio_gap']) if right_dur>=CONFIG['confirm_s']-1e-9 else None
                    l_opt=supported(left_cand,rows[j],gap=CONFIG['bridge_audio_gap']) if left_dur>=CONFIG['confirm_s']-1e-9 else None
                    bridged.append(r_opt or l_opt)
                if all(c is not None for c in bridged):
                    for j,candidates in zip(range(a,b),bridged):values[j]=candidates;status[j]='bridged_transition_chatter'
    output=[]
    for i,(row,candidates) in enumerate(zip(rows,values)):
        lo=np.searchsorted(times,times[i]-CONFIG['slash_window_s']/2)
        hi=np.searchsorted(times,times[i]+CONFIG['slash_window_s']/2,side='right')
        full=(times[i]-.25>=times[0]-1e-9 and times[i]+.25<=times[-1]+1e-9)
        evidence=[r['context']['bass'] for r in rows[lo:hi]]
        bass=row['context']['bass'];pc=bass.get('pc');midi=bass.get('midi');shown=[]
        for source in candidates:
            c=copy.deepcopy(source)
            c.setdefault('base_symbol',c['symbol'].split('/')[0])
            c['bass_pc']=pc;c['bass_midi']=midi;c['bass_status']=bass['status']
            same=[e for e in evidence if e.get('pc')==pc and pc is not None]
            persistent=bool(full and evidence and len(same)/len(evidence)>=CONFIG['slash_presence'])
            activation=float(np.median([e.get('activation',0) for e in same])) if same else 0.
            low_inv=is_low_below_root_inversion(c,pc,midi) and bool(full and bass.get('presence',0)>=CONFIG['slash_presence'] and bass.get('activation',0)>=CONFIG['low_inversion_activation'])
            reliable=len(candidates)==1 and pc in c['pcs'] and ((persistent and activation>=CONFIG['slash_activation']) or low_inv)
            if pc==c['root_pc']:
                c['symbol']=c['base_symbol'];c['bass_display_status']='root_position'
            elif reliable:
                c['symbol']=c['base_symbol']+'/'+NAMES[pc]
                c['bass_display_status']='low_string_below_root_inversion' if low_inv else 'sustained_strong_inversion_candidate'
            else:c=plain(c,'bass_hypothesis_only')
            shown.append(c)
        shown.sort(key=identity)
        output.append(dict(display_candidates=shown,status=status[i],
                           underlying_context_status=row['context']['status'],
                           slash_policy='strong_persistent_or_low_below_root_inversion',
                           observed_bass=copy.deepcopy(bass)))
    # Remove short islands of slash spelling; allow 0.20s for physical low-below-root inversions (e.g. D/F# passing chord).
    labels=[tuple((identity(c),c.get('bass_pc')) for c in r['display_candidates']) for r in output]
    start=0
    for i in range(1,len(output)+1):
        if i==len(output) or labels[i]!=labels[start]:
            low_inv_run=any(c.get('bass_display_status')=='low_string_below_root_inversion' for r in output[start:i] for c in r['display_candidates'])
            min_s=CONFIG['low_inversion_min_run_s'] if low_inv_run else CONFIG['slash_min_run_s']
            if (i-start)*step<min_s-1e-9:
                for row in output[start:i]:
                    row['display_candidates']=[plain(c,'short_bass_island_suppressed') if '/' in c['symbol'] else c for c in row['display_candidates']]
            start=i
    if isinstance(tempo,dict) and tempo.get('bpm'):
        if not tempo.get('bar_aligned'):
            align_tempo_to_chords(times,rows,output,tempo)
        output=quantize_to_16beat_grid(times,rows,output,bpm=tempo['bpm'],offset_s=tempo.get('offset_s',0.))
    return output


apply_chord_presentation_layer = prepare
