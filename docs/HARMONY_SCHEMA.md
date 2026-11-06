# Harmony evidence contract (initial implementation)

## Actual Demucs v5 replay

`harmony_demucs_review.py --input-root <audio v5 root> --output <new directory>`
validates shared source_id/timebase/PTS origin, component identity and separation
flags, actual branch PCM hashes, upstream separation/model/review/QA file hashes,
and candidate peak/parent-track references before replaying all nine fixtures.
It preserves entire candidate and persistence records in results.json; spectral
fingering_comparison_candidates are never converted into tentative or observed notes.
The branch source_identity object is used directly without guessed field aliases.
Salience event IDs are namespaced upstream and retained in each provisional candidate.

summary.json counts per-frame top1 labels/changes/ambiguity/exact ties. These are
descriptions of rankings, not temporal pooling of PCs or a stable-chord assertion.
comparison.md shows three candidates from each branch's central eligible frame;
abstaining frames are excluded from that representative selection and counts expose
how many were eligible. Scores/coverage/missing/extra and each frame time are in
results.json. All exact ties retain the existing deterministic root/quality sort;
the first label in an exact tie has no stronger evidence.

## Provisional accompaniment hypotheses (2026-11-03)

`provisional_audio_harmony` is independent of confirmed `chord_candidates`,
confirmed-pitch `mixed_audio_harmony`, and `fingering_hypotheses`. It preserves
audio source context (including accompaniment, separation and piano uncertainty).
The user's Demucs review confirms subjective vocal reduction and audible piano;
it does not establish isolated guitar or pitch correctness.

Each salience frame uses its own time_s and twelve finite nonnegative weights;
frames outside [start,end) are excluded and never pooled. Active PCs have positive
weight >=10% of the frame maximum; fewer than three active PCs abstains.
For target chord C, score = sum(weights on C)/sum(all weights)
- 0.15*(number of inactive chord PCs)/number of chord PCs. All dictionary roots
are compared, top three returned, ties resolved as before. Top gap <0.1 is
ambiguous. Coverage, missing/extra/active PCs, raw weights, event IDs and score_type
are available. This heuristic is not a calibrated probability or pitch transcription;
diffuse/noisy salience can still generate hypotheses requiring review.

`tentative_notes` with provisional/tentative pitch_status, integer MIDI and support
covering the complete requested interval can produce separate tentative_note_candidates
using the existing overlap score. Spectral peaks are not rounded or promoted.
The parent source_context derived_from_separation flag also blocks guitar confirmation,
even if individual notes are mistakenly labelled verified guitar. Instrument-source
ambiguity remains in all provisional outputs. Piano-compatible hypotheses are not
evidence that the guitarist sounded those notes.

`fixtures/actual_hpss_salience.json` is a pinned actual old HPSS fixture, explicitly
not Demucs accompaniment. `actual_accompaniment_pending.json` references the real
no_vocals.wav and user review but has empty acoustic evidence until the audio
owner supplies the new analysis fixture; mixture/HPSS features are never copied
onto the separated accompaniment source.

## Mixed-source boundary (2026-11-03)

User listening review confirms vocal+guitar only; it does not confirm pitches,
onsets, A/V alignment, other instruments, or instrument attribution of each peak.
`adapt_audio(..., listening_review=review)` requires matching source_id/timebase
and review coverage of the input interval. It preserves the review scope as
source_context. It does not create observed notes or change pitch_status.

Audio note source_identity is guitar/mixed/vocal/accompaniment/unknown; this is
distinct from spectral_peak_candidate/provisional/confirmed pitch_status.
Only pitch-confirmed notes (legacy absent pitch_status remains an explicit pitch
assertion) with source_identity=guitar, source_attribution_status=verified and
no derived_from_separation flag enter the main guitar chord candidates.
Attribution is an explicit upstream verification assertion, not inferred from a
file name, mixture containing guitar, salience, or a separator stem label.
Missing identity defaults to unknown and is withheld. Verified attribution must
be supported by upstream provenance. Audio adapters never populate it automatically.
Separated stems remain excluded from guitar confirmation even if labelled guitar;
future independently validated stem policies require a separate contract revision.

`mixed_audio_harmony` ranks temporally eligible confirmed audio pitches without
claiming instrument attribution. It is hypotheses_only or insufficient_evidence,
never a confirmed guitar result. `fingering_hypotheses` ranks only explicit
upstream possible joint string states and never combines them with audio.
Hand pixels, eight human landmarks, fret numbering semantics, and legacy hand
positions do not produce string states or sounding MIDI. The main `chord_candidates`
continues to accept explicit manual sounding MIDI assertions for engine fixtures;
callers must not relabel mixed audio as manual guitar evidence to bypass identity.

Actual input `fixtures/actual_pts_v3_mixed.json` pins the audio owner's pts_v3
5.05~5.35 s fixture and attaches source review provenance with file hashes.
This interval is a review target, not a validated stable chord segment.

## 2026-11-03 actual-audio boundary update

`capo` missing, null or an unknown object now all mean unknown fret. Fret-derived
notes are withheld; independent concert MIDI can still rank chords. Null tuning
continues to record an explicit unconfirmed standard tuning assumption.

The actual audio baseline has top-level `pitch_candidates` (floating MIDI,
`pitch_status=spectral_peak_candidate`) and `pitch_class_salience`; these are
preserved without copying into observed notes, rounding MIDI, or chord ranking.
`tentative_notes` is a separate preserved proposal tier with event_id, start_s,
end_s, pitch_status=tentative, score and score_type. Its score is not probability.
No tentative/salience hypothesis ranking is implemented. Only integer concert MIDI
in evidence.observed_audio_notes with pitch_status=confirmed is eligible in the
new timed contract. Legacy records lacking pitch_status retain their explicit
sounding-assertion meaning. A nonconfirmed status in that array is excluded with
a reason, and cannot influence bass or conflicts. Event IDs become evidence IDs.

`adapt_audio(record, start_s=..., end_s=..., selection_source=...)` selects an
explicit window within the source interval and records its source in
provenance.harmony_window. Candidate/support intervals are retained if overlapping;
onsets and salience centers use [start,end). Raw coordinates, event IDs, methods,
score_type and pitch_status are unchanged. Overlapping spectral windows still
contain surrounding audio; filtering does not assert acoustic stability.

Confirmed timed notes and string states must cover the entire analysis window to
enter ranking; others remain in excluded_note_evidence with reasons. This is
conservative and prevents sequential notes from becoming a fictitious chord.
Windowed adapter calls reject untimed sounding records. Legacy direct analyze
calls still treat untimed records as caller assertions for the entire interval.
Source-video identity is preserved; cross-source fusion remains the integrator's
responsibility. Window selection is explicit and is never inferred from a chord.

CLI supports `--start 3 --end 3.2 --selection-source contract_smoke_not_reviewed`.
This selection is a contract replay, not a reviewed stable musical segment.

Two-PC policy remains abstention, including E/B: no standalone power-chord
recognition is claimed. Dictionary quality 5 is retained only for comparison with
inputs of three or more PCs (with extras). No silent threshold relaxation was
made. Explicit dyad hypotheses and their ambiguity are deferred.

`harmony_engine.py` uses only the Python standard library. Import has no side effects.
Input and output are JSON objects with `schema_version: guitar_evidence.v1`,
`run_id`, `source_id` (original video SHA-256, null when unavailable), `start_s`,
`end_s`, and `timebase: source_video_seconds`. Intervals are finite [start,end).
Unknown source identity must not be replaced with a fixture hash.

## Input

- `tuning`: `{midi_6_to_1:[40,45,50,55,59,64],source,confirmed}`.
  Omission records an unconfirmed standard tuning assumption.
- `capo`: `{fret:0,source,confirmed}`. Missing/null fret remains unknown.
- `evidence.manual_notes` / `observed_audio_notes`: arrays of `{id,midi}`;
  null MIDI is preserved but excluded. Manual MIDI is an explicit sounding assertion.
- `evidence.string_states`: joint upstream state records with `string` (6 low E,
  1 high E), `state` (`sounding`, `possible`, `unknown`, `muted`, `unplayed`),
  `physical_fret` and/or `relative_fret`. Sounding is an explicit upstream assertion,
  never inferred by this engine. Unknown/X states produce no pitch. An X in a
  sounding numeric fret field is invalid. Physical frets behind capo remain unknown.
- `evidence.confirmed_bass_midi`: optional externally confirmed bass. Must be the
  lowest supplied sounding MIDI. Lowest detected/possible pitches do not confirm bass.
- `assumptions`, `provenance`, `limitations`: retained from caller.

MIDI = tuning[string] + physical_fret = tuning[string] + capo + relative_fret.
Both fret fields must agree. Capo-relative open is relative 0 / physical capo.
Output `computed_string_notes` includes MIDI, PC, display name and source labels.
PC is spelling independent; display uses fixed flat spellings, without key inference.

## Dictionary and ranking

Intervals relative to root, modulo 12:

| quality | intervals |
|---|---|
| major | 0,4,7 |
| minor | 0,3,7 |
| 5 | 0,7 |
| diminished | 0,3,6 |
| augmented | 0,4,8 |
| sus2 | 0,2,7 |
| sus4 | 0,5,7 |
| 6 | 0,4,7,9 |
| m6 | 0,3,7,9 |
| 7 | 0,4,7,10 |
| maj7 | 0,4,7,11 |
| m7 | 0,3,7,10 |
| m7b5 | 0,3,6,10 |
| dim7 | 0,3,6,9 |
| add9 | 0,2,4,7 |

For observed PC set O and candidate C, score is
`max(0,(|O intersect C| - 0.5*|C-O| - |O-C|)/|O union C|)`.
This is a heuristic similarity, not probability. Octave duplicates do not affect
the score. Roots have equal prior weight; dictionary membership is a musical prior.
At least three distinct observed PCs are required, including for power-chord
interpretations. Candidates require two matches and score >= .35. Rootless and
thirdless candidates are allowed. Return top three by score; ties use root PC then
quality. More tied interpretations can exist beyond the output cap.

Each candidate has concert_symbol, shape_symbol (always null until a reviewed
shape convention exists), root_pc, quality, bass_midi, score, score_type,
matched_pcs, missing_pcs, extra_pcs, evidence_ids and score_components.
Slash labels require confirmed bass. Status is insufficient_evidence when no
candidate is eligible, ambiguous when top two score difference < .1, otherwise ok.
Audio and explicit sounding string PC set disagreement overrides status with
evidence_conflict; this conservative set check can also flag partial observations.
No observation is repaired. `unknown_reason` explains abstention.

## Adapters and limits

`adapt_audio` currently accepts the proposed version unchanged. It is a boundary
fixture contract, not a claim of compatibility with a future audio detector.
`adapt_legacy_hand` preserves selected-hand candidate records and geometry sources
but strips tutorial reference labels. It generates no notes, contacts or string
assignments, does not select per-finger maxima, and searches no combinations.
The source hash must be supplied by caller; record SHA-256 is separate provenance.
Legacy interval duration is explicitly assumed 1/24 s. No real synchronization
or accuracy evaluation has been performed. Stage C joint hypothesis fusion awaits
upstream contracts; possible positions never enter observed chord ranking.

## Run

```powershell
python harmony_engine.py --input dataset/harmony_analysis/fixtures/input.json --output dataset/harmony_analysis/runs/demo
python -m unittest test_harmony_engine -v
```

Optional `--video PATH` checks and records an explicit video path without reading
media or extracting audio. Fixtures are synthetic; source_id is null. References,
if later added, belong in `dataset/harmony_analysis/references/`, outside evidence.
