"""Evaluation-only alternatives to coverage-biased chord ranking; no learned weights."""
import numpy as np
from guitarset_benchmark import TEMPLATES,rank_saliences


def ordered(scores,usable):
    return scores,np.argsort(-scores,axis=1,kind='stable'),usable


def score_variants(saliences):
    sal=np.asarray(saliences,float)
    legacy=rank_saliences(sal)
    masks=np.zeros((len(TEMPLATES),12))
    for j,template in enumerate(TEMPLATES):masks[j,template['pcs']]=1
    norm=np.linalg.norm(sal,axis=1)
    active=(sal>0)&(sal>=.1*sal.max(axis=1)[:,None])
    usable=(norm>0)&(active.sum(axis=1)>=2)
    scores=(sal@masks.T)/(np.maximum(norm[:,None],1e-300)*np.sqrt(masks.sum(axis=1))[None,:])
    scores[~usable]=-np.inf
    finite=np.where(usable[:,None],scores,0.)
    padded=np.pad(finite,((1,1),(0,0)));support=np.pad(usable.astype(float),(1,1))
    denominator=support[:-2]+support[1:-1]+support[2:]
    smoothed=(padded[:-2]+padded[1:-1]+padded[2:])/np.maximum(denominator[:,None],1)
    smooth_usable=denominator>0;smoothed[~smooth_usable]=-np.inf
    return dict(legacy=legacy,cosine=ordered(scores,usable),cosine_context=ordered(smoothed,smooth_usable))
