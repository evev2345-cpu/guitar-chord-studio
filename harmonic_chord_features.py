"""Experimental, fixed harmonic-spectrum decomposition. No trained parameters.

Fits nonnegative note amplitudes per audio window; these are candidates, not notes
or calibrated probabilities. Harmonic amplitudes and tuning are fixed assumptions.
"""
from functools import lru_cache
import numpy as np
from scipy.optimize import nnls
from scipy.ndimage import maximum_filter1d

WINDOW=8192
MIDIS=np.arange(38,89)  # D2 through E6, inclusive.

@lru_cache(4)
def dictionary(rate):
    if rate<=12000:raise ValueError('Require sample rate above 12kHz')
    freq=np.fft.rfftfreq(WINDOW,1/rate);valid=(freq>=50)&(freq<=6000)
    t=np.arange(WINDOW)/rate;window=np.hanning(WINDOW)
    columns=[]
    for midi in MIDIS:
        fundamental=440*2**((midi-69)/12)
        # Incoherent sum of magnitude spectra; arbitrary waveform phase is not a label.
        col=sum(np.abs(np.fft.rfft(np.cos(2*np.pi*fundamental*h*t)*window))/h
                for h in range(1,9) if fundamental*h<rate/2)
        columns.append(col[valid])
    return freq[valid],np.array(columns).T,valid

def harmonic_salience(samples,rate):
    x=np.asarray(samples,float)
    if x.shape!=(WINDOW,) or not np.isfinite(x).all():raise ValueError('Require one finite mono window')
    freq,templates,valid=dictionary(rate)
    mag=np.abs(np.fft.rfft(x*np.hanning(WINDOW)))[valid]
    if np.sqrt(np.mean(x*x))<1e-5:return np.zeros(12),np.zeros(len(MIDIS)),0.
    # Reduce broad spectral-envelope dominance; apply identical weights to observation and model.
    envelope=maximum_filter1d(mag,size=max(3,round(100*WINDOW/rate)))
    weights=1/np.sqrt(np.maximum(envelope,mag.max()*.01))
    model=templates*weights[:,None];target=mag*weights
    norms=np.linalg.norm(model,axis=0);unit=model/np.maximum(norms,1e-12)
    amplitudes,_=nnls(unit,target,maxiter=10*len(MIDIS))
    amplitudes=amplitudes/np.maximum(norms,1e-12)
    chroma=np.bincount(MIDIS%12,weights=amplitudes,minlength=12)
    chroma/=max(chroma.sum(),1e-12)
    residual=float(np.linalg.norm(target-model@amplitudes)/max(np.linalg.norm(target),1e-12))
    return chroma,amplitudes,residual
