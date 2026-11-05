"""Three feature alternatives on the same already D2-E6 filtered window.

The harmonic observation AND model are restricted to the retained band, so removed
high harmonics are not treated as observed negative evidence. Evaluation only.
"""
from functools import lru_cache
import numpy as np
from scipy.ndimage import maximum_filter1d
from scipy.optimize import nnls
from scipy.signal import find_peaks
from audio_analysis import features
from harmonic_chord_features import dictionary,MIDIS,WINDOW
from sweep_bandcut_vision_weights import LOW_HZ,HIGH_HZ

@lru_cache(4)
def cut_dictionary(rate):
    freq,templates,_=dictionary(rate)
    keep=(freq>=LOW_HZ)&(freq<=HIGH_HZ)
    return templates[keep],(np.fft.rfftfreq(WINDOW,1/rate)>=LOW_HZ)&(np.fft.rfftfreq(WINDOW,1/rate)<=HIGH_HZ)

def cut_features(samples,rate):
    x=np.asarray(samples,float)
    if x.shape!=(WINDOW,) or not np.isfinite(x).all():raise ValueError('Require one finite mono window')
    evidence,_=features(x,rate,min_frequency=LOW_HZ,max_frequency=HIGH_HZ)
    peak=np.array(evidence['pitch_class_salience'][0]['salience'])
    if np.sqrt(np.mean(x*x))<1e-5:
        return dict(peak=peak,harmonic=np.zeros(12),supported=np.zeros(12)),np.zeros(len(MIDIS)),0.
    templates,valid=cut_dictionary(rate);spectrum=np.abs(np.fft.rfft(x*np.hanning(WINDOW)));mag=spectrum[valid]
    envelope=maximum_filter1d(mag,size=max(3,round(100*WINDOW/rate)))
    weights=1/np.sqrt(np.maximum(envelope,mag.max()*.01));model=templates*weights[:,None];target=mag*weights
    norms=np.linalg.norm(model,axis=0);unit=model/np.maximum(norms,1e-12)
    amplitudes,_=nnls(unit,target,maxiter=10*len(MIDIS));amplitudes/=np.maximum(norms,1e-12)
    allowed=set();bins,_=find_peaks(spectrum)
    for b in bins:
        if spectrum[b]<=max(spectrum.max()*.12,1e-7):continue
        logs=np.log(np.maximum(spectrum[b-1:b+2],1e-15));denom=logs[0]-2*logs[1]+logs[2]
        delta=float(np.clip(.5*(logs[0]-logs[2])/denom,-.5,.5)) if denom else 0.
        hz=(b+delta)*rate/WINDOW
        if LOW_HZ<=hz<=HIGH_HZ:allowed.add(round(69+12*np.log2(hz/440)))
    arrays=dict(peak=peak)
    for name,amp in [('harmonic',amplitudes),('supported',amplitudes*np.array([m in allowed for m in MIDIS]))]:
        chroma=np.bincount(MIDIS%12,weights=amp,minlength=12);arrays[name]=chroma/max(chroma.sum(),1e-12)
    residual=float(np.linalg.norm(target-model@amplitudes)/max(np.linalg.norm(target),1e-12))
    return arrays,amplitudes,residual
