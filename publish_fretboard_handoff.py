"""Publish dense frame identity/board fixtures for 3-12s, no API calls."""
import json
import subprocess
from pathlib import Path
import cv2
import numpy as np
from review_fretboard_clip import DEFAULT_OUT,make_board,write
from fretboard_frame_identity import make_frame_identity,sha256_file,assert_same_frame


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, default=DEFAULT_OUT)
    out=parser.parse_args().run
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
    video=Path(manifest['source_path']);source_id=sha256_file(video)
    assert source_id==manifest['source_id']
    pts=json.loads((out/'video_frame_pts.json').read_text(encoding='utf-8'))['frames']
    motion={r['frame_index']:r for r in json.loads((out/'motion_evidence.json').read_text(encoding='utf-8'))}
    selected={r['frame_index']:r for r in manifest['frames']}
    stream=json.loads(subprocess.run(['ffprobe','-v','error','-select_streams','v:0','-show_entries',
        'stream=time_base,start_pts,start_time,avg_frame_rate,nb_frames','-of','json',str(video)],capture_output=True,text=True,check=True).stdout)['streams'][0]
    time_base=stream['time_base']
    cap=cv2.VideoCapture(str(video));records=[]
    for i in range(max(motion)+1):
        ok,frame=cap.read()
        if not ok:raise RuntimeError('Dense decode failed')
        if i not in motion:continue
        case_id=f'clip003012_f{i:06d}'
        image=out/'frames'/f'{case_id}.png'
        if not image.exists():cv2.imwrite(str(image),frame)
        decoded=cv2.imread(str(image))
        if not np.array_equal(decoded,frame):raise ValueError('Existing PNG frame differs from source decode')
        identity=make_frame_identity(source_id,i,float(pts[i]['pts_time']),frame,image,case_id)
        identity.update(frame_pts=int(pts[i]['pts']),frame_time_base=time_base,
            frame_pts_s_basis='ffprobe original-stream pts_time, rounded to six decimals; ticks/time_base retained',
            legacy_index_over_fps_s=i/24.,opencv_pos_msec=cap.get(cv2.CAP_PROP_POS_MSEC))
        board_path=out/'frames'/f'{case_id}_board.json'
        if board_path.exists():
            board=json.loads(board_path.read_text(encoding='utf-8'))
            assert_same_frame(board,identity)
            board.update(identity);board['frame_identity']=identity;board['source_metadata']=identity
        else:
            r=motion[i]
            board=make_board(identity,np.asarray(r['affine']),r['evidence'],image.resolve())
        write(board_path,board)
        strings_path=out/'frames'/f'{case_id}_strings.json'
        if strings_path.exists():
            strings=json.loads(strings_path.read_text(encoding='utf-8'))
            assert_same_frame(strings,identity)
            strings.update(identity);strings['source_metadata']=identity
            write(strings_path,strings)
        records.append(dict(**identity,in_primary_interval=3<=identity['frame_pts_s']<12,
            board_json=str(board_path.resolve()),strings_json=str(strings_path.resolve()) if strings_path.exists() else None,
            strings_status='partial' if strings_path.exists() else 'not_analyzed',
            geometry_validity=board['geometry_validity'],
            exact_contact_fret_decision_allowed=False))
    cap.release()
    write(out/'frame_index_manifest.json',dict(source_id=source_id,interval=dict(start_s=3,end_s=12,end_exclusive=True),
        frames=records,primary_interval_frames=sum(r['in_primary_interval'] for r in records),
        boundary_audit_frames=sum(not r['in_primary_interval'] for r in records),stream_metadata=stream,
        decoded_pts_mapping='OpenCV display ordinal checked against FFmpeg select n, showinfo pts and explicit bt601 bilinear BGR conversion',api_calls=0))
    representative=[r for r in records if r['frame_index'] in selected]
    write(out/'same_frame_fixture.json',dict(source_id=source_id,frames=representative,
        dense_frame_index=str((out/'frame_index_manifest.json').resolve()),
        join_keys=['source_id','frame_index','frame_pts_s','frame_pixel_sha256'],
        pts_float_join_tolerance_s=5e-7,decoding='Use supplied PNG or OpenCV BGR; encoded file hash is separate',api_calls=0))
    manifest['frames']=[dict(selected[r['frame_index']],**{k:v for k,v in r.items() if k not in selected[r['frame_index']]}) for r in representative]
    manifest['dense_frame_index']=str((out/'frame_index_manifest.json').resolve())
    manifest['clock']=stream
    write(out/'manifest.json',manifest)
    print('Published',len(records),'frames; primary',sum(r['in_primary_interval'] for r in records),'representative string frames',len(representative))


if __name__=='__main__':main()
