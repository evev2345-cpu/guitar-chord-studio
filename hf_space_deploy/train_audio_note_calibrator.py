"""Train a small note correction network; split by composition before training.

GuitarSet-only note supervision. IDMT and tutorial never train or select settings.
Basic Pitch pretraining overlap prevents claiming independent base-model testing.
"""
import json
import hashlib
from pathlib import Path
import random
import numpy as np
import torch
from torch import nn
from guitarset_benchmark import load_reference,KNOWN_TIMING
from audio_note_calibrator import corrected_probabilities

ROOT=Path(__file__).resolve().parent
PRED=ROOT/'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions'
OUT=ROOT/'dataset/audio_analysis/runs/note_calibrator_20261105_v1'

def split_for(recording_id):
    pattern=recording_id.split('_')[1].split('-')[0]
    return 'validation' if pattern in ('BN3','Funk3') else 'test' if pattern in ('Jazz3','Rock3','SS3') else 'train'

def note_metrics(p,y,threshold):
    pred=p>=threshold;truth=y>0;tp=int((pred&truth).sum());fp=int((pred&~truth).sum());fn=int((~pred&truth).sum())
    precision=tp/max(1,tp+fp);recall=tp/max(1,tp+fn)
    return dict(tp=tp,fp=fp,fn=fn,precision=precision,recall=recall,f1=2*precision*recall/max(precision+recall,1e-12))

def choose_threshold(p,y):
    grid=[.15,.2,.25,.3,.35,.4,.45,.5]
    metrics={str(t):note_metrics(p,y,t) for t in grid}
    selected=max(grid,key=lambda t:(metrics[str(t)]['f1'],-abs(t-.3)))
    return selected,metrics

def main():
    if OUT.exists():raise FileExistsError(OUT)
    OUT.mkdir(parents=True);random.seed(20261105);np.random.seed(20261105);torch.manual_seed(20261105);torch.set_num_threads(4)
    batches={s:[] for s in ['train','validation','test']};targets={s:[] for s in batches};manifest=[]
    for path in sorted((ROOT/'GuitarSet/annotation').glob('*_comp.jams')):
        rid=path.stem
        if rid in KNOWN_TIMING:continue
        split=split_for(rid);npz=PRED/(rid+'_raw.npz');meta=json.loads(npz.with_suffix('.json').read_text());_,notes=load_reference(path)
        with np.load(npz) as d:
            idx=np.arange(0,len(d['times']),9);times=d['times'][idx];p=d['note'][idx,17:68].astype(np.float32)
        valid=(times>=.2)&(times<meta['duration_s']-.2);times=times[valid];p=p[valid];y=np.zeros_like(p)
        for note in notes:
            midi=round(note['midi'])
            if 38<=midi<=88:y[(times>=note['start'])&(times<note['end']),midi-38]=1
        batches[split].append(p);targets[split].append(y)
        manifest.append(dict(id=rid,split=split,pattern=rid.split('_')[1].split('-')[0],frames=len(times),
            prediction_sha256=hashlib.sha256(npz.read_bytes()).hexdigest(),annotation_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    x={s:np.concatenate(v) for s,v in batches.items()};y={s:np.concatenate(v) for s,v in targets.items()}
    sets={s:{r['pattern'] for r in manifest if r['split']==s} for s in batches}
    assert not sets['train']&sets['validation'] and not sets['train']&sets['test'] and not sets['validation']&sets['test']
    config=dict(seed=20261105,architecture='Frozen BasicPitch logits +51->32ReLU->51residual; input logits/8',
        parameter_count=3347,epochs_max=40,patience=6,optimizer='Adam lr0.001 weight_decay0.0001',
        loss='Unweighted BCEWithLogits +0.01mean_squared_residual',batch_size=512,
        split_patterns={s:sorted(v) for s,v in sets.items()},sample_stride_model_frames=9,
        threshold_selection='Validation-only global note-F1 over fixed0.15..0.50 grid; tie closest0.30',
        limitations='Base pretrained model used GuitarSet; this test holds out compositions only from new correction training. No independent pretrained-model claim.',
        training_sources=['GuitarSet mono mic and per-string note_midi'],not_trained_on=['IDMT','tutorial','chord labels'],
        source_sha256={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['audio_note_calibrator.py','train_audio_note_calibrator.py']})
    (OUT/'config.json').write_text(json.dumps(config,indent=2),encoding='utf-8');(OUT/'split_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    class Residual(nn.Module):
        def __init__(self):
            super().__init__();self.l1=nn.Linear(51,32);self.l2=nn.Linear(32,51);nn.init.zeros_(self.l2.weight);nn.init.zeros_(self.l2.bias)
        def forward(self,p):
            z=torch.logit(p.clamp(1e-4,1-1e-4));delta=self.l2(torch.relu(self.l1(z/8)));return z+delta,delta
    model=Residual();opt=torch.optim.Adam(model.parameters(),lr=.001,weight_decay=.0001);loss_fn=nn.BCEWithLogitsLoss()
    tx=torch.from_numpy(x['train']);ty=torch.from_numpy(y['train']);vx=torch.from_numpy(x['validation']);vy=torch.from_numpy(y['validation'])
    history=[];best=float('inf');best_state=None;stale=0
    for epoch in range(40):
        model.train();order=torch.randperm(len(tx));total=0.
        for indices in order.split(512):
            pred,delta=model(tx[indices]);loss=loss_fn(pred,ty[indices])+.01*delta.square().mean();opt.zero_grad();loss.backward();opt.step();total+=float(loss.detach())*len(indices)
        model.eval()
        with torch.no_grad():pred,_=model(vx);val=float(loss_fn(pred,vy))
        history.append(dict(epoch=epoch+1,train_loss=total/len(tx),validation_bce=val));print('epoch',epoch+1,'validation',round(val,6),flush=True)
        if val<best-1e-6:best=val;best_state={k:v.detach().clone() for k,v in model.state_dict().items()};stale=0
        else:stale+=1
        if stale>=6:break
    model.load_state_dict(best_state)
    weights=dict(w1=model.l1.weight.detach().numpy(),b1=model.l1.bias.detach().numpy(),w2=model.l2.weight.detach().numpy(),b2=model.l2.bias.detach().numpy())
    np.savez(OUT/'weights.npz',**weights)
    validation=corrected_probabilities(x['validation'],weights);base_t,base_sweep=choose_threshold(x['validation'],y['validation']);corrected_t,sweep=choose_threshold(validation,y['validation'])
    # Test is evaluated only after checkpoint and thresholds have been fixed above.
    result=dict(best_epoch=int(np.argmin([r['validation_bce'] for r in history]))+1,history=history,
        selected_thresholds=dict(baseline=base_t,corrected=corrected_t),validation_threshold_sweep=dict(baseline=base_sweep,corrected=sweep),splits={})
    for split in ['validation','test']:
        p=corrected_probabilities(x[split],weights)
        result['splits'][split]=dict(frames=len(p),baseline_default=note_metrics(x[split],y[split],.3),baseline_calibrated=note_metrics(x[split],y[split],base_t),
            corrected_default=note_metrics(p,y[split],.3),corrected_calibrated=note_metrics(p,y[split],corrected_t))
    result['weights_sha256']=hashlib.sha256((OUT/'weights.npz').read_bytes()).hexdigest()
    (OUT/'training_result.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result['splits']['test'],indent=2))

if __name__=='__main__':main()
