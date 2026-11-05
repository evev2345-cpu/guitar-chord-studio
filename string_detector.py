"""Image-supported string candidates, variable count; no API or chord logic."""
import cv2
import numpy as np
from scipy.signal import find_peaks


def detect_strings(flat, frets=(), native_board_width=None, physical_order=None, reference=None):
    if flat is None or flat.ndim not in (2,3):
        raise ValueError('Expected a fretboard image')
    gray=cv2.cvtColor(flat,cv2.COLOR_BGR2GRAY) if flat.ndim==3 else flat.copy()
    h,w=gray.shape
    if h<30 or w<60:raise ValueError('Fretboard image is too small')
    result=dict(width=w,height=h,strings=[],unresolved=[],observed_count=0,estimated_count=0,
        native_board_width_px=native_board_width,physical_order=physical_order,
        numbering_status='unresolved',status='insufficient_evidence',
        note='Variable-count line candidates; no six-line spacing template. Physical numbering is distinct from screen rank.')
    if float(np.std(gray))<2:
        result['unresolved']=[dict(string_num=n,source='unresolved',geometry=None,reason='no image evidence') for n in range(1,7)]
        return result
    native_scale=h/max(1,native_board_width or h)
    smooth=cv2.GaussianBlur(gray.astype(np.float32),(0,0),max(.5,native_scale*.25))
    low=cv2.GaussianBlur(smooth,(1,0),1,sigmaY=max(2,native_scale*1.2))
    # Both signs are retained, so light/dark strings are supported.
    ridge=np.abs(smooth-low)
    ridge=cv2.GaussianBlur(ridge,(max(3,int(w*.012)//2*2+1),1),0)
    energy=np.minimum(ridge/(np.median(ridge,axis=0,keepdims=True)+1),6)
    xs=np.arange(max(3,int(w*.02)),min(w-3,int(w*.98)),max(2,w//240))
    valid=np.ones(len(xs),bool)
    for f in frets:
        if 'xt' in f:
            valid &= ~((xs>=min(f['xt'],f['xb'])-w*.004)&(xs<=max(f['xt'],f['xb'])+w*.004))
    xs=xs[valid]
    if len(xs)<20:
        result['unresolved']=[dict(string_num=n,source='unresolved',geometry=None,reason='insufficient unmasked columns') for n in range(1,7)]
        return result
    drifts=np.linspace(-h*.16,h*.16,49)
    rows=np.arange(h)
    profiles=[]
    for drift in drifts:
        yy=rows[:,None]+drift*(xs[None,:]/(w-1)-.5)
        lo=np.floor(yy).astype(int);fraction=yy-lo
        samples=(1-fraction)*energy[np.clip(lo,0,h-1),xs]+fraction*energy[np.clip(lo+1,0,h-1),xs]
        samples[(yy<h*.035)|(yy>h*.965)]=0
        profiles.append(np.mean(np.minimum(samples,3.5),axis=1))
    profiles=np.asarray(profiles)
    profile=profiles.max(axis=0)
    # Native-pixel-aware separation merges two edges of one wire, without
    # imposing six regularly spaced locations.
    distance=max(3,int(native_scale*3.5))
    peaks,_=find_peaks(profile,distance=distance,prominence=.22)
    candidates=[]
    for peak in peaks:
        di=int(np.argmax(profiles[:,peak]));drift=float(drifts[di])
        left=float(peak-drift/2);right=float(peak+drift/2)
        if not (h*.025<=left<=h*.975 and h*.025<=right<=h*.975):continue
        if (left+right)/2 < h*.055 or (left+right)/2 > h*.94:continue
        yy=peak+drift*(xs/(w-1)-.5)
        sampled=energy[np.clip(np.round(yy).astype(int),0,h-1),xs]
        baseline=float(np.median(profiles[di]))
        support=sampled>1.4
        blocks=[]
        for indices in np.array_split(np.arange(len(xs)),12):
            if len(indices) and np.mean(support[indices])>=.40:
                blocks.append([float(xs[indices[0]]),float(xs[indices[-1]])])
        if profile[peak]-baseline<.22 or len(blocks)<4 or float(np.mean(support))<.30:continue
        candidates.append(dict(string_num=None,number_source='unresolved',source='observed',
            kind='string_candidate',geometry_source='fit_to_visible_segments',
            outside_observed_intervals='model_prediction_not_direct_observation',m=drift/(w-1),b=left,y_left=left,y_right=right,
            model=dict(type='line',equation='y=m*x+b',m=drift/(w-1),b=left,domain_x=[0,w-1]),
            observed_intervals=blocks,support_fraction=float(np.mean(support)),
            evidence_score=float(profile[peak]),prominence=float(profile[peak]-baseline)))
    # Reject paths that stitch together portions of different strings. This is
    # a direction-consistency prior, independent of how many strings exist.
    if len(candidates)>1:
        directions=np.array([s['m']*(w-1) for s in candidates])
        weights=np.array([s['evidence_score']**2*s['support_fraction'] for s in candidates])
        consistency=np.exp(-((directions[:,None]-directions[None,:])/(h*.035))**2)@weights
        dominant=directions[int(np.argmax(consistency))]
        rejected=[dict(s,rejection_reason='inconsistent_direction') for s,d in zip(candidates,directions) if abs(d-dominant)>h*.06]
        candidates=[s for s,d in zip(candidates,directions) if abs(d-dominant)<=h*.06]
        result['rejected_candidates']=rejected
    candidates.sort(key=lambda s:(s['y_left']+s['y_right'])/2)
    for i,line in enumerate(candidates):line.update(line_id=f'line_{i+1}',screen_rank=i+1)
    # Identity is inferred only for a complete, noncrossing, plausible family.
    # Position detection never inserts/removes lines to achieve this condition.
    if len(candidates)==6 and physical_order in ('low_e_top','high_e_top'):
        left=np.array([s['y_left'] for s in candidates]);right=np.array([s['y_right'] for s in candidates])
        gaps=np.r_[np.diff(left),np.diff(right)]
        if gaps.min()>h*.065 and gaps.max()/gaps.min()<1.7 and left[-1]-left[0]>h*.60:
            for i,line in enumerate(candidates):
                line.update(string_num=6-i if physical_order=='low_e_top' else i+1,
                            number_source='inferred_from_six_ordered_candidates_and_physical_sides')
            result['numbering_status']='inferred'
    # Estimates require explicit previously validated geometry, never a comb.
    if reference:
        if not reference.get('validated') or reference.get('width')!=w or reference.get('height')!=h:
            raise ValueError('Reference estimates require explicitly validated same-canvas geometry')
        for prior in reference.get('strings',[]):
            if prior.get('string_num') is None:continue
            if any(abs(s['b']-prior['b'])<h*.035 for s in candidates):continue
            estimate=dict(prior)
            estimate.update(source='estimated',number_source='reference',observed_intervals=[],
                            line_id='reference_'+str(prior['string_num']),reference_id=reference.get('source_id'))
            candidates.append(estimate)
    assigned={s['string_num'] for s in candidates if s.get('string_num') is not None}
    result['unresolved']=[dict(string_num=n,source='unresolved',geometry=None,
        reason='physical identity not established' if candidates else 'no supported line') for n in range(1,7) if n not in assigned]
    result.update(strings=candidates,observed_count=sum(s['source']=='observed' for s in candidates),
        estimated_count=sum(s['source']=='estimated' for s in candidates),
        status='detected' if result['numbering_status']=='inferred' else ('partial' if candidates else 'insufficient_evidence'),
        resolution_limited=native_board_width is not None and native_board_width<18)
    return result


def query_string_fret(x,y,string_result,frets,allow_estimates=False):
    if not (0<=x<string_result.get('width',800) and 0<=y<string_result.get('height',150)):return None
    lines=[s for s in string_result.get('strings',[]) if s.get('string_num') is not None]
    if not lines:return None
    distances=[abs(s['m']*x+s['b']-y) for s in lines]
    i=int(np.argmin(distances));chosen=lines[i]
    tolerance=string_result.get('height',150)*.06
    local_observed=chosen['source']=='observed' and any(a<=x<=b for a,b in chosen.get('observed_intervals',[]))
    if distances[i]>tolerance or (not local_observed and not allow_estimates):return None
    wires=sorted((f for f in frets if 'xt' in f),key=lambda f:f['fret_num'])
    for a,b in zip(wires,wires[1:]):
        if b['fret_num']==a['fret_num']+1 and a['m']*y+a['b']<=x<b['m']*y+b['b']:
            return dict(string=chosen['string_num'],fret=b['fret_num'],string_source='observed' if local_observed else 'estimated',
                numbering_source=chosen['number_source'],fret_estimated=bool(a.get('estimated') or b.get('estimated') or a.get('interpolated') or b.get('interpolated')))
    return None


def render_strings(flat,raw,inverse,result):
    flat_vis=flat.copy();raw_vis=raw.copy()
    h,w=flat.shape[:2]
    def draw(line,a,b,color):
        if b<=a:return
        y1=line['m']*a+line['b'];y2=line['m']*b+line['b']
        cv2.line(flat_vis,(round(a),round(y1)),(round(b),round(y2)),color,1,cv2.LINE_AA)
        points=np.array([[[a,y1]],[[b,y2]]],np.float32)
        transformed=cv2.perspectiveTransform(points,inverse).reshape(-1,2)
        cv2.line(raw_vis,tuple(np.round(transformed[0]).astype(int)),tuple(np.round(transformed[1]).astype(int)),color,1,cv2.LINE_AA)
    for line in result.get('strings',[]):
        # Dashed magenta is model continuation, never presented as visible wire.
        for x in range(0,w-1,14):draw(line,x,min(x+6,w-1),(255,0,255))
        if line['source']=='observed':
            for a,b in line.get('observed_intervals',[]):
                draw(line,max(0,a),min(w-1,b),(0,255,255))
        label=(('~' if line.get('number_source','').startswith('inferred') else '')+str(line['string_num'])
               if line.get('string_num') is not None else 'C'+str(line.get('screen_rank','?')))
        cv2.putText(flat_vis,label,(w-35,round(line['m']*(w-1)+line['b'])-2),cv2.FONT_HERSHEY_SIMPLEX,.35,(0,255,255),1)
    return flat_vis,raw_vis
