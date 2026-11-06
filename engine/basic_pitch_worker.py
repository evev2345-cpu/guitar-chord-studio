"""Isolated Basic Pitch ONNX inference. Run using .venv-audio-model Python.

Official model/preprocessing/decoding are used with an explicit sample-position
clock to avoid the package0.4.0 output timing drift. No labels are read.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import tempfile
import time
import logging
logging.getLogger().setLevel(logging.ERROR)
import numpy as np
import onnxruntime as ort
from scipy.io import wavfile
from basic_pitch import build_icassp_2022_model_path,FilenameSuffix
from basic_pitch.inference import Model,get_audio_input
from basic_pitch.constants import AUDIO_N_SAMPLES,FFT_HOP,AUDIO_SAMPLE_RATE
from basic_pitch.note_creation import output_to_notes_polyphonic,note_events_to_midi
from basic_pitch_clock import window_output_times

LOW=440*2**((38-69)/12);HIGH=440*2**((88-69)/12)

def cut_pcm(x,rate):
    freq=np.fft.rfftfreq(len(x),1/rate);spec=np.fft.rfft(x);spec[(freq<LOW)|(freq>HIGH)]=0
    return np.fft.irfft(spec,n=len(x))

def main():
    p=argparse.ArgumentParser();p.add_argument('--tasks',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--modes',nargs='+',choices=['raw','cut'],default=['raw','cut']);a=p.parse_args()
    out=a.output;out.mkdir(parents=True,exist_ok=True)
    path=build_icassp_2022_model_path(FilenameSuffix.onnx);options=ort.SessionOptions();options.intra_op_num_threads=4;options.inter_op_num_threads=1
    model=Model.__new__(Model);model.model_type=Model.MODEL_TYPES.ONNX
    model.model=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
    provenance=dict(model=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),size_bytes=path.stat().st_size,
        basic_pitch=importlib.metadata.version('basic-pitch'),runtime=importlib.metadata.version('onnxruntime'),providers=model.model.get_providers(),
        threads=4,frame_threshold=.3,onset_threshold=.5,min_note_len_frames=11,pitch_bends=False,
        timestamp='v2 input-window sample clock, trim15outputframes each side; no fitted offset; avoids0.4.0 duration truncation/drift',trained_here=False,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    manifest=out/'model.json'
    if manifest.exists() and json.loads(manifest.read_text())!=provenance:raise ValueError('Inference configuration changed')
    manifest.write_text(json.dumps(provenance,indent=2),encoding='utf-8')
    tasks=json.loads(a.tasks.read_text())
    for task in tasks:
        for mode in a.modes:
            dest=out/(task['id']+'_'+mode+'.npz');meta=dest.with_suffix('.json')
            audio=Path(task['audio']);sha=hashlib.sha256(audio.read_bytes()).hexdigest()
            if dest.exists():
                old=json.loads(meta.read_text())
                if old['source_sha256']!=sha:raise ValueError('Source changed')
                continue
            started=time.perf_counter();rate,pcm=wavfile.read(audio)
            if np.issubdtype(pcm.dtype,np.signedinteger):x=pcm.astype(float)/2**(np.iinfo(pcm.dtype).bits-1)
            else:x=pcm.astype(float)
            if x.ndim==2:x=x.mean(axis=1)
            if mode=='cut':x=cut_pcm(x,rate)
            with tempfile.TemporaryDirectory(prefix='basic_pitch_') as tmp:
                temp=Path(tmp)/'input.wav';wavfile.write(temp,rate,x.astype(np.float32))
                predictions={k:[] for k in ['note','onset','contour']};clock=[]
                overlap=30;trim=overlap//2  # official0.4.0 run_inference overlap
                for index,(window,_,original_length) in enumerate(get_audio_input(temp,overlap*FFT_HOP,AUDIO_N_SAMPLES-overlap*FFT_HOP)):
                    result=model.predict(window);count=result['note'].shape[1]
                    clock.extend(window_output_times(index,count,rate=AUDIO_SAMPLE_RATE,fft_hop=FFT_HOP,input_samples=AUDIO_N_SAMPLES,overlap_frames=overlap))
                    for k in predictions:predictions[k].append(result[k][0,trim:-trim])
                times=np.array(clock);valid=(times>=0)&(times<original_length/AUDIO_SAMPLE_RATE)
                times=times[valid];prediction={k:np.concatenate(v)[valid] for k,v in predictions.items()}
            indexed=output_to_notes_polyphonic(prediction['note'],prediction['onset'],onset_thresh=.5,frame_thresh=.3,min_note_len=11,
                min_freq=LOW,max_freq=HIGH,infer_onsets=True,melodia_trick=True)
            events=[(float(times[e[0]]),float(times[e[1]]),int(e[2]),float(e[3]),None) for e in indexed]
            midi=note_events_to_midi(events,False,120)
            midi.write(str(dest.with_suffix('.mid')))
            np.savez_compressed(dest,times=times,**prediction)
            metadata=dict(id=task['id'],mode=mode,audio=str(audio),source_sha256=sha,rate=rate,duration_s=len(x)/rate,
                          elapsed_s=time.perf_counter()-started,shape=list(prediction['note'].shape),
                          note_events=[dict(start_s=float(e[0]),end_s=float(e[1]),midi=int(e[2]),amplitude=float(e[3])) for e in events])
            meta.write_text(json.dumps(metadata,indent=2),encoding='utf-8')
            print(task['id'],mode,round(metadata['elapsed_s'],2),'seconds',flush=True)

if __name__=='__main__':main()
