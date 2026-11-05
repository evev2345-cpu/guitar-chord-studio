# Boundary handling: same five images retest

## Results

```json
{
  "summary": {
    "images": 5,
    "old_unresolved": 8,
    "new_unresolved": 0,
    "old_outside": 1,
    "new_outside": 0,
    "boundary_estimated": 7,
    "adjusted": 1,
    "old_mean_iou": 0.9246673647400614,
    "new_mean_iou": 0.897270692998213,
    "old_corner_error_px": 2.514273798465729,
    "new_corner_error_px": 3.3374103784561155
  },
  "usage": {
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
}
```

| Image | Previous unresolved | Previous outside | Boundary estimates | Small clips | New unresolved/outside | Old last / new last |
|---|---|---|---|---|---|---|
| 1051_5605_0000.jpg | [0, 20] | [] | [21] | [] | [] / [] | 20 / 21 |
| 1347539285769.jpg | [0] | [] | [0, 22] | [] | [] / [] | 20 / 22 |
| 2012032601357_0.jpg | [17, 18, 19, 20] | [] | [21] | [] | [] / [] | 20 / 21 |
| escgE1715241981.jpg | [] | [22] | [22] | [0] | [] / [] | 22 / 22 |
| l_2014061102000525100136271.jpg | [0] | [] | [0, 22] | [] | [] / [] | 21 / 22 |

## Interpretation

Magenta lines are boundary estimates, cyan lines are internal interpolation, green lines are observed wires. Small clipped observations retain original_endpoints and geometry_adjustment metadata.
Nut recovery uses the semantic stage-1 nut corners. Terminal-number recovery requires at least six observed wires, a projective fit of 12-TET positions, low residual, monotonic positions, agreement at both edges and agreement with last_fret_num when supplied. Inconclusive cases remain unresolved.
Small out-of-board extrapolations <=0.5% of board width are clipped with original endpoints retained. Larger excursions are rejected from geometry and may only be filled with explicit estimates between valid anchors.
Old cached responses also resolve all old unresolved records after the geometry change; these were replayed without API charges.
Fresh endpoint counts changed in some images. No fret-wire ground truth exists, so these are model/geometry estimates, not certified physical numbering. Endpoint crop quality affects every boundary estimate.
Fresh corner IoU slightly declined compared with the same five old runs; the corner detector itself was not improved by this boundary change. This is not a claim of improved corner accuracy.
15 fresh requests, no automatic retries. Original results retained under dataset/gpt_full_evaluation.