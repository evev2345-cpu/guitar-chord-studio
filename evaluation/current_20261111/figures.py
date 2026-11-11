"""Diagnostic plots from observed audio, annotations and stored native outputs."""
import gzip
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]
RUN=Path(os.environ.get('GCS_EVAL_RUN',str(ROOT/'evaluation/runs/current_20261111_v1'))).resolve()
sys.path.insert(0,str(ROOT/'engine'))
from labels import load_reference


def main():
    import warnings
    import numpy as np
    from scipy.io import wavfile
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    manifest=json.loads((RUN/'manifest.json').read_text());directory=RUN/'figures';directory.mkdir(exist_ok=True)
    records={r['id']:r for r in manifest['records']}
    # Fixed documented suspect reference case; never used to alter scoring labels.
    r=records['ableton_live_guitar_Campfire']
    with warnings.catch_warnings():warnings.simplefilter('ignore');rate,raw=wavfile.read(r['audio'])
    x=raw.astype(float)/32768 if raw.dtype.kind=='i' else raw.astype(float)
    a=x[round(312.8*rate):round(313.2*rate)];spectrum=abs(np.fft.rfft(a*np.hanning(len(a))));f=np.fft.rfftfreq(len(a),1/rate)
    fig,ax=plt.subplots(1,2,figsize=(10,3.5));ax[0].plot(np.arange(len(a))/rate+312.8,a,lw=.5);ax[0].set_title('Observed audio: Campfire 313s');ax[0].set_xlabel('File time (seconds)');ax[0].set_ylabel('Original amplitude');ax[0].set_xticks([312.8,313.,313.2])
    ax[1].plot(f,20*np.log10(np.maximum(spectrum/spectrum.max(),1e-6)),color='#2b6f8d');ax[1].set_xlim(60,270);ax[1].set_ylim(-70,3);ax[1].set_xlabel('Hz');ax[1].set_ylabel('Relative dB');ax[1].set_title('Provided label D5; model notes E2/B2')
    for i,hz in enumerate([73.416,146.832,110.,220.]):ax[1].axvline(hz,color='#bd5353',alpha=.5,linestyle='--',label='D/A PC positions' if i==0 else None)
    for i,hz in enumerate([82.407,123.471,164.814,246.942]):ax[1].axvline(hz,color='#44885b',alpha=.45,label='E/B PC positions' if i==0 else None)
    ax[1].legend(fontsize=8);fig.tight_layout();fig.savefig(directory/'idmt_reference_uncertainty.png',dpi=150);plt.close(fig)
    wavfile.write(directory/'idmt_power_312_314.wav',rate,raw[round(312*rate):round(314*rate)])
    diagnosis=json.loads((RUN/'transition_diagnosis.json').read_text(encoding='utf-8'))
    candidates=[c for c in diagnosis['cases'] if c['mode']=='github' and c['dataset']=='guitarset' and c['layer']=='performed' and (c['confirmed_lookahead_interval_omission'] or c['confirmed_grid_interval_omission']) and not c['new_present']['B']]
    if not candidates:return
    case=sorted(candidates,key=lambda c:(c['id'],c['time_s']))[0];r=records[case['id']];start=max(0,case['time_s']-.75);end=case['end_s']+.5
    rows=[]
    with gzip.open(RUN/'github/dense'/(r['id']+'_0.2.jsonl.gz'),'rt',encoding='utf-8') as g:
        for line in g:
            row=json.loads(line)
            if start<=row['time_s']<end:rows.append(row)
    layers,_=load_reference(r['annotation']);events=[e for e in layers['performed'] if e['time']<end and e['time']+e['duration']>start]
    fig,axes=plt.subplots(5,1,figsize=(11,5),sharex=True)
    axes[0].set_ylabel('Reference',rotation=0,labelpad=42)
    for event in events:
        a=max(start,event['time']);b=min(end,event['time']+event['duration']);axes[0].barh(0,b-a,left=a,height=.65,color='#b8d0a5',edgecolor='white');axes[0].text((a+b)/2,0,event['value'],ha='center',va='center',fontsize=8)
    colors=['#bfd1e1','#d6c4dc','#e5d2b8','#b5d2c9']
    for axis,key,color in zip(axes[1:],['A','U_context','B_frame','B'],colors):
        labels=[' + '.join(c['symbol'] for c in row[key]) or 'hold' for row in rows];i=0
        while i<len(rows):
            j=i+1
            while j<len(rows) and labels[j]==labels[i]:j+=1
            a=rows[i]['time_s'];b=min(end,rows[j-1]['time_s']+1/24);axis.barh(0,b-a,left=a,height=.65,color=color,edgecolor='white')
            if b-a>.1:axis.text((a+b)/2,0,labels[i],ha='center',va='center',fontsize=7)
            i=j
        axis.set_ylabel(key,rotation=0,labelpad=42)
    for axis in axes:axis.set_yticks([]);axis.set_ylim(-.6,.6);axis.axvline(case['time_s'],color='#a74747',linestyle='--',linewidth=1)
    axes[-1].set_xlim(start,end);axes[-1].set_xlabel('File time (seconds)');axes[0].set_title('Native postprocessing omission: '+case['id'])
    fig.tight_layout();fig.savefig(directory/'observed_transition_omission.png',dpi=150);plt.close(fig)
    (directory/'omission_case.json').write_text(json.dumps(case,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Diagnostic figures and original two-second audio written:',directory)


if __name__=='__main__':main()
