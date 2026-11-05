# YOLO retraining comparison

Same 12 original images; imgsz=640, conf=0.25, CPU, highest box confidence.

| Metric | Original | Corrected |
|---|---:|---:|
| detected | 9 | 9 |
| mean_iou | 0.05764609145303768 | 0.05357652028667551 |
| mean_corner_error_px | 68.16275999281142 | 45.88046561347114 |
| mean_error_width_pct | 212.99325137668185 | 148.9666002061632 |
| pck_20pct_width | 0.0 | 0.0 |

Training early-stopped after 78 epochs (maximum 120; patience 40). Best validation checkpoint used.
The original split is retained: 9 training sources and 3 validation sources. Both models miss all three validation images at confidence 0.25.
Lower corner error does not imply successful extraction: mean polygon IoU slightly decreased and crossing corners remain.
These are train/model-selection validation results, not independent test performance. Several settings changed together; causal attribution requires ablation.

| Image | Split | Old mean px | New mean px | Old IoU | New IoU |
|---|---|---:|---:|---:|---:|
| 1051_5603_0000.jpg | val | - | - | 0.000 | 0.000 |
| 1051_5605_0000.jpg | train | 34.367 | 22.370 | 0.000 | 0.000 |
| 1347539285769.jpg | train | 33.007 | 23.602 | 0.000 | 0.000 |
| 1350562795380.jpg | train | 16.053 | 16.909 | 0.146 | 0.322 |
| 2012032601357_0.jpg | train | 64.174 | 63.776 | 0.000 | 0.000 |
| 2015111201921_0.jpg | val | - | - | 0.000 | 0.000 |
| 201801031717219410_1.jpg | train | 57.456 | 39.260 | 0.130 | 0.119 |
| escgE1715241981.jpg | train | 193.514 | 111.914 | 0.064 | 0.000 |
| images (1).jpg | train | 43.922 | 34.304 | 0.257 | 0.000 |
| images (2).jpg | train | 56.484 | 24.625 | 0.000 | 0.202 |
| images.jpg | val | - | - | 0.000 | 0.000 |
| l_2014061102000525100136271.jpg | train | 114.489 | 76.165 | 0.095 | 0.000 |