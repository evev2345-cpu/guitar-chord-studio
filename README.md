# Guitar fretboard pipeline

소스·문서와 일부 검수 그림을 보관하는 개발 저장소입니다. 데이터셋·원본 미디어·모델·비밀키는 제외합니다. 새 PC에서의 실행 준비와 제외 범위는 [저장소 구성 안내](docs/REPOSITORY_SETUP.md)를 참고하세요.

## Chord Studio 로컬 웹앱

`python chord_web_server.py --open`으로 실행하고 [로컬 웹앱](http://127.0.0.1:8765)을 엽니다. 파일 업로드·기존 오디오 모델 분석·재생 동기화 코드 후보·동점 표시·카포 전환·시간축 탐색·JSON 내보내기를 제공합니다. [사용법과 현재 범위](webapp/README.md)를 참고하세요. 타브와 크롬 확장은 다음 단계입니다.

보고서는 [사진 첨부 규칙](docs/REPORTING_GUIDELINES.md)에 따라 원본과 분석 비교 사진을 함께 기록합니다. [확대 손 신뢰도·가장자리 현 최신 보고서](docs/ROBUST_CANDIDATES_2026-11-03.md)를 참고하세요.

## Same-frame strings, quality gates and short continuous review

[Latest integration report](dataset/chord_sequence_review/report.md) verifies
the current variable-count string-owner schema, including null physical string
numbers, support intervals and unresolved identities. `string_interface` validates
decoded BGR pixel SHA-256, image size, common canvas and homographies for new
results. Legacy path-only results are explicitly identified as less verified.

`validate_chord_sequence.py` reuses the string owner's functions and cached
manual board fixtures, runs fresh full-frame and ROI hand observations and emits
same-frame string/hand/fret overlays. `hand_quality.py` withholds location decisions
on absent/ambiguous secondary views, >6px disagreement, >180px/s raw landmark
motion or large wrist discontinuities. These are preliminary heuristics, not
calibrated visibility or contact confidence. Raw candidates and unassigned mass
remain available; no averaging silently repairs an incorrect center.

The frozen C#m7 error is in `dataset/regression/csharp_m7_wrong_center.json`.
The 216.208–218.208s sequence contains 49 fresh IMAGE-mode observations; no
coordinates are carried forward when selection fails. Geometry remains a manual
reference and is marked unvalidated per frame, so all sequence fret decisions are
withheld. Persistent IDs and smoothing are not claimed.

[Model-blind manual review tool](dataset/chord_sequence_review/independent_review.html)
prepares 126 annotation items. Independent human points remain **0** until reviewed
JSON is supplied; existing agent provisional points are not independent ground
truth. New source outputs distinguish manual approximation from automatic detections.

```powershell
python validate_chord_sequence.py --sequence
python summarize_chord_sequence.py
python build_blind_hand_review.py
python -m unittest test_hand_quality test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector -v
```

## Chord analyzer milestone: tutorial still-frame review

The user's video under `sample video/` supplies open/barre tutorial scenes with
chord/TAB references. See [review report](dataset/chord_photo_validation/report.md).
No video tracking or API calls are used. New per-frame manual board fixtures live
under `dataset/chord_video_review`; existing unrelated photo caches stay intact.
These approximate fixtures are agent-reviewed inputs, not independently measured
board ground truth. Source video is not copied or uploaded.

`chord_photo_validation.py` consumes saved hand JSON, preserves all hands and thumb,
emits per-finger multi-fret distributions and explicit unassigned mass, and exports
index MCP/PIP/DIP/TIP phalange segments with sampled spatial candidates. All contact
states remain unknown. Radius sensitivity is 3/6/9/12 original pixels plus an
experimental label-error-derived radius when reviewed labels are supplied.
Two frames currently have provisional agent visual point labels; independent human
review and held-out coverage calibration are still required. Tutorial chord names
are references, not automatic predictions or synchronized contact labels. Capo-relative
and physical fret numbers are separate.

Existing `string_detector.py` is the only string detector. Optional `--strings-json`
accepts its saved result, verifies the same `input_geometry` and canvas and retains
observed/estimated evidence. Missing results remain `not_provided`; no uniform
six-band substitute is used. See the review report for reproducible commands.

```powershell
python -m unittest test_chord_photo_validation test_fingertip_probability test_hand_fret_tracker test_fret_geometry test_baze_client test_string_detector -v
```

## Fingertip circle and probability ellipse (offline)

```powershell
python fingertip_probability.py --tracking-json dataset/hand_tracking_comparison/1051_5605_0000_boundary.json --radius 6 --out-prefix sample_images/fingertip_probability/1051_5605
```

Uses saved landmarks and M, without API calls or new hand inference. Original circle:
`(x-cx)^2+(y-cy)^2=r^2`. The configurable radius (default 6 original pixels)
is assumed to enclose 95% of an isotropic 2D Gaussian: `sigma=r/sqrt(-2 ln .05)`.
It is a visualization/uncertainty parameter, not a measured finger-pad radius or
calibrated detector confidence. Contact probability is not estimated.

The exact transformed conic is `Cflat=M_inv.T @ Ccircle @ M_inv`.
Disks crossing the projective horizon are rejected rather than drawn as ellipses.
The probability approximation uses local Jacobian `Sigma_flat=J Sigma_original J.T`
and `mu_flat=H(mu_original)`. Its 95% contour is an ellipse; it can differ from the
exact transformed circle when perspective varies over the disk. Colored solid
outlines show the exact circle transform; thin white contours show the local
Gaussian 95% ellipse. Colored intensity represents density relative to each
finger's own peak, not a common absolute probability color scale. Each finger is
an independent distribution; overlapping colors are not a mixture probability.

Outputs: original circles, flat ellipses/density overlay, JSON equations/matrices
and approximate per-fret probability masses, and numeric density grids in NPZ
(units: probability per flat square pixel). Masses use a 1px grid sum; no
renormalization to the board, so outside-board mass is retained implicitly.
Very narrow distributions require finer numerical integration. Frets without
consecutive resolved boundaries receive no mass allocation. Geometry uncertainty
is not propagated, but boundary source labels are retained. No selected hand
produces empty distributions. Test with `python -m unittest test_fingertip_probability -v`.

## 개발 방향과 프로젝트 감사

2026-11-02 기준 [개발 총괄 지시서](docs/DEVELOPMENT_DIRECTIVE.md)에 개발 우선순위, 표준 분석·검증 파이프라인, 단계별 완료 기준을 정리했습니다. [전체 파일 목록](docs/file_inventory.csv)과 [감사 스냅샷](docs/audit_snapshot.json)에서 확인 범위를 추적할 수 있습니다.

## Offline still-image hand candidates

`hand_fret_tracker.py` uses the local `hand_landmarker.task` and a **resolved**
pipeline `*_result.json`. It never imports the legacy demos (both execute at import)
or calls BAZE. Verified locally with Python 3.10, mediapipe 1.1.1,
opencv-python 4.12.0.88 and numpy 2.2.6.

```powershell
python hand_fret_tracker.py --board-result dataset/gpt_boundary_retest/1051_5605_0000/result_result.json --out-prefix sample_images/hand_tracking/1051_5605_0000
python -m unittest test_hand_fret_tracker test_fret_geometry test_baze_client -v
```

Outputs: `_original.png`, `_flat.png`, and `.json` with all 21 normalized/pixel/flat
landmarks per detected hand, image-local hand indices, selection diagnostics,
four fingertip candidates and complete wire evidence. `FretboardGeometry.from_pipeline(pipeline)`
also accepts a completed live pipeline and reuses its `M`, `M_inv`, `fret_records`.
Use `detect_image`, `analyze_result`, and `render` for programmatic integration.
The existing fret pipeline is unchanged.

Saved corners are ordered original-pixel `[x,y]`, not normalized prompt coordinates.
Legacy results omit canvas dimensions: defaults are 800x150; explicitly supply
`--canvas-width/--canvas-height` for any other canvas. The image must be exactly
the frame used for board detection; `--image` only relocates that same image.
Relative image paths are resolved from the working directory (run at project root).

`--player right|left` specifies playing orientation (default right). Board proximity
dominates hand selection; near ties return `ambiguous_hand_selection` with no candidates.
`--mirrored unknown|yes|no` defaults to unknown, which disables the handedness prior.
The optional prior assumes MediaPipe's selfie convention (`yes`: raw label;
`no`: swapped). Validate this convention on a known hand for your camera/model;
handedness alone never chooses a hand. Proximity and ambiguity thresholds are
initial heuristics, not calibrated confidence probabilities.

Fret cells use consecutive physical wire numbers evaluated at each fingertip's y.
Outside-board, invalid-projection and unresolved-geometry points receive no fret.
Observed/interpolated/boundary-estimated evidence and adjustment histories remain
intact. Green wires are observed, cyan interpolated, magenta boundary estimates;
orange skeleton is selected, gray skeletons are other detections.
These are **fingering candidates**, not confirmed contacts or TAB notes. Hovering,
occlusion, off-plane projection, barre contacts and unverified fret numbering remain
limitations. Actual strings are not detected. Optional `--estimate-strings` uses
explicitly temporary uniform bands, top=Low E string 6, bottom=High E string 1.

`no_hands`, `no_hand_near_board`, and `ambiguous_hand_selection` are normal outcomes;
no earlier coordinates are reused. This module is still-image only: video timestamps,
persistent IDs, smoothing and tracking-loss lifecycle are the next stage and are not
implemented by image-local hand indices. The sample is an execution/visual smoke test,
not measured hand/contact accuracy; existing labels cover board corners only.

## Unified entry point

`two_stage_fret_pipeline.py` runs corner detection, homography, CLAHE/unsharp enhancement, human-exemplar few-shot fret detection, validated geometry, interpolation and rendering.
`run_perfect_certain_pipeline.py` and `render_perfect_pipeline.py` forward to the same CLI; they no longer run separate hard-coded experiments.

Live analysis uses the BAZE common Chat Completions gateway. Enter your key in the project-root `.env` file:

```dotenv
BAZE_API_KEY=your_baze_key
BAZE_MODEL=gpt-6.1-sol
```

Environment variables override `.env`. `.env` is ignored by Git. No agent settings, shell profiles or global OpenAI variables are changed. The default model is an example from the gateway documentation; verify your organization's availability before analysis:

```powershell
python baze_client.py
```

This checks authentication and model availability without uploading an image. After that, run the pipeline below. No Google-key fallback exists in the unified pipeline or corner-comparison tool. Historical standalone experiment scripts still use the old Google API; use the unified entry point for BAZE.

Endpoint: `https://factchat-cloud.mindlogic.ai/v1/gateway/chat/completions/`, with Bearer authentication. Image and few-shot contents are preserved; JSON output is requested through the shared prompt. See [BAZE Chat Completions reference](https://docs.mindlogic.ai/docs/general/api-gateway/reference/chat-completions).

```powershell
python two_stage_fret_pipeline.py sample_images/new_user_fender_maple.jpg --out-prefix sample_images/my_result
```

Replay cached results without an API request:

```powershell
python two_stage_fret_pipeline.py sample_images/new_user_fender_maple.jpg --corners-json sample_images/new_guitar_corners.json --frets-json sample_images/perfect_certain_frets.json --out-prefix sample_images/integrated_frets
python -m unittest test_fret_geometry -v
```

Corner JSON uses named `nut_top`, `body_top`, `body_bottom`, `nut_bottom` coordinates normalized as `[y,x]` in `[0,1000]`. Fret JSON contains `frets`, each with its physical `fret_num` and either visible `p1`/`p2` in the same coordinate format or `occluded: true` with a reason.

## Geometry contract

- Physical numbers are preserved, never replaced by array indices. Duplicate numbers, invalid/degenerate points, shallow segments, and crossed/reversed observed lines fail explicitly.
- Every bounded gap between observed wires is interpolated using normalized 12-TET geometric interval weights, independently at both board edges. This is a geometric estimate, not a measured wire position.
- Both explicitly hidden wires and omitted interior numbers are filled. Missing detections do not imply hand occlusion.
- Unbounded hidden wires remain unresolved, without coordinates. No nut or end-of-board extrapolation is performed.
- JSON records retain `source` (`observed`, `interpolated`, `occluded`), `occluded`, `interpolated`, and interpolation `anchors`. Cells are made only from consecutive physical numbers. Green lines are observed; cyan lines are interpolated.
- The system cannot establish correct physical numbering if the model supplies a consistently shifted sequence. No audio or actual string/contact detection is included.

Dependencies for this path: Python, numpy, opencv-python, requests. Run from the project directory.

## Refined corner extraction

Stage 1 first requests a coarse fretboard bounding box, pads it by 15%, enlarges the crop to at least 1400 pixels on its longest side, then requests precise nut/last-fret corners in crop coordinates. Coordinates are mapped back to the original image without integer rounding. Invalid boxes and crossed/degenerate quadrilaterals are rejected. Upsampling improves inspection size but does not recover lost image detail.

`check_corner_refinement.py` reproduces the explicitly authorized same-image API comparison against the existing manual label and runs subsequent fret detection. It writes per-corner Euclidean errors and polygon IoU to `sample_images/refined_corner_comparison.json`. This diagnostic uses the same project BAZE settings.


## Three-model BAZE comparison

The unified client now routes Gemini, GPT and Claude through the same `/chat/completions/` endpoint. Existing image/text few-shot contents are translated to OpenAI-compatible message blocks, preserving prompt text. `.env` accepts `BAZE_MODEL=gemini-3.5-flash`, `gpt-6.1-sol`, or `claude-sonnet-5-5`. Agent settings remain unchanged.

```powershell
# Offline estimate, no key needed, no network or API charges:
python compare_baze_models.py
# Execute all 12 images x 3 models x 2 extraction stages:
python compare_baze_models.py --run
python -m unittest test_baze_client test_fret_geometry -v
```

This benchmark evaluates fretboard corners only, not fret wires or TAB transcription. Both prompts are centralized in `fretboard_prompts.py`; manual labels are used only after detection for scoring, never as model inputs. Full-frame inputs are limited to 1400 pixels on their longest side. Each model chooses its own candidate crop, so this is an end-to-end comparison with identical preprocessing rules, not identical second-stage crop pixels.

Model availability is checked before any image analysis. Results under `dataset/baze_comparison` include the exact prompt manifest, data/config fingerprint, per-image responses, latency, normalized and raw usage, raw predicted corners, overlays (green manual, magenta prediction), aggregate JSON and CSV. Failures count as zero IoU; coordinate error is averaged over successes only. Missing token usage is explicitly counted. No automatic retries or provider fallback are performed. Existing per-image records (including failures/interrupted requests) are skipped to avoid silent rebilling; choose a new output directory to rerun. Keep benchmark artifacts local if input images are private.

Default planning estimate: 72 calls, 72k–288k input tokens, 14.4k–144k output/reasoning tokens, 86.4k–432k total. This is a broad engineering allowance, not measured tokenizer output or a cost quote. Image tokenization and internal reasoning differ between providers; actual usage can exceed this range. Each call has a 16,000 output-token budget (all calls combined: 1,152,000 configured output-token ceiling, not expected consumption). Network failures can be billed without usage returned. Provider pricing is not comparable by total token count alone.

Official reference: https://docs.mindlogic.ai/docs/general/api-gateway/reference/chat-completions


The actual comparison is saved under `dataset/baze_comparison/report.md`. Use `python summarize_baze_comparison.py` to rebuild the final report and visual comparisons without API calls. Claude responses with a preamble exposed a client parsing limitation; the parser now accepts exactly one complete JSON object within surrounding text. Eleven failed Claude images were explicitly retried with the same prompts. `previous_attempts` preserves initial failures and usage. One additional diagnostic request is accounted separately. Use `--retry-failed` only for deliberate paid retries; it does not retry successes. Provider totals may include tokens absent from input/output subtotals, so use reported total_tokens for total usage and retain the raw breakdown.

The production default is now `gpt-6.1-sol` based on the 12-image evaluation. Each CLI run writes `_api_calls.json` with raw JSON answers and reported usage, even when later geometry validation fails. No agent settings are modified.


## Boundary-aware fret recovery

The pipeline now uses its stage-1 nut/last-wire corner contract to recover clipped endpoints as explicitly estimated geometry. `resolve_frets(..., board_boundaries=True)` enables this; the standalone default remains conservative. A terminal index needs at least six observed wires, a projective 12-TET fit with <=0.4% canvas-width mean residual at both edges, monotonic spacing, and one unambiguous index within 0.65 local fret intervals at each edge. A supplied `last_fret_num` must agree. No fixed universal 20/21/22-fret assumption is used. Inconclusive cases remain unresolved.

`source=boundary_estimated` and `estimated=true` mark these lines (magenta); they are not reclassified as observed. Original occlusion reasons remain. Internal missing wires are interpolated between anchors (cyan). Short observed lines extrapolating <=0.5% canvas width beyond an edge are explicitly clipped with `original_endpoints` retained; larger excursions are rejected, never silently clamped.

Fresh five-image validation: `python retest_fret_boundaries.py` incurs API usage and skips existing records. `python summarize_boundary_retest.py` rebuilds the before/after report without API calls. Results and limitations: `dataset/gpt_boundary_retest/boundary_report.md`. The old runs remain under `dataset/gpt_full_evaluation`. Do not interpret zero unresolved geometry as certified physical fret numbering; some endpoint counts changed across model calls, and corner quality still limits recovery.


## Local string detection (no API)

The detector no longer creates six regularly spaced slots. It extracts a variable number of ridge-line candidates and rejects inconsistent directions. `strings` contains measured candidate line models, explicit reference-based estimates only when a validated same-canvas reference is supplied, and `unresolved` lists identities not established. `screen_rank` is independent of physical `string_num`. Six-line physical numbering is inferred only for a plausible complete family using explicit physical-side metadata; inferred numbers are not direct observations. Queries reject unnamed strings and unobserved line intervals by default.

`string_geometry.py` warps directly from the original image into a native-size-aware detector canvas, then converts line models and visible intervals back to the common canvas. It saves source/frame IDs, hashes, original/common/detection sizes, all transformation matrices, physical-side provenance, preserved fret numbers/sources, per-line model/identity source, and unresolved records. No API is imported by this geometry/detection path.

```powershell
python evaluate_string_review.py
python detect_strings_offline.py
python -m unittest test_string_detector test_fret_geometry test_baze_client -v
```

Review deliverables: `dataset/string_review/report.md`, `resolution_comparison.jpg`, per-frame `*_high_raw.png`, `*_high.json`, `manual_string_references.json`, and `failure_photo.json`. Manual references are agent visual approximations on four clearly visible lines per frame, pending independent user review. They are not six-string ground truth. This sample's 800x150 warp upsamples native board dimensions; measured resampling differences are within manual-reference uncertainty.

Fret labeler: explicit number input, deletion preserving identities, JSON import and gap-aware cell labels. Run `python fret_labeler.py`, load `dataset/fret_labels/user_fret_example.json`. The partial numbering audit and preserved original are under `dataset/label_audit/`. No chord-name classification is implemented in this string module; existing unrelated chord experiments were left untouched.
