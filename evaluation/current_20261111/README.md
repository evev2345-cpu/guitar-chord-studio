# Current-system audit / evaluation

This directory contains **evaluation adapters only**. Production engine/model/thresholds are not modified.

## Frozen scope

- GitHub commit: `5c5396bc2c3ac8a667cd0fb42db66e09340742cd`.
- Main execution: unmodified Git archive, `server_v2.analyze(..., separate_guitar=True)`. Its separation error and fallback are recorded, not repaired in the main experiment.
- Additional execution: locally corrected separation dispatcher and the current production `analyze()`. This is a separate variant; it is not presented as the unmodified Git commit.
- All 180 archived GuitarSet comp files (2 known timing files excluded only from primary statistics), and the same six IDMT guitar files / 1,638 labelled intervals.
- `A`: native `top3[0]` before cleanup/context/onset/presentation. `B`: native `onset_presentation.display_candidates`, default context/onset/beat grid. Other native layers are diagnostic. This is **the full postprocessing-stack ablation**, not an isolated Look-Ahead experiment.
- Exact uses the legacy root + pitch-class-set normalization. Bass spelling is additionally scored in `posthoc.py`; the two metrics must not be conflated.
- No learned note calibrator, parameter sweep, synthetic vision, annotation timing adjustment, or training is added.

Full preregistration: `PROTOCOL.json`. Dataset file hashes and fixed query times: `dataset_manifest.json`.

## Reproduction

Keep the chosen source commit available locally and install the project's audio-model and separation runtime environments. The original run includes exact version locks and environment details in its output. Both datasets must be supplied locally; no audio is downloaded or included here.

```powershell
# From E:\GUITAR. The IDMT root contains guitar/*.wav and guitar_annotation.lab.
python evaluation/current_20261111/prepare.py `
  --guitarset-root 'C:/Users/evev2/Documents/antigravity/GUITAR/GuitarSet' `
  --idmt-root 'C:/Users/evev2/Documents/antigravity/GUITAR/IDMT_SMT_Chords/extracted/IDMT-SMT-CHORDS' `
  --output evaluation/runs/reproduction_v1

$env:GCS_EVAL_RUN = (Resolve-Path evaluation/runs/reproduction_v1).Path
.venv-audio-model/Scripts/python.exe evaluation/current_20261111/inventory.py
.venv-audio-model/Scripts/python.exe evaluation/current_20261111/run.py --mode github
.venv-audio-model/Scripts/python.exe evaluation/current_20261111/run.py --mode patched
python evaluation/current_20261111/aggregate.py
python evaluation/current_20261111/posthoc.py
python evaluation/current_20261111/transition_diagnosis.py
python evaluation/current_20261111/audit.py
node evaluation/current_20261111/audit_ui.js github
node evaluation/current_20261111/audit_ui.js patched
python evaluation/current_20261111/test_metrics.py -q
```

Production datasets/model caches are read-only. New analysis artifacts are written under the selected evaluation run, outside the app's user library. Completed per-record results are resumable. Existing unsuccessful output directories are preserved as attempts, never used as inference caches. Evaluation errors are kept separately from production failures.

The archived FFT / early Basic Pitch comparisons use **previously saved predictions**, not new inference. `history.py` requires the original archived experiment directory for re-scoring and integrity checking. The original run preserves the re-scored historical JSON and source record hashes. Never describe these archived values as new model runs.

## Artifacts

- `manifest.json`, `protocol.json`, source ZIP/snapshot, working-tree patch, environment and model hashes.
- `<mode>/artifacts/<job>/`: actual input, analysis logs, new predictions, MIDI, model metadata and full production `result.json`.
- `<mode>/records/`: per-file metrics, timings, model/separation execution evidence and transition records.
- `<mode>/details/*.csv`: each evaluated timestamp, reference, candidates and exact/root/quality correctness.
- `<mode>/dense/*.jsonl.gz`: native 24Hz candidates, independent of reference evaluation sampling.
- `summary.json`, `per_quality.csv`, `confusions.csv`, `per_file.csv`, `transitions.json`, `posthoc.json`, `transition_diagnosis.json`.

`A` shares actual preprocessing/inference with `B`. Its native raw-candidate stage is timed separately, but an independent complete A end-to-end run is **not** performed. Only B `analyze()` wall times and observed component times are reported; no fabricated A total is inferred.

These are previously examined development corpora, not a new held-out test. GuitarSet was also used in the Basic Pitch research data. The datasets have different domains/protocols; absolute scores across them must not be treated as a generalization comparison.
