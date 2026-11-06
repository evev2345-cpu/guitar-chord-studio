"""Build an offline, score-hidden listening/annotation package from a fresh run."""
import argparse
import csv
import hashlib
import json
import subprocess
from pathlib import Path
from audio_analysis import time_local_evidence, evaluate_onsets


def build(manifest):
    path=Path(manifest);root=path.parent;m=json.loads(path.read_text());e=json.loads((root/'evidence.json').read_text())
    if abs(m['start_s']-3)>1/m['sample_rate'] or abs(m['end_s']-12)>1/m['sample_rate']:
        raise ValueError('This review package currently supports only the shared 3–12 second interval')
    pts=json.loads(subprocess.check_output(['ffprobe','-v','error','-select_streams','v:0','-show_frames','-show_entries','frame=best_effort_timestamp_time,pts_time,pkt_duration_time','-of','json',m['source_path']],text=True))
    (root/'video_pts.json').write_text(json.dumps(pts,indent=2))
    origin=float(m['metadata']['format'].get('start_time',0))
    with (root/'pts_mapping.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['frame_index','frame_pts_s','source_video_s','frame_index_over_24_s','difference_s'])
        for i,frame in enumerate(pts['frames']):
            p=float(frame['best_effort_timestamp_time']);t=p-origin
            if 2.8<=t<=12.2:writer.writerow([i,p,t,i/24,t-i/24])
    # Trim against original timestamps; retain A/V offsets rather than separately zeroing streams.
    target=root/'review_score_hidden.mp4'
    cmd=['ffmpeg','-v','error','-i',m['source_path'],'-filter_complex',
         '[0:v]trim=start=3:end=12,crop=600:430:0:0,setpts=PTS-3/TB[v];[0:a]atrim=start=3:end=12,asetpts=PTS-3/TB[a]',
         '-map','[v]','-map','[a]','-c:v','libx264','-crf','20','-c:a','aac','-b:a','192k',str(target)]
    if not target.exists():subprocess.run(cmd,check=True)
    (root/'review_clip_provenance.json').write_text(json.dumps(dict(command=cmd,lossy_review_copy=True,
        analysis_audio='analysis.wav',original_channel_audio='original.wav',crop='x=0,y=0,w=600,h=430; screen score hidden',
        local_to_source_s=3.,applied_av_correction_s=0.),indent=2))
    folder=root/'fixtures';folder.mkdir(exist_ok=True)
    for a,b in [(5.05,5.35),(7.80,8.10),(8.75,9.05)]:
        fixture=time_local_evidence(e,a,b)
        (folder/f'audio_{a:.2f}_{b:.2f}.json').write_text(json.dumps(fixture,indent=2))
    template=dict(schema_version='audio_review.v1',source_id=m['source_id'],timebase=m['timebase'],start_s=3.,end_s=12.,
        reviewer=None,independent_review=False,listening_status='not_performed',instrument_mix='unknown',
        coverage_intervals=[],onsets=[],stable_windows=[],av_strokes=[],
        instructions='Listen before viewing model predictions. Source seconds = clip seconds + 3. Provide onset time_s/uncertainty_s, stable start_s/end_s and notes or unknown. Do not copy screen notation. Unknown is valid.')
    (root/'review_template.json').write_text(json.dumps(template,indent=2))
    html='''<!doctype html><meta charset="utf-8"><title>Audio review — score hidden</title>
<style>body{font:16px system-ui;max-width:1000px;margin:24px auto}video{width:100%}textarea{width:100%;height:400px}button{padding:10px;margin:5px}</style>
<h1>3–12s audio review</h1><p>Source time = local player time + 3 seconds. Review copy hides score/TAB. Do not infer notes from hand positions.</p>
<video id="v" controls src="review_score_hidden.mp4"></video><p id="clock"></p>
<p>Native stereo audio:</p><audio controls src="original.wav"></audio>
<p>Record reviewer, listening status, mixture, coverage intervals, onset time/uncertainty, and stable windows. Empty labels remain pending; silence is not mute.</p>
<button id="mark">Append current source time as unconfirmed onset</button><button id="save">Download labels</button>
<textarea id="labels"></textarea><script>
const template=__TEMPLATE__;labels.value=JSON.stringify(template,null,2);
v.ontimeupdate=()=>clock.textContent='Source '+(v.currentTime+3).toFixed(4)+' s';
mark.onclick=()=>{let r=JSON.parse(labels.value);r.onsets.push({time_s:v.currentTime+3,uncertainty_s:null,status:'unconfirmed'});labels.value=JSON.stringify(r,null,2)};
save.onclick=()=>{let a=document.createElement('a');a.href=URL.createObjectURL(new Blob([labels.value],{type:'application/json'}));a.download='audio_review.json';a.click();URL.revokeObjectURL(a.href)};
</script>'''.replace('__TEMPLATE__',json.dumps(template))
    (root/'review.html').write_text(html,encoding='utf-8')
    (root/'evaluation_pending.json').write_text(json.dumps({key:evaluate_onsets([o['time_s'] for o in e[key]],[],reviewed=False) for key in ['onsets','legacy_long_window_onsets']},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True)
    build(p.parse_args().manifest)
