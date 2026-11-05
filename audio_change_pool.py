"""Audio-only change candidates and boundary-clipped short evidence windows.

No reference chord labels, hand positions, or annotation boundaries are accepted.
"""
import numpy as np
from scipy.signal import find_peaks
from audio_note_calibrator import probabilities_to_chroma

CONTEXT=.2
HEIGHT=.25
PROMINENCE=.08
MIN_DISTANCE=.2

def detect_changes(times,note_frames):
    times=np.asarray(times,float);values=np.asarray(note_frames,float)
    if values.shape!=(len(times),88) or len(times)<2 or not np.isfinite(values).all() or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid model time grid')
    note=values[:,17:68];pc=np.zeros((len(times),12))
    for j,midi in enumerate(range(38,89)):pc[:,midi%12]+=note[:,j]
    cumulative=np.vstack([np.zeros(12),pc.cumsum(axis=0)]);scores=np.zeros(len(times))
    for i,t in enumerate(times):
        if t-CONTEXT<times[0] or t+CONTEXT>times[-1]:continue
        a=np.searchsorted(times,t-CONTEXT);b=np.searchsorted(times,t+CONTEXT)
        if a==i or b==i:continue
        left=(cumulative[i]-cumulative[a])/(i-a);right=(cumulative[b]-cumulative[i])/(b-i)
        if min(left.sum(),right.sum())<.3:continue
        scores[i]=max(0.,1-np.dot(left,right)/max(np.linalg.norm(left)*np.linalg.norm(right),1e-12))
    dt=float(np.median(np.diff(times)));idx,_=find_peaks(scores,height=HEIGHT,prominence=PROMINENCE,distance=max(1,round(MIN_DISTANCE/dt)))
    return times[idx],scores,idx

def clipped_pool(times,note_frames,query,width,boundaries):
    times=np.asarray(times,float);values=np.asarray(note_frames,float);boundaries=np.asarray(boundaries,float);rows=[];supports=[]
    if width<=0 or not np.isfinite(width) or values.shape!=(len(times),88) or not np.isfinite(values).all():raise ValueError('Invalid pooling input')
    if not np.isfinite(boundaries).all() or np.any(np.diff(boundaries)<=0):raise ValueError('Invalid boundary candidates')
    for t in query:
        if t-width/2<times[0] or t+width/2>times[-1]:raise ValueError('Incomplete audio window')
        a=t-width/2;b=t+width/2;left=boundaries[boundaries<=t];right=boundaries[boundaries>t]
        if len(left):a=max(a,float(left[-1]))
        if len(right):b=min(b,float(right[0]))
        ia=np.searchsorted(times,a);ib=np.searchsorted(times,b)
        if ia>=ib:rows.append(np.zeros(51))
        else:rows.append(values[ia:ib,17:68].max(axis=0))
        supports.append(dict(start_s=float(a),end_s=float(b),clipped=bool(a>t-width/2+1e-9 or b<t+width/2-1e-9),near_change=bool(len(boundaries) and np.min(abs(boundaries-t))<.04)))
    return probabilities_to_chroma(np.array(rows),.3),supports
