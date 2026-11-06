"""Sample-accurate local audio extraction; no network access."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path
import numpy as np
from scipy.io import wavfile


def command(args):
    return subprocess.check_output(args, text=True, encoding='utf-8')


def decoded_timeline(frames, rate, format_start=0.):
    """Map raw PCM sample indices to original PTS, retaining timestamp gaps."""
    segments=[]; count=0
    for frame in frames:
        t=float(frame['best_effort_timestamp_time'])-format_start
        offset=t-count/rate
        if not segments or abs(offset-segments[-1]['offset_s'])>2/rate:
            if segments: segments[-1]['end_sample']=count
            segments.append(dict(first_sample=count,end_sample=None,offset_s=offset,first_source_s=t))
        count+=int(frame['nb_samples'])
    if not segments: raise ValueError('No decoded audio frames')
    segments[-1]['end_sample']=count
    return segments,count


def sample_interval(segments,start,end,rate):
    for seg in segments:
        lo=seg['first_sample']/rate+seg['offset_s'];hi=seg['end_sample']/rate+seg['offset_s']
        if lo<=start<end<=hi:
            return round((start-seg['offset_s'])*rate),round((end-seg['offset_s'])*rate),seg['offset_s']
    raise ValueError('Clip crosses an audio PTS discontinuity or exceeds decoded timeline')


def extract(video, start, end, output):
    video = Path(video).resolve(strict=True)
    if not 0 <= start < end:
        raise ValueError('Require 0 <= start < end')
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists():
        raise FileExistsError('Choose a new output directory')
    probe = json.loads(command(['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(video)]))
    stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
    rate, channels = int(stream['sample_rate']), int(stream['channels'])
    # FFmpeg decodes AAC skip_samples/priming; do not apply a second delay correction.
    initial_origin = float(stream.get('start_time', 0)) - float(probe['format'].get('start_time', 0))
    frame_probe = json.loads(command(['ffprobe','-v','error','-select_streams','a:0',
        '-show_frames','-show_entries','frame=best_effort_timestamp_time,nb_samples','-of','json',str(video)]))
    segments, expected_samples = decoded_timeline(frame_probe['frames'],rate,float(probe['format'].get('start_time',0)))
    first,last,origin = sample_interval(segments,start,end,rate)

    if first < 0:
        raise ValueError('Requested start precedes decoded audio origin')
    with tempfile.TemporaryDirectory() as temp:
        raw = Path(temp) / 'decoded.f32'
        cmd = ['ffmpeg', '-v', 'error', '-i', str(video), '-map', f"0:{stream['index']}", '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', str(raw)]
        subprocess.run(cmd, check=True)
        samples = np.fromfile(raw, dtype='<f4').reshape(-1, channels)
        if last > len(samples):
            raise ValueError('Requested end exceeds decoded audio')
        if len(samples) != expected_samples:
            raise ValueError('Probe frame sample count differs from raw decoder output')
        clip = samples[first:last].copy()
        decoded_count = len(samples)
    wavfile.write(output / 'original.wav', rate, clip)
    mono = clip.mean(axis=1)
    wavfile.write(output / 'analysis.wav', rate, mono.astype(np.float32))
    digest = hashlib.sha256()
    with video.open('rb') as f:
        for block in iter(lambda: f.read(1024*1024), b''):
            digest.update(block)
    channel_rms = np.sqrt(np.mean(clip.astype(float)**2, axis=0))
    manifest = dict(schema_version='guitar_evidence.v1', run_id=output.name, source_id=digest.hexdigest(), source_path=str(video), start_s=origin+first/rate, end_s=origin+last/rate, timebase='source_video_seconds', metadata=probe, sample_rate=rate, channels=channels, decoded_sample_count=decoded_count, clip_first_sample=first, clip_end_sample=last, decoded_origin_video_s=initial_origin, decoded_sample_mapping_offset_s=origin, decoded_timeline=segments, audio_frame_probe=frame_probe, local_to_source_offset_s=origin+first/rate, extraction_command=cmd, versions={x:command([x,'-version']).splitlines()[0] for x in ['ffmpeg','ffprobe']}, files={'original':'original.wav','analysis':'analysis.wav'}, processing={'resampling':False,'mono':'arithmetic channel mean','channel_rms':channel_rms.tolist(),'mono_rms':float(np.sqrt(np.mean(mono.astype(float)**2))), 'cancellation_rms_ratio':float(np.sqrt(np.mean(mono.astype(float)**2))/max(np.mean(channel_rms),1e-12)), 'priming':'FFmpeg decoder applies AAC skip_samples; no additional correction', 'timestamp_assumption':'Per decoded audio frame PTS maps cumulative raw PCM sample indices; clips crossing a PTS gap are rejected. Visual synchronization remains unverified'}, tuning=None, capo=None, assumptions=['Tuning and capo unverified acoustically'], limitations=['Container timestamps do not establish visual/acoustic synchronization'])
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    return manifest


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--video',required=True)
    p.add_argument('--start',type=float,default=3)
    p.add_argument('--end',type=float,default=12)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    extract(a.video,a.start,a.end,a.output)
