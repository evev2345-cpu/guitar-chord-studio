"""Noise-gated variant; threshold selected on validation compositions only."""
import numpy as np
from scipy.signal import find_peaks

def detect_changes(times,frames,height=.15):
    times=np.asarray(times,float);frames=np.asarray(frames,float)
    if frames.shape!=(len(times),88) or len(times)<2 or not np.isfinite(frames).all() or not np.isfinite(times).all() or np.any(np.diff(times)<=0):raise ValueError('Invalid model grid')
    notes=np.where(frames[:,17:68]>=.3,frames[:,17:68],0.);pc=np.zeros((len(times),12))
    for j,m in enumerate(range(38,89)):pc[:,m%12]+=notes[:,j]
    prefix=np.vstack([np.zeros(12),pc.cumsum(axis=0)]);score=np.zeros(len(times))
    for i,t in enumerate(times):
        if t-.2<times[0] or t+.2>times[-1]:continue
        a=np.searchsorted(times,t-.2);b=np.searchsorted(times,t+.2)
        if a==i or b==i:continue
        x=(prefix[i]-prefix[a])/(i-a);y=(prefix[b]-prefix[i])/(b-i)
        if min(x.sum(),y.sum())<.3:continue
        score[i]=max(0.,1-np.dot(x,y)/max(np.linalg.norm(x)*np.linalg.norm(y),1e-12))
    idx,_=find_peaks(score,height=height,prominence=.08,distance=max(1,round(.2/np.median(np.diff(times)))))
    return times[idx],score,idx
