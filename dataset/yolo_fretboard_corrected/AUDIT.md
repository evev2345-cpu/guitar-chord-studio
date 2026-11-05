# Keypoint and augmentation audit

The 12 JSON labels agree with the declared order: nut_top, body_top, body_bottom, nut_bottom. The old converter relied on array position; the corrected converter explicitly indexes by name.

The installed Ultralytics RandomFlip implementation mirrors coordinates and then applies flip_idx to keypoint indices. The old mapping [3,2,1,0] swaps low-E and high-E identities. Since these labels describe physical string sides rather than screen top/bottom, mirroring the image does not change their identities. The corrected mapping is [0,1,2,3]. Flips are disabled in this training run to avoid mirror ambiguity.

cv2.convertScaleAbs takes absolute values, so alpha=0.7, beta=-20 brightened values below zero. The corrected dark augmentation uses float arithmetic and clipping.

The corrected dataset preserves the original 9/3 source-image split and 27/3 augmented-image counts. Exact normalized label matching verifies all 12 sources belong exclusively to their expected split. The original data and weights are retained.

Training starts from the same local yolov8n-pose.pt, CPU, imgsz=640, batch=4. Changes include 120 maximum epochs, no mosaic/mixup/flips, small rotation (10 degrees), reduced translation (0.05) and scale jitter (0.15), seed 0. Several changes are bundled; this is not a controlled ablation attributing improvement to one change.

Evaluation uses the original full images, confidence threshold 0.25, highest-confidence detection, same physical keypoint order, polygon IoU (invalid quadrilaterals receive zero), and per-corner Euclidean errors. Mean pixel error excludes missed detections. PCK uses 20% of the manually labeled mean board width; misses count as zero. These 12 images include training and model-selection validation data, not an independent test set.
