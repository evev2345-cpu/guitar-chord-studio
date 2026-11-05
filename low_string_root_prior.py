"""Soft root prior from string/fret location support; preserves tied alternatives.

Weights are hypotheses, not calibrated confidence. Low note != guaranteed root.
No open-string, mute or pressing state is inferred from absent fingertips.
"""
import copy
from visual_root_tiebreak import resolve

STRING_WEIGHTS={6:1.,5:.8,4:.35,3:.15,2:.05,1:.025}
TUNING={6:40,5:45,4:50,3:55,2:59,1:64}
FINGER_WEIGHTS={'index':1.,'ring':1.,'pinky':1.,'middle':.25}

def low_string_support(fingers,*,include_uncertain_middle=False):
    cells={}
    for finger in fingers:
        name=finger['finger']
        if name=='middle' and not include_uncertain_middle:continue
        reliability=FINGER_WEIGHTS.get(name,0.)
        for cell in finger['cells']:
            string=cell['virtual_string_num'];fret=cell['physical_fret_candidate'];mass=float(cell['position_mass'])
            if string not in TUNING or fret<0 or not 0<=mass<=1:raise ValueError('Invalid location cell')
            key=(string,fret);value=reliability*mass
            if value>cells.get(key,0.):cells[key]=value
    roots=[0.]*12;bass=[0.]*12;contributions=[]
    for (string,fret),mass in cells.items():
        if not mass:continue
        midi=TUNING[string]+fret;weighted=STRING_WEIGHTS[string]*mass;roots[midi%12]+=weighted
        if string in (6,5):bass[midi%12]+=weighted
        contributions.append(dict(string=string,physical_fret=fret,midi=midi,pc=midi%12,location_support=mass,string_weight=STRING_WEIGHTS[string],weighted_support=weighted))
    return dict(root_support=roots,low65_support=bass,cells=contributions,
                contact='unknown',score_type='uncalibrated_weighted_location_support')

def assess(candidates,fingers,*,include_uncertain_middle=False,visual_status='unknown',minimum_low65_support=.05):
    support=low_string_support(fingers,include_uncertain_middle=include_uncertain_middle);group=resolve(candidates)['tie_group'];ranked=sorted(group,key=lambda c:support['root_support'][c['root_pc']],reverse=True)
    allowed=visual_status
    if not ranked or support['low65_support'][ranked[0]['root_pc']]<minimum_low65_support:allowed='insufficient_low_string_support'
    decision=resolve(candidates,{i:v for i,v in enumerate(support['root_support'])},visual_status=allowed,minimum_margin=.05)
    return dict(support=support,exploratory_tie_order=copy.deepcopy(ranked),decision=decision,
                uncertain_middle_included=include_uncertain_middle,visual_status=visual_status,
                interpretation='Soft root preference only; inversion alternatives retained, no confirmed sounding/contact claim')
