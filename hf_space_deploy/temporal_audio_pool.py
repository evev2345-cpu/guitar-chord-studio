"""Fixed short-window pooling of pretrained audio activations. No labels used."""
import numpy as np
from audio_note_calibrator import probabilities_to_chroma

WIDTHS=[.1,.2,.4,.8]
VARIANTS=['instant']+[f'{method}_{width:.1f}s' for method in ['max','mean'] for width in WIDTHS]

def pooled_chroma(frame_times,note_frames,query_times,width=0.,method='max'):
    grid=np.asarray(frame_times,float);values=np.asarray(note_frames,float);query=np.asarray(query_times,float)
    if values.shape!=(len(grid),88) or not len(grid) or not np.isfinite(values).all() or np.any(np.diff(grid)<=0):raise ValueError('Invalid model grid')
    if not np.isfinite(grid).all() or not np.isfinite(query).all() or width<0 or not np.isfinite(width) or method not in ('max','mean'):raise ValueError('Invalid pooling')
    rows=[]
    for t in query:
        if width==0:
            i=int(np.argmin(abs(grid-t)))
            if abs(grid[i]-t)>.03:raise ValueError('Query outside model support')
            row=values[i,17:68]
        else:
            if t-width/2<grid[0] or t+width/2>grid[-1]:raise ValueError('Incomplete time window')
            a=np.searchsorted(grid,t-width/2,side='left');b=np.searchsorted(grid,t+width/2,side='left')
            if a>=b:raise ValueError('Empty window')
            row=getattr(np,method)(values[a:b,17:68],axis=0)
        rows.append(row)
    return probabilities_to_chroma(np.array(rows).reshape(-1,51),.3)

def all_variants(grid,frames,query):
    result=dict(instant=pooled_chroma(grid,frames,query))
    for method in ['max','mean']:
        for width in WIDTHS:result[f'{method}_{width:.1f}s']=pooled_chroma(grid,frames,query,width,method)
    return result
