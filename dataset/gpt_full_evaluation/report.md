# GPT-6.1 Sol: remaining 11 images end-to-end

All calls explicitly approved. Same live candidate/corner/fret pipeline; no manual target coordinates supplied to the model.

{
  "images": 11,
  "successful": 11,
  "failed": 0,
  "mean_corner_error_px": 2.0055056431076745,
  "mean_iou_including_failures": 0.9182249592696846,
  "calls": 33,
  "input_tokens": 39107,
  "output_tokens": 22247,
  "total_tokens": 61354,
  "calls_without_usage": 0
}

| Image | Status | Corner px | IoU | Wires | Interpolated | Tokens |
|---|---|---:|---:|---:|---|---:|
| 1051_5603_0000.jpg | ok | 1.13 | 0.919 | 21 | - | 4,874 |
| 1051_5605_0000.jpg | ok | 0.81 | 0.951 | 21 | - | 5,115 |
| 1347539285769.jpg | ok | 1.16 | 0.968 | 21 | 2,3,4 | 6,024 |
| 1350562795380.jpg | ok | 1.36 | 0.876 | 21 | - | 4,939 |
| 2012032601357_0.jpg | ok | 2.63 | 0.896 | 21 | 8 | 6,221 |
| 2015111201921_0.jpg | ok | 1.44 | 0.956 | 20 | 3 | 4,296 |
| 201801031717219410_1.jpg | ok | 1.58 | 0.902 | 21 | 3,4 | 6,274 |
| escgE1715241981.jpg | ok | 5.82 | 0.887 | 23 | 4 | 6,632 |
| images.jpg | ok | 2.28 | 0.943 | 21 | - | 4,746 |
| images (2).jpg | ok | 1.70 | 0.880 | 20 | 2,3,4 | 5,653 |
| l_2014061102000525100136271.jpg | ok | 2.15 | 0.921 | 22 | 2 | 6,580 |

Corner accuracy is measured against the 4-point labels. No per-image fret-wire ground truth exists; wire counts and source classifications are model outputs, not certified fret accuracy.
Out-of-bounds wire endpoints and unresolved wires are retained in each evaluation JSON for review. No automatic paid retries.
The previously tested images (1).jpg is excluded; its earlier usage was 6,019 tokens.

## Review flags

- 1051_5605_0000.jpg: unresolved=[0, 20], outside=[]
- 1347539285769.jpg: unresolved=[0], outside=[]
- 2012032601357_0.jpg: unresolved=[17, 18, 19, 20], outside=[]
- escgE1715241981.jpg: unresolved=[], outside=[22]
- l_2014061102000525100136271.jpg: unresolved=[0], outside=[]

Unresolved endpoints are not extrapolated. A range violation is a review flag, not certified correct geometry. Successful execution does not mean every physical wire was detected.

## Combined with the previous single-image test

{
  "images": 12,
  "completed": 12,
  "calls": 36,
  "total_tokens": 67373,
  "mean_corner_error_px": 1.9589274972677233,
  "mean_iou": 0.9174907577804015
}
