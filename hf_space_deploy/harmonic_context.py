"""Bounded, additive audio/key/neighbor priors and provisional bass spelling.

No chord/scale whitelist, no ground-truth input, no instrument attribution.
Raw coverage scores and raw top-three predictions are never overwritten.
"""
import copy
import numpy as np
from guitarset_benchmark import TEMPLATES, rank_saliences
from temporal_audio_pool import pooled_chroma
from harmony_engine import NAMES, SUFFIX

CONFIG = dict(key_bonus_max=.02, progression_bonus_max=.025, bass_bonus_max=.05,
              maximum_raw_gap=.06, minimum_decision_margin=.025,
              bass_window_s=.30, bass_activation=.35, bass_presence=.70,
              bass_midi_range=[38, 59], mode='offline_additive_soft_priors_v1',
              full_mix_concordance_bonus=.05)
SCALE = np.array([0, 2, 4, 5, 7, 9, 11])


def bass_track(grid, frames, times):
    """Lowest sustained model candidate, restricted to existing guitar note range."""
    grid=np.asarray(grid);frames=np.asarray(frames);result=[]
    for t in times:
        lo=np.searchsorted(grid,t-.15);hi=np.searchsorted(grid,t+.15,side='right')
        if t-.15<grid[0] or t+.15>grid[-1] or hi-lo<3:
            result.append(dict(status='insufficient_window',midi=None,pc=None));continue
        values=frames[lo:hi,17:39]  # MIDI38..59; below-D2 evidence is not introduced.
        presence=(values>=CONFIG['bass_activation']).mean(axis=0)
        means=values.mean(axis=0)
        eligible=np.flatnonzero((presence>=CONFIG['bass_presence'])&(means>=CONFIG['bass_activation']))
        if not len(eligible):
            result.append(dict(status='unknown',midi=None,pc=None));continue
        i=int(eligible[0]);midi=38+i
        result.append(dict(status='provisional_sustained_low_note',midi=midi,pc=midi%12,
                           presence=float(presence[i]),activation=float(means[i]),
                           instrument_attribution='unknown',window_s=.3))
    return result


def key_hypotheses(frames, duration):
    # Relative major/minor share a collection; do not claim their mode is resolved.
    notes=np.where(frames[:,17:68]>=.3,frames[:,17:68],0).sum(axis=0)
    mass=np.bincount(np.arange(38,89)%12,weights=notes,minlength=12)
    if mass.sum()==0:return dict(status='unknown',hypotheses=[])
    mass/=mass.sum();hyp=[]
    for root in range(12):
        pcs=sorted(((SCALE+root)%12).tolist());coverage=float(mass[pcs].sum())
        hyp.append(dict(major_root_pc=root,relative_minor_root_pc=(root+9)%12,pcs=pcs,
                        label=NAMES[root]+' major / '+NAMES[(root+9)%12]+' minor',coverage=coverage))
    hyp.sort(key=lambda h:-h['coverage'])
    stable=duration>=8 and hyp[0]['coverage']>=.78 and hyp[0]['coverage']-hyp[1]['coverage']>=.04
    return dict(status='provisional_collection' if stable else 'ambiguous',hypotheses=hyp[:3],
                bonus_enabled=bool(stable),mode_identified=False,source='global_audio_pitch_mass')


def affinity(left, right):
    union=set(left['pcs'])|set(right['pcs']);shared=len(set(left['pcs'])&set(right['pcs']))/max(1,len(union))
    movement=(right['root_pc']-left['root_pc'])%12
    root={5:1.,7:.7,2:.5,10:.5,0:.3}.get(movement,.15)
    return .5*shared+.5*root


def spell(candidate, bass):
    c=copy.deepcopy(candidate);pc=bass.get('pc')
    c['bass_pc']=pc;c['bass_midi']=bass.get('midi');c['bass_status']=bass['status']
    c['base_symbol']=NAMES[c['root_pc']]+SUFFIX.get(c['quality'],c['quality'])
    c['symbol']=c['base_symbol']+('/'+NAMES[pc] if pc is not None and pc!=c['root_pc'] else '')
    c['bass_in_chord']=pc in c['pcs'] if pc is not None else None
    c['bass_instrument']='unknown'
    return c


def rerank_candidate_pool(pool, bass, key, before=(), after=(), full_mix_top=None):
    """Bonuses only. Strong raw winners cannot be displaced by a weak candidate."""
    if not pool:return []
    best=max(c['score'] for c in pool);out=[]
    fm_candidates = [(f['root_pc'], f['quality']) for f in (full_mix_top or [])[:2]]
    for source in pool:
        c=copy.deepcopy(source);eligible=best-c['score']<=CONFIG['maximum_raw_gap']+1e-10
        key_fit=0.
        if key.get('bonus_enabled'):
            scale=set(key['hypotheses'][0]['pcs'])
            key_fit=(len(set(c['pcs'])&scale)/len(c['pcs']))**2
        neighbors=[affinity(p,c) for p in before]+[affinity(c,p) for p in after]
        progression=float(np.mean(neighbors)) if neighbors else 0.
        # A root-position interpretation is a preference, never a proof; inversion
        # alternatives remain listed (e.g. Am7 versus C6/A).
        # In guitar music, major 6th chords (e.g. C6, D6, A6) are almost always inversions or
        # relative minor 7th chords (Am7, Bm7, F#m7). If a relative m7 candidate
        # sharing the exact same pitch classes is present in the pool, do not give '6' an unfair
        # root-match bonus over the standard m7 interpretation.
        has_relative_m7 = (
            c['quality'] == '6' and any(
                other['quality'] == 'm7' and (other['root_pc'] - c['root_pc']) % 12 == 9
                and set(other['pcs']) == set(c['pcs'])
                for other in pool
            )
        )
        pc=bass.get('pc')
        bass_fit=(1. if not has_relative_m7 else .25) if pc==c['root_pc'] else .25 if pc in c['pcs'] else 0.
        fm_fit = 1.0 if (c['root_pc'], c['quality']) in fm_candidates else 0.
        fm_bonus = CONFIG.get('full_mix_concordance_bonus', .05) * fm_fit if eligible else 0.
        bonuses=dict(key=CONFIG['key_bonus_max']*key_fit if eligible else 0.,
                     progression=CONFIG['progression_bonus_max']*progression if eligible else 0.,
                     bass=CONFIG['bass_bonus_max']*bass_fit if eligible else 0.,
                     full_mix=fm_bonus)
        c.update(audio_score=float(c['score']),bonus_components=bonuses,
                 adjusted_score=float(c['score']+sum(bonuses.values())),prior_eligible=eligible)
        out.append(spell(c,bass))
    out.sort(key=lambda c:-c['adjusted_score'])
    return out


def enrich(grid, frames, times, width, raw, baseline_display, key=None, bass=None, full_mix=None):
    times=np.asarray(times);key=key if key is not None else key_hypotheses(frames,float(times[-1]) if len(times) else 0.)
    bass=bass if bass is not None else bass_track(grid,frames,times)
    valid=(times-width/2>=grid[0])&(times+width/2<=grid[-1]);sal=np.zeros((len(times),12))
    sal[valid]=pooled_chroma(grid,frames,times[valid],width)
    scores,order,usable=rank_saliences(sal);result=[]

    # Wider accumulation window (0.8s) for arpeggio and sustained fingerpicking context
    wide_width=min(.8,max(width,.8))
    valid_wide=(times-wide_width/2>=grid[0])&(times+wide_width/2<=grid[-1]);sal_wide=np.zeros((len(times),12))
    if valid_wide.any():sal_wide[valid_wide]=pooled_chroma(grid,frames,times[valid_wide],wide_width)
    scores_w,order_w,usable_w=rank_saliences(sal_wide)
    key_scale=set(key['hypotheses'][0]['pcs']) if (key and key.get('bonus_enabled') and key.get('hypotheses')) else None

    for i,t in enumerate(times):
        pool=[]
        is_arpeggio_recovery=False
        if raw[i]['top3']:
            best=float(scores[i,order[i,0]])
            # Include all plausible dictionary candidates rather than only the first
            # three: an inversion or equal-PC alternative may lie beyond that cutoff.
            ids=[int(j) for j in order[i] if best-scores[i,j]<=CONFIG['maximum_raw_gap']+1e-10]
            pool=[dict(TEMPLATES[j],score=float(scores[i,j])) for j in ids]
        elif usable_w[i]:
            best_w=float(scores_w[i,order_w[i,0]])
            ids=[int(j) for j in order_w[i] if best_w-scores_w[i,j]<=CONFIG['maximum_raw_gap']+1e-10]
            pool=[dict(TEMPLATES[j],score=float(scores_w[i,j])) for j in ids]
            is_arpeggio_recovery=True
        elif bass[i].get('pc') is not None:
            # Dyad recovery: check if 2 pitch classes active in sal[i] or sal_wide[i]
            s_cur=sal[i] if sal[i].max()>0 else sal_wide[i]
            if s_cur.max()>0:
                active_pcs=[pc for pc in range(12) if s_cur[pc]>0 and s_cur[pc]>=.1*s_cur.max()]
                bpc=int(bass[i]['pc'])
                if len(active_pcs)==2 and (bpc in active_pcs or active_pcs[0]==bpc):
                    other_pc=active_pcs[1] if active_pcs[0]==bpc else active_pcs[0]
                    if (other_pc-bpc)%12==7:
                        q='major'
                        if key_scale:
                            maj_3rd=(bpc+4)%12;min_3rd=(bpc+3)%12
                            if min_3rd in key_scale and maj_3rd not in key_scale:q='minor'
                        tmpl=next((t for t in TEMPLATES if t['root_pc']==bpc and t['quality']==q),None)
                        if tmpl:pool=[dict(tmpl,score=.85)];is_arpeggio_recovery=True
                    elif (other_pc-bpc)%12==5:
                        tmpl=next((t for t in TEMPLATES if t['root_pc']==bpc and t['quality']=='sus4'),None)
                        if tmpl:pool=[dict(tmpl,score=.82)];is_arpeggio_recovery=True

        if not pool:
            if full_mix and full_mix.get('raw') and i < len(full_mix['raw']) and full_mix['raw'][i]['top3']:
                fm_raw_i = full_mix['raw'][i]['top3']
                fm_bass_i = full_mix['bass'][i] if (full_mix.get('bass') and i < len(full_mix['bass'])) else dict(status='unknown', midi=None, pc=None)
                fm_key_i = full_mix.get('key') or key
                if fm_raw_i[0]['score'] >= 0.65:
                    best_fm = float(fm_raw_i[0]['score'])
                    ids_fm = [int(j) for j in range(len(fm_raw_i)) if best_fm - fm_raw_i[j]['score'] <= CONFIG['maximum_raw_gap'] + 1e-10]
                    fm_pool = [dict(fm_raw_i[j]) for j in ids_fm]
                    ranked_fm = rerank_candidate_pool(fm_pool, fm_bass_i, fm_key_i)
                    chosen_fm = copy.deepcopy(ranked_fm[0])
                    chosen_fm['source'] = 'full_mix_anchor'
                    chosen_fm['anchor_note'] = '원곡 화성 기반'
                    gap_fm = ranked_fm[0]['adjusted_score'] - ranked_fm[1]['adjusted_score'] if len(ranked_fm) > 1 else 1.
                    result.append(dict(status='full_mix_harmonic_anchor', top3=ranked_fm[:3], bass=fm_bass_i,
                                       display_candidates=[chosen_fm], adjusted_margin=float(gap_fm),
                                       resolved=True, total_candidate_count=len(fm_pool),
                                       instrument_attribution='full_mix_anchor'))
                    continue
            # Original bridged display may remain, but cannot acquire fresh bass/priors.
            chosen=copy.deepcopy(baseline_display[i]['display_candidate'])
            result.append(dict(status='no_current_chord_evidence',top3=[],bass=bass[i],
                               display_candidates=[chosen] if chosen else [],resolved=False));continue
        fm_raw_i = full_mix['raw'][i]['top3'] if (full_mix and full_mix.get('raw') and i < len(full_mix['raw'])) else None
        fm_bass_i = full_mix['bass'][i] if (full_mix and full_mix.get('bass') and i < len(full_mix['bass'])) else None
        eff_bass = bass[i] if (bass[i].get('pc') is not None) else (fm_bass_i if (fm_bass_i and fm_bass_i.get('pc') is not None) else bass[i])
        best=max(c['score'] for c in pool)
        before=[];after=[]
        for offset in [-24,-12,12,24]:
            index=i+offset
            if not 0<=index<len(raw):continue
            neighbors=raw[index]['top3']
            if not neighbors:continue
            # Exact ties are all consulted; never bootstrap from enriched results.
            tied=[c for c in neighbors if abs(c['score']-neighbors[0]['score'])<=1e-10]
            (before if offset<0 else after).extend(tied)
        ranked=rerank_candidate_pool(pool,eff_bass,key,before,after,full_mix_top=fm_raw_i)
        gap=ranked[0]['adjusted_score']-ranked[1]['adjusted_score'] if len(ranked)>1 else 1.
        original_ties=[c for c in pool if abs(c['score']-best)<=1e-10]
        enough=gap>=CONFIG['minimum_decision_margin']
        if len(original_ties)>1 and not enough:
            shown=[spell(c,eff_bass) for c in original_ties];status='ambiguous_keep_alternatives'
        elif enough:
            changed=len(original_ties)>1 or (ranked[0]['root_pc'],ranked[0]['quality'])!=(pool[0]['root_pc'],pool[0]['quality'])
            chosen=ranked[0] if changed else spell(baseline_display[i]['display_candidate'] or ranked[0],eff_bass)
            shown=[chosen];status='arpeggio_sustain_recovery' if is_arpeggio_recovery else ('soft_prior_preference' if changed else 'audio_supported')
        else:
            chosen=baseline_display[i]['display_candidate'] or pool[0]
            shown=[spell(chosen,eff_bass)];status='insufficient_prior_margin_keep_baseline'
        result.append(dict(status=status,top3=ranked[:3],bass=eff_bass,display_candidates=shown,
                           adjusted_margin=float(gap),resolved=bool(len(original_ties)>1 and enough),
                           total_candidate_count=len(pool),instrument_attribution='unknown'))
    return result
