"""Derive output times from input-window sample positions, never reference labels."""
import numpy as np

def window_output_times(window_index,n_frames,*,rate=22050,fft_hop=256,input_samples=43844,overlap_frames=30):
    trim=overlap_frames//2
    if overlap_frames%2 or n_frames<=2*trim or window_index<0:raise ValueError('Invalid model window')
    input_hop=input_samples-overlap_frames*fft_hop
    positions=window_index*input_hop+np.arange(trim,n_frames-trim)*fft_hop-trim*fft_hop
    return positions/rate
