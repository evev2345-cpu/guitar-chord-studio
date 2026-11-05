"""Fixed follow-up: require fundamental peak support at the legacy 12% threshold."""
import numpy as np
from scipy.signal import find_peaks
from harmonic_chord_features import harmonic_salience,MIDIS,WINDOW

def supported_salience(samples,rate):
    _,amplitudes,residual=harmonic_salience(samples,rate)
    mag=np.abs(np.fft.rfft(np.asarray(samples,float)*np.hanning(WINDOW)))
    bins,_=find_peaks(mag);allowed=set()
    for b in bins:
        if mag[b]<=max(mag.max()*.12,1e-7):continue
        logs=np.log(np.maximum(mag[b-1:b+2],1e-15));denom=logs[0]-2*logs[1]+logs[2]
        delta=float(np.clip(.5*(logs[0]-logs[2])/denom,-.5,.5)) if denom else 0.
        hz=(b+delta)*rate/WINDOW
        if 65<=hz<=1600:allowed.add(round(69+12*np.log2(hz/440)))
    supported=amplitudes*np.array([m in allowed for m in MIDIS])
    sal=np.bincount(MIDIS%12,weights=supported,minlength=12)
    sal/=max(sal.sum(),1e-12)
    return sal,supported,residual
