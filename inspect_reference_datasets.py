"""Read-only local dataset audit and annotation example visualization; no downloads."""
import json
from collections import Counter
from pathlib import Path
import warnings
from scipy.io import wavfile
from joint_evidence_review import ROOT


def main():
    inventory={}
    for name in ['GuitarSet','EGDB_repo']:
        files=[p for p in (ROOT/name).rglob('*') if p.is_file() and '.git' not in p.parts]
        inventory[name]=dict(file_count=len(files),bytes=sum(p.stat().st_size for p in files),
            extensions=dict(Counter(p.suffix.lower() for p in files)),audio=[])
        for p in files:
            if p.suffix.lower()=='.wav':
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore');sr,x=wavfile.read(p,mmap=True)
                inventory[name]['audio'].append(dict(path=str(p),sample_rate=sr,shape=list(x.shape),duration_s=len(x)/sr))
    annotations=sorted((ROOT/'GuitarSet/annotation').glob('*.jams'))
    namespaces=Counter();notes=0;intended=Counter();performed=Counter();sources=Counter();performers=Counter();duration=0.;dual=0
    for p in annotations:
        data=json.loads(p.read_text(encoding='utf-8'));duration+=data['file_metadata']['duration'];performers[p.name.split('_')[0]]+=1
        chords=[]
        for a in data['annotations']:
            namespaces[a['namespace']]+=1
            if a['namespace']=='note_midi':notes+=len(a['data']);sources[a['annotation_metadata']['data_source']]+=1
            if a['namespace']=='chord':chords.append(a)
        if len(chords)>1:dual+=1
        for c in chords:
            target=performed if c['annotation_metadata'].get('data_source')=='Semi-automatic chord transcription with manual verification' else intended
            target.update(x['value'] for x in c['data'])
    inventory['GuitarSet']['annotations']=dict(jams_count=len(annotations),comp_count=sum('_comp' in p.name for p in annotations),
        solo_count=sum('_solo' in p.name for p in annotations),performer_files=dict(performers),duration_s=duration,
        namespaces=dict(namespaces),note_event_count=notes,string_source_counts=dict(sources),files_with_multiple_chord_layers=dual,
        nominal_chord_label_count=sum(intended.values()),performed_chord_label_count=sum(performed.values()),
        nominal_top_labels=intended.most_common(15),performed_top_labels=performed.most_common(15))
    folder=ROOT/'dataset/integration_review/runs/reference_dataset_audit_20261105_v1';folder.mkdir(parents=True,exist_ok=True)
    (folder/'inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    example=ROOT/'GuitarSet/annotation/00_BN1-129-Eb_comp.jams'
    data=json.loads(example.read_text());render(data,folder/'annotation_example.png')
    print(json.dumps({k:{x:y for x,y in v.items() if x!='audio'} for k,v in inventory.items()},indent=2))


def render(data,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(3,1,figsize=(15,8),gridspec_kw={'height_ratios':[3,1,1]},sharex=True)
    chords=[]
    for a in data['annotations']:
        if a['namespace']=='note_midi':
            string=int(a['annotation_metadata']['data_source'])
            for event in a['data']:
                if event['time']<12:axes[0].plot([event['time'],min(12,event['time']+event['duration'])],[event['value']]*2,lw=2,color=plt.cm.tab10(string))
        if a['namespace']=='chord':chords.append(a)
    axes[0].set(ylabel='Annotated MIDI pitch',title='Actual local annotation: '+data['file_metadata']['title'])
    for ax,annotation in zip(axes[1:],chords):
        for event in annotation['data']:
            if event['time']>=12:continue
            start=event['time'];end=min(12,start+event['duration'])
            ax.axvspan(start,end,alpha=.15,color='blue');ax.text((start+end)/2,.5,event['value'],ha='center',va='center',fontsize=9)
        detailed=bool(annotation['annotation_metadata'].get('data_source'))
        ax.set(yticks=[],ylabel='Performed label' if detailed else 'Nominal label',ylim=(0,1))
    axes[-1].set(xlim=(0,12),xlabel='Annotation seconds (audio absent locally)')
    fig.suptitle('Two chord reference layers must not be treated as interchangeable; no new transcription was inferred')
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(path,dpi=125);plt.close(fig)


if __name__=='__main__':main()
