"""Root-only tie resolution boundary: same PC set, same audio score, validated cue.

Generic fingering PC compatibility cannot distinguish identical-PC chords.
Root support must come from separately validated root/voicing evidence; an
arbitrary fingertip PC mass or the lowest audio note alone is not validation.
"""
import copy

def resolve(candidates,root_support=None,*,visual_status='unknown',minimum_margin=.1):
    result=copy.deepcopy(candidates)
    if not candidates:return dict(candidates=result,status='no_audio_candidates',tie_group=[])
    best=candidates[0];group=[c for c in candidates if abs(c['score']-best['score'])<=1e-10 and set(c['pcs'])==set(best['pcs'])]
    if len(group)<2:return dict(candidates=result,status='no_equal_pc_audio_tie',tie_group=group)
    if visual_status!='validated_root_or_voicing' or not root_support:
        return dict(candidates=result,status='ambiguous_visual_unverified',tie_group=group)
    ranked=sorted(group,key=lambda c:root_support.get(c['root_pc'],0),reverse=True)
    margin=root_support.get(ranked[0]['root_pc'],0)-root_support.get(ranked[1]['root_pc'],0)
    if margin<minimum_margin:return dict(candidates=result,status='ambiguous_visual_margin',tie_group=group,visual_margin=margin)
    chosen=ranked[0];result=[copy.deepcopy(chosen)]+[c for c in result if (c['root_pc'],c['quality'])!=(chosen['root_pc'],chosen['quality'])]
    return dict(candidates=result,status='root_tie_reranked',tie_group=group,visual_margin=margin,
                interpretation='Root/voicing support is a soft preference, not confirmed contact or exclusion of inversions')
