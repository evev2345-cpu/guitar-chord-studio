"""Portable residual note calibrator on frozen Basic Pitch D2-E6 activations."""
import numpy as np

def corrected_probabilities(activations,weights):
    p=np.asarray(activations,float)
    if p.ndim!=2 or p.shape[1]!=51 or not np.isfinite(p).all():raise ValueError('Require finite N by51 activations')
    logits=np.log(np.clip(p,1e-4,1-1e-4)/np.clip(1-p,1e-4,1-1e-4))
    hidden=np.maximum(0,(logits/8)@weights['w1'].T+weights['b1'])
    out=logits+hidden@weights['w2'].T+weights['b2']
    return 1/(1+np.exp(-np.clip(out,-50,50)))

def probabilities_to_chroma(probabilities,threshold):
    p=np.asarray(probabilities,float)
    if p.ndim!=2 or p.shape[1]!=51 or not np.isfinite(p).all() or not 0<threshold<1:raise ValueError('Invalid calibrated activations')
    weights=np.where(p>=threshold,p,0.);sal=np.zeros((len(p),12))
    for i,midi in enumerate(range(38,89)):sal[:,midi%12]+=weights[:,i]
    return sal/np.maximum(sal.sum(axis=1,keepdims=True),1e-12)
