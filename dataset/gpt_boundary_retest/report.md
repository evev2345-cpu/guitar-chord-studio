# GPT-6.1 Sol: remaining 11 images end-to-end

All calls explicitly approved. Same live candidate/corner/fret pipeline; no manual target coordinates supplied to the model.

{
  "images": 5,
  "successful": 5,
  "failed": 0,
  "mean_corner_error_px": 3.3374103784561155,
  "mean_iou_including_failures": 0.897270692998213,
  "calls": 15,
  "input_tokens": 21395,
  "output_tokens": 13139,
  "total_tokens": 34534,
  "calls_without_usage": 0
}

| Image | Status | Corner px | IoU | Wires | Interpolated | Tokens |
|---|---|---:|---:|---:|---|---:|
| 1051_5605_0000.jpg | ok | 3.76 | 0.912 | 22 | 2 | 5,735 |
| 1347539285769.jpg | ok | 0.75 | 0.924 | 23 | 2,3,4 | 7,648 |
| 2012032601357_0.jpg | ok | 1.82 | 0.935 | 22 | 7,8,16,17,18,19,20 | 7,472 |
| escgE1715241981.jpg | ok | 7.33 | 0.855 | 23 | 4 | 7,095 |
| l_2014061102000525100136271.jpg | ok | 3.02 | 0.861 | 23 | 2 | 6,584 |

Corner accuracy is measured against the 4-point labels. No per-image fret-wire ground truth exists; wire counts and source classifications are model outputs, not certified fret accuracy.
Out-of-bounds wire endpoints and unresolved wires are retained in each evaluation JSON for review. No automatic paid retries.
The previously tested images (1).jpg is excluded; its earlier usage was 6,019 tokens.