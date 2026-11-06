# Experimental fusion_cell.v1 — 2026-11-03

## Semantic identity/chain gate — 2026-11-04

Actual B adapter supports hand_anatomical_validity.v1. It verifies pre-sidecar
owner file SHA and unchanged observation/cell masses, review JSON/image hashes,
baseline ROI raw21 equality and digest, then recomputes each medoid lineage using
B.resolve_medoid and its policy using B.anatomical_validity. Supplied status,
human_review_applied and allowed flag must match those results. Per-finger
observation_id/branch still identify the recorded derived observation, while
raw_hand_sha256 binds it to the full original single-hand skeleton. Different
raw views are not fused into a hand or given the reviewed hand's digest.

Distribution and cell anatomical_fingering_evidence_allowed=false are hard gates
even if a caller supplies status=valid; the affected cell remains semantically
unknown/denied. Actual B v2 produces invalid middle/ring/pinky and unknown
thumb/index. No valid anatomical permission is manufactured from that review.
The 30 standalone files are verified against their six frame records; only their
two additional wrapper provenance fields may differ. Replay saves all thirty
per-file results and exact source paths/hashes. Old records without sidecars now
default to unknown, so previous synthetic CLI inputs without explicit simulated
permission may conservatively abstain. Current stress fixtures are generated in
`runs/semantic_gate_20261104_v4/`, explicitly synthetic.

Semantic permission precedes score weighting. Every finger needs
`observation_lineage` and `semantic_validity` with status valid/invalid/unknown,
finger_id, matching lineage and reasons. Status concerns anatomical finger and
chain identity only; it does not establish coordinate accuracy, contact or sound.
Missing validity defaults to unknown. Invalid and unknown remain distinct
diagnostics, but neither can rank cells, supply MIDI, or enter combinations in
any of the five weight experiments, including finger-labelled audio-only rows.
Raw V/A remain in raw_video_score/raw_audio_score; effective values and rank score
are null, never zero. Raw audio component evidence remains diagnostic at grid level.

Lineage keys: source_id, frame_index, frame_pts_s, frame_pixel_sha256,
observation_id, branch, raw_hand_sha256. Validity lineage must match the finger
record exactly. Source/index/pixel must match the grid; raw PTS vs upstream
six-decimal grid PTS tolerance is at most 1 microsecond with raw values retained.
There is no cross-frame transfer. A raw21-hand digest identifies the whole raw
observation; per-finger medoids from different hands cannot be labelled that hand.
Absent/incomplete/contradictory lineage becomes unknown, not an invalid judgement
about another crop. Finger identity also must match the scoped assessment.

`apply_fusion_semantic_policy` accepts fusion_semantic_policy.v1, policy_id,
complete lineage and fingers mapping names to {status,reasons}. It attaches only
on an exact seven-key match and records matched_fingers. No match leaves unrelated
records unchanged. A policy for baseline ROI cannot cover another crop just by
sharing frame210. Unknown anatomical semantics are independent of low/zero
numeric score, missing audio, geometry withholding and crop coordinate quality.
Legacy actual inputs with no semantic permission now abstain conservatively.

The user's frame210 review only invalidates baseline ROI middle/ring/pinky
anatomical chains, not all crops/frames. Qualitatively acceptable thumb/index are
not precise point or contact truth. No automatic finger relabelling, missing
pinky construction or runtime use of Kim coordinates is allowed.

## Actual owner bridge

`fusion_from_owner_records` accepts A grid, B hand_cell_frame.v1 and C
audio_cell_compatibility.v1. B's inclusive unassigned_mass already includes
outside/unresolved; adapter subtracts those categories to form exclusive residual
(invalid-projection mass remains in it) and preserves the entire owner record.
It selects exactly one named full/crop observation branch, never pools correlated
observations or replaces full pixels with a crop medoid. Abstain stays withheld.

B's referenced original grid file hash is verified. A v2 changes only
geometry_status/upstream_geometry_validity for the same ID/cells; the adapter
allows that explicit metadata-only revision only after A.assert_grid_compatible,
exact unchanged cell/transform payload and original artifact hash validation.
Geometry cannot be promoted through this exception. All old/new hashes and changed
fields remain provenance. A changed polygon or other field is rejected.

C's exact_frequency score alone maps to A, preserving raw exact/persistent/PC
diagnostics separately. Evaluated zero with explicit no_matching_candidate_evidence
or pitch_class_only_support is allowed even without exact-match IDs. It is no
matching support, not mute or zero probability. Null remains missing.
Synthetic C grid IDs are rejected for actual A/B; no cell-name aliasing is done.

`cell_audio_fusion_replay.py` reuses C.compare (does not implement another audio
algorithm) for actual Demucs fixtures and A/B at124/190/215, six grid models each.
Standard tuning is explicitly assumed and capo remains null; scores are therefore
conditional physical-fret hypotheses. Actual source hash, audio fixture hash and
C implementation hash are retained. Geometry suspect/hand abstain still prevents
fusion ranking. Raw-modality plots expose observations without changing the gate.
Accompaniment provisional harmony is attached diagnostically and not rescored.

Owner: harmony. CLI: `python cell_audio_fusion.py --input FILE --output NEW_DIR`.
No model/API calls; import has no side effects. Output directory must be new.

## Boundary

Input has `schema_version: fusion_cell.v1`, `data_kind`, `grid`, `video`, `audio`.
Each branch repeats source_id, grid_id, grid_version, frame_index, frame_pts_s,
frame_pixel_sha256, canvas_size, M, M_inv, start_s, end_s and
timebase=source_video_seconds. They must match exactly. Frame PTS must be inside
the window. Homographies must be finite inverse 3x3 matrices (projective scale
allowed). Do not replace frame PTS with index/fps. Each grid variant is a separate
input/run; cells from different anchor/spacing models cannot be mixed.

`grid.cells[]`: cell_id, virtual_string_num, physical_fret_candidate, polygon,
is_virtual=true, estimated=true; geometry/anchor/spacing/numbering sources and
assumptions remain unchanged. `geometry_status=usable_for_hypotheses` explicitly
allows ranking, not contact. Any other status withholds cell fusion. Actual A
grid geometry_status=unverified is preserved and withheld by the pending adapter.
Optional possible_midi is usable for chord hypotheses only with
pitch_basis=explicit_assumption or verified_tuning_physical_fret; upstream must
preserve the actual tuning/capo derivation. No MIDI is computed from pixels here.

`video.score_type=unconditional_location_mass`; fingers[] contains finger_id,
quality_status, cell_masses mapping cell_id→mass and outside_mass/unresolved_mass/
unassigned_mass. Sum must be <=1. No in-board normalization or max scaling occurs.
Only quality_status=usable enters joint ranking. Crop/full disagreement, ROI-only
grades and original records must be retained by an upstream adapter; do not map a
withheld grade to usable just because a distribution is concentrated.

`audio.score_type=normalized_compatibility_0_1`, quality_status, cells mapping
cell_id→{score,evidence_ids,...}. Audio owner's normalized heuristic [0,1] score is
accepted unchanged, not z-scored or interpreted as probability. Non-null scores
must carry support IDs. Null/missing score remains unavailable. The source identity,
separation/piano uncertainty and exact/persistent/PC support remain in raw records.
The boundary deliberately does not silently guess another owner's field aliases.
An actual-owner adapter must verify grid/frame/canvas provenance before translating.

## Scores and search

For available modalities only, S=wV*V+wA*A. Fixed experiments: 60:40, 80:20,
40:60, video-only, audio-only. A missing required modality produces score=null;
no zero fill or hidden weight renormalization. Single-modal experiments expose
what is still available. Input quality statuses, not score magnitude, determine
poor/withheld states. Both poor yields no assignment; geometry withholding is
never overridden by audio. 60:40 is a starting heuristic, not a learned optimum.

Each finger's full cell ranking is distinct from the joint combination ranking.
Beam search width128 takes at most12 cell options per finger plus unassigned.
At most one cell per finger, at most one finger per virtual string. This deliberately
conservative constraint rejects conflicting frets and also excludes legitimate
multi-finger same-string/barre techniques; no barre or sounding model is inferred.
Low-quality fingers remain unassigned. Audio-only gives cell rankings, no finger
assignment. Partial combinations retain unassigned fingers implicitly; score
denominator is the total number of input fingers, so missing assignments do not
increase the average. Search limits and constraints are emitted, not exhaustive.

Joint score = (wV*sum assigned visual masses + wA*sum independent support scores)
/total input fingers. An audio support set overlapping already-counted evidence
IDs contributes no second audio score. This is conservative and order dependent
for partially overlapping sets, not a claim of statistical independence. The same
accompaniment-derived chord score is never added/multiplied into cell scoring.
Per-cell scores have no such joint deduplication, so their top choices can differ
from the best valid combination. Top combination gap<.05 is an ambiguity flag,
not calibrated uncertainty.

Outputs separate confirmed_guitar_chords (always empty in this module), retained
accompaniment_harmony (diagnostic only), and combination fingering_chord_hypotheses.
All contact/sounding remain unknown. Correct-looking code names or Kim evaluation
points must never be runtime score inputs. No accuracy claim without cell truth.

## Current fixtures

`dataset/cell_audio_fusion/fixtures/synthetic_contract.json` and
`synthetic_geometry_withheld.json` are synthetic scores and grid, not observations.
`actual_grid124_pending.json` preserves actual A frame124/PTS5.208333 grid,
unverified geometry and sources, with empty B/C measurements. It does not fabricate
a real fusion. `harmony_input_adapter.fusion_pending_from_grid` reproduces it.

Heatmaps show max rank score over fingers, not sum, pressure or contact probability.
White means unavailable; a genuinely evaluated zero is dark. Actual grid/hand
photos remain separate from synthetic heatmaps to avoid implying a pixel match.
