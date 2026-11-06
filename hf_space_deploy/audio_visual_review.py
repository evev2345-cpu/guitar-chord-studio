"""Reproducible PTS-based contact sheets with score region excluded."""
import argparse
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from scipy.io import wavfile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def render(manifest):
    root=Path(manifest).parent;m=json.loads(Path(manifest).read_text());frames=json.loads((root/'video_pts.json').read_text())['frames']
    sr,x=wavfile.read(root/'analysis.wav');cap=cv2.VideoCapture(m['source_path']);rows=[]
    origin=float(m['metadata']['format'].get('start_time',0))
    for j,center in enumerate([4.958333,7.666667,8.625]):
        idx=min(range(len(frames)),key=lambda i:abs(float(frames[i]['best_effort_timestamp_time'])-origin-center))
        fig,axes=plt.subplots(2,7,figsize=(21,5),gridspec_kw={'height_ratios':[2,1]})
        for col,i in enumerate(range(idx-3,idx+4)):
            cap.set(cv2.CAP_PROP_POS_FRAMES,i);ok,bgr=cap.read()
            if not ok:raise RuntimeError(f'Could not decode frame {i}')
            pts=float(frames[i]['best_effort_timestamp_time']);t=pts-origin
            image_path=root/f'av{j}_frame_{i}.png';cv2.imwrite(str(image_path),bgr[:430,:600])
            rows.append(dict(source_id=m['source_id'],frame_index=i,frame_pts_s=pts,source_video_s=t,
                frame_pixel_sha256=hashlib.sha256(bgr.tobytes()).hexdigest(),
                image_file_sha256=hashlib.sha256(image_path.read_bytes()).hexdigest(),
                image_path=image_path.name,image_crop=[0,0,600,430],pixel_hash_scope='full decoded BGR; file hash is cropped PNG'))
            axes[0,col].imshow(cv2.cvtColor(bgr[:430,:600],cv2.COLOR_BGR2RGB));axes[0,col].set_title(f'index {i}: PTS {pts:.6f}');axes[0,col].axis('off')
            a=max(0,round((t-.04-m['start_s'])*sr));b=min(len(x),round((t+.12-m['start_s'])*sr))
            axes[1,col].plot(m['start_s']+np.arange(a,b)/sr,x[a:b],lw=.4);axes[1,col].axvline(t,c='r');axes[1,col].set_ylim(-.6,.6);axes[1,col].tick_params(axis='x',labelrotation=60)
        fig.tight_layout();fig.savefig(root/f'av_stroke_{j}.jpg');plt.close(fig)
    cap.release();(root/'av_frame_identity.json').write_text(json.dumps(rows,indent=2))
    fig,axes=plt.subplots(3,1,figsize=(14,8))
    for ax,(lo,hi) in zip(axes,[(5.05,5.35),(7.8,8.1),(8.75,9.05)]):
        y=x[round((lo-m['start_s'])*sr):round((hi-m['start_s'])*sr)]
        mag=np.abs(np.fft.rfft(y*np.hanning(len(y))));freq=np.fft.rfftfreq(len(y),1/sr)
        ax.plot(freq,20*np.log10(np.maximum(mag,1e-8)));ax.set_xlim(65,1600);ax.grid();ax.set_title(f'{lo:.2f}–{hi:.2f}: review target, not validated notes')
    fig.tight_layout();fig.savefig(root/'local_spectra.png');plt.close(fig)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);render(p.parse_args().manifest)
