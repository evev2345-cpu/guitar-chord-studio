"""Verify the official microphone archive, safely unpack, and index label pairs."""
import hashlib
import json
from pathlib import Path
import zipfile
from scipy.io import wavfile
from joint_evidence_review import ROOT

EXPECTED_MD5='275966d6610ac34999b58426beb119c3'


def main():
    archive=ROOT/'GuitarSet/audio_mono-mic.zip';dest=ROOT/'GuitarSet/audio_mono-mic'
    out=ROOT/'dataset/integration_review/runs/guitarset_audio_ready_20261105_v1'
    if (out/'manifest.json').exists():raise FileExistsError(out)
    md5=hashlib.md5();sha=hashlib.sha256()
    with archive.open('rb') as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b''):md5.update(chunk);sha.update(chunk)
    if md5.hexdigest()!=EXPECTED_MD5:raise ValueError('Official archive checksum mismatch')
    if dest.exists():raise FileExistsError('Use an absent extraction folder')
    with zipfile.ZipFile(archive) as zipped:
        members=zipped.infolist();seen=set()
        for item in members:
            name=item.filename
            if Path(name).name!=name or not name.endswith('_mic.wav') or name.lower() in seen:raise ValueError('Unexpected ZIP path or duplicate')
            if (item.external_attr>>16)&0o170000==0o120000:raise ValueError('ZIP symlink rejected')
            seen.add(name.lower())
        bad=zipped.testzip()
        if bad is not None:raise ValueError('Archive CRC failure: '+bad)
        dest.mkdir()
        zipped.extractall(dest)
    rows=[];annotations={p.stem:p for p in (ROOT/'GuitarSet/annotation').glob('*.jams')}
    for path in sorted(dest.glob('*.wav')):
        key=path.name.removesuffix('_mic.wav')
        if key not in annotations:raise ValueError('Unmatched audio: '+key)
        annotation=annotations[key];data=json.loads(annotation.read_text(encoding='utf-8'))
        rate,samples=wavfile.read(path,mmap=True)
        note_tracks=[a for a in data['annotations'] if a['namespace']=='note_midi']
        sources=[a['annotation_metadata'].get('data_source') for a in note_tracks]
        if sorted(sources)!=list('012345'):raise ValueError('Missing or duplicate string labels')
        chords=[a for a in data['annotations'] if a['namespace']=='chord']
        nominal=[a for a in chords if not a['annotation_metadata'].get('data_source')]
        performed=[a for a in chords if a['annotation_metadata'].get('data_source')=='Semi-automatic chord transcription with manual verification']
        notes=[event for a in note_tracks for event in a['data']]
        duration=len(samples)/rate
        outside=[event for event in notes if event['time']<0 or event['duration']<=0 or event['time']+event['duration']>duration+.02]
        rows.append(dict(recording_id=key,audio_file=str(path),annotation_file=str(annotation),sample_rate=rate,
            channels=1 if samples.ndim==1 else samples.shape[1],sample_count=len(samples),dtype=str(samples.dtype),duration_s=duration,
            annotation_duration_s=data['file_metadata']['duration'],duration_delta_s=duration-data['file_metadata']['duration'],
            audio_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),annotation_sha256=hashlib.sha256(annotation.read_bytes()).hexdigest(),
            style=key.split('_')[1],performer_id=key.split('_')[0],performance='comp' if key.endswith('_comp') else 'solo',
            note_count=len(notes),nominal_chord_annotation_count=len(nominal),performed_chord_annotation_count=len(performed),
            temporal_note_anomaly_count=len(outside),temporal_note_anomaly_examples=outside[:3]))
    matched={r['recording_id'] for r in rows};missing=sorted(set(annotations)-matched)
    if missing:raise ValueError('Annotations missing audio: '+str(missing))
    out.mkdir(parents=True,exist_ok=True)
    result=dict(archive=str(archive),archive_md5=md5.hexdigest(),official_md5_match=True,archive_sha256=sha.hexdigest(),
                zip_crc_valid=True,audio_dir=str(dest),audio_count=len(rows),annotation_count=len(annotations),
                comp_count=sum(r['performance']=='comp' for r in rows),solo_count=sum(r['performance']=='solo' for r in rows),
                duration_s=sum(r['duration_s'] for r in rows),unmatched_annotations=missing,
                duration_mismatch_over_20ms=[r['recording_id'] for r in rows if abs(r['duration_delta_s'])>.02],
                note_temporal_anomaly_files=[r['recording_id'] for r in rows if r['temporal_note_anomaly_count']],
                evaluation_started=False,rows=rows)
    (out/'manifest.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    render(rows[0],out/'paired_example.png')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'},indent=2))


def render(record,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    rate,x=wavfile.read(record['audio_file']);data=json.loads(Path(record['annotation_file']).read_text())
    fig,axes=plt.subplots(4,1,figsize=(15,10),sharex=True,gridspec_kw={'height_ratios':[2,3,1,1]})
    axes[0].plot(np.arange(min(len(x),rate*12))/rate,x[:rate*12],lw=.4);axes[0].set_ylabel('Mic PCM')
    chords=[]
    for a in data['annotations']:
        if a['namespace']=='note_midi':
            for event in a['data']:
                if event['time']<12:axes[1].plot([event['time'],min(12,event['time']+event['duration'])],[event['value']]*2,lw=2)
        elif a['namespace']=='chord':chords.append(a)
    axes[1].set_ylabel('Reference MIDI')
    for ax,a in zip(axes[2:],chords):
        for event in a['data']:
            if event['time']<12:
                left=event['time'];right=min(12,left+event['duration'])
                ax.axvspan(left,right,alpha=.15,color='blue');ax.text((left+right)/2,.5,event['value'],ha='center',va='center',fontsize=9)
        ax.set(yticks=[],ylim=(0,1),ylabel='Performed' if a['annotation_metadata'].get('data_source') else 'Nominal')
    axes[-1].set(xlim=(0,12),xlabel='Recording seconds; file pairing is not independent timing verification')
    fig.suptitle(record['recording_id']+' | downloaded microphone audio + both original chord layers')
    fig.tight_layout(rect=[0,0,1,.96]);fig.savefig(path,dpi=125);plt.close(fig)


if __name__=='__main__':main()
