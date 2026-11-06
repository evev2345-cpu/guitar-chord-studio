"""Automatic tempo (BPM) / 16th-note tatum grid estimation and grid-locked chord transitions."""
import copy
import numpy as np


def estimate_tempo_and_phase(times, notes, onsets=None, min_bpm=75.0, max_bpm=175.0):
    """Estimate song BPM and 16th-note grid phase offset from Basic Pitch note/onset activations."""
    times = np.asarray(times, dtype=float)
    notes = np.asarray(notes, dtype=float)
    if len(times) < 8 or notes.ndim != 2 or len(notes) != len(times):
        return {
            "bpm": 120.0,
            "auto_bpm": 120.0,
            "beat_s": 0.5,
            "sixteenth_s": 0.125,
            "offset_s": 0.0,
            "sixteenth_offset_s": 0.0,
            "subdivision": 16,
            "confidence": 0.0,
            "source": "fallback_short",
        }
    dt = float(np.median(np.diff(times)))
    guitar_notes = notes[:, 19:68] if notes.shape[1] >= 68 else notes
    flux = np.maximum(0.0, np.diff(guitar_notes, axis=0, prepend=guitar_notes[:1])).sum(axis=1)
    if onsets is not None and np.asarray(onsets).shape == notes.shape:
        onsets_arr = np.asarray(onsets, dtype=float)
        guitar_onsets = onsets_arr[:, 19:68] if onsets_arr.shape[1] >= 68 else onsets_arr
        onset_env = guitar_onsets.max(axis=1) * 2.5 + guitar_onsets.sum(axis=1) * 0.4
        env = flux * 0.5 + onset_env
    else:
        env = flux

    kernel = np.array([0.2, 0.6, 1.0, 0.6, 0.2], dtype=float)
    kernel /= kernel.sum()
    env = np.convolve(env, kernel, mode="same")
    env = np.maximum(0.0, env - np.percentile(env, 35))
    if np.max(env) > 1e-9:
        env = env / np.max(env)

    env_centered = env - np.mean(env)
    ac = np.correlate(env_centered, env_centered, mode="full")[len(env_centered) - 1:]
    if ac[0] > 1e-9:
        ac = ac / ac[0]

    bpms = np.arange(min_bpm, max_bpm + 0.1, 0.25)
    best_bpm = 120.0
    best_score = -1e9
    lags_idx = np.arange(len(ac), dtype=float)
    for bpm in bpms:
        beat_s = 60.0 / float(bpm)
        score = 0.0
        for mult, weight in [(0.25, 0.15), (0.5, 0.35), (1.0, 1.0), (2.0, 0.70), (4.0, 0.50), (8.0, 0.35)]:
            exact_lag = (beat_s * mult) / dt
            if 1.0 <= exact_lag < len(ac) - 2:
                score += weight * float(np.interp(exact_lag, lags_idx, ac))
        prior = np.exp(-0.5 * ((np.log2(bpm / 128.0)) / 0.45) ** 2)
        total_score = score * (0.80 + 0.20 * prior)
        if total_score > best_score:
            best_score = total_score
            best_bpm = float(bpm)

    fine_bpms = np.round(np.arange(max(min_bpm, best_bpm - 1.0), min(max_bpm, best_bpm + 1.05), 0.1), 2)
    best_offset = 0.0
    best_phase_score = -1e9
    for cand_bpm in fine_bpms:
        beat_s = 60.0 / float(cand_bpm)
        sixteenth_s = beat_s / 4.0
        phase_candidates = np.linspace(0.0, beat_s, 48, endpoint=False)
        for ph in phase_candidates:
            p_score = 0.0
            for sub, w in [(beat_s, 1.0), (beat_s / 2.0, 0.45), (sixteenth_s, 0.25)]:
                grid_t = np.arange(ph % sub, times[-1], sub)
                idx = np.clip(np.searchsorted(times, grid_t), 0, len(env) - 1)
                p_score += w * float(np.mean(env[idx])) if len(idx) else 0.0
            if p_score > best_phase_score:
                best_phase_score = p_score
                best_bpm = float(cand_bpm)
                best_offset = float(ph)

    beat_s = 60.0 / best_bpm
    sixteenth_s = beat_s / 4.0
    rounded_bpm = round(best_bpm, 1)
    return {
        "bpm": rounded_bpm,
        "auto_bpm": rounded_bpm,
        "beat_s": round(beat_s, 5),
        "sixteenth_s": round(sixteenth_s, 5),
        "offset_s": round(best_offset, 4),
        "sixteenth_offset_s": round(best_offset % sixteenth_s, 4),
        "subdivision": 16,
        "confidence": round(float(max(0.0, min(1.0, best_score / 2.0))), 3),
        "source": "auto_onset_flux_comb_v1",
    }


def _full_key(candidates):
    if not candidates:
        return ()
    return tuple(
        sorted(
            (c["root_pc"], c["quality"], c.get("bass_pc") if "/" in c.get("symbol", "") else None)
            for c in candidates
        )
    )


_QUALITY_PREFERENCE = {
    "major": 3.0,
    "minor": 3.0,
    "m7": 2.7,
    "7": 2.6,
    "maj7": 2.5,
    "sus4": 1.4,
    "add9": 1.0,
    "sus2": 0.8,
    "6": 0.5,
    "m6": 0.5,
    "dim": 0.2,
    "aug": 0.2,
    "m7b5": 0.2,
}


def _resolve_single_candidate(cands, left_cand, right_cand, song_counts, root_counts, frame_idxs, rows):
    """Deterministically pick the best single chord when multiple tied candidates remain."""
    if not cands or len(cands) <= 1:
        return cands
    obs_bass_pcs = []
    for fi in frame_idxs:
        ctx = rows[fi].get("context") or {}
        bass = ctx.get("bass") or {}
        if bass.get("pc") is not None:
            obs_bass_pcs.append(int(bass["pc"]))

    best_c = cands[0]
    best_score = -1e9
    for c in cands:
        cid = (c["root_pc"], c["quality"])
        root = c["root_pc"]
        sc = _QUALITY_PREFERENCE.get(c["quality"], 0.5)
        sc += 0.35 * min(song_counts.get(cid, 0), 15)
        sc += 0.10 * min(root_counts.get(root, 0), 20)
        if left_cand is not None:
            if (left_cand["root_pc"], left_cand["quality"]) == cid:
                sc += 10.0
            elif left_cand["root_pc"] == root:
                sc += 4.0
            elif (left_cand["root_pc"] - root) % 12 == 7:
                # V -> I resolution (e.g. G#7 -> C#m7, E7 -> Am7)
                sc += 6.0
            elif (root - left_cand["root_pc"]) % 12 in (5, 7):
                sc += 1.5
        if right_cand is not None:
            if (right_cand["root_pc"], right_cand["quality"]) == cid:
                sc += 10.0
            elif right_cand["root_pc"] == root:
                sc += 4.0
            elif (root - right_cand["root_pc"]) % 12 == 7:
                sc += 3.0
        if obs_bass_pcs:
            bass_match = sum(1 for pc in obs_bass_pcs if pc == root) / len(obs_bass_pcs)
            sc += 2.5 * bass_match
        sc += float(c.get("adjusted_score", c.get("score", 0.0))) * 0.1
        if sc > best_score:
            best_score = sc
            best_c = c
    return [copy.deepcopy(best_c)]


def quantize_to_16beat_grid(times, rows, presentation, bpm, offset_s=0.0):
    """Snap chord transitions to a 16th-note grid (1/16 of a 4/4 measure) and remove transition chatter."""
    if not rows or not presentation or bpm is None or float(bpm) <= 0:
        return presentation
    times = np.asarray(times, dtype=float)
    out = copy.deepcopy(presentation)
    sixteenth_s = 60.0 / float(bpm) / 4.0
    slot_origin = float(offset_s or 0.0) % sixteenth_s

    slot_indices = np.floor((times - slot_origin + 1e-9) / sixteenth_s).astype(int)
    unique_slots = sorted(set(slot_indices.tolist()))
    slot_map = {k: [] for k in unique_slots}
    for i, k in enumerate(slot_indices):
        slot_map[int(k)].append(i)

    slot_cands = []
    slot_frames = []
    slot_has_low_inv = []
    for k in unique_slots:
        f_idxs = slot_map[k]
        slot_frames.append(f_idxs)
        votes = {}
        rep_cands = {}
        has_low_inv = False
        for i in f_idxs:
            cands = out[i].get("display_candidates") or []
            if not cands:
                continue
            if any(c.get("bass_display_status") == "low_string_below_root_inversion" for c in cands):
                has_low_inv = True
            fk = _full_key(cands)
            w = float(max((c.get("score", 0.8) for c in cands), default=0.8))
            if len(cands) == 1:
                w += 0.15
            votes[fk] = votes.get(fk, 0.0) + w
            if fk not in rep_cands or len(cands) < len(rep_cands[fk]):
                rep_cands[fk] = copy.deepcopy(cands)
        if votes:
            best_fk = max(votes.keys(), key=lambda k_: votes[k_])
            chosen_cands = rep_cands[best_fk]
            slot_cands.append(chosen_cands)
            has_low_inv = any(
                c.get("bass_display_status") == "low_string_below_root_inversion" for c in chosen_cands
            )
        else:
            slot_cands.append([])
        slot_has_low_inv.append(has_low_inv)

    def slot_runs(seq):
        res = []
        s = 0
        for i in range(1, len(seq) + 1):
            if i == len(seq) or _full_key(seq[i]) != _full_key(seq[s]):
                res.append((s, i))
                s = i
        return res

    # 0. Resolve tied multi-candidate slots (e.g. C#m7 / E6, C6 / Am7, Em7 / G6) into a single canonical chord
    song_counts = {}
    root_counts = {}
    for cands in slot_cands:
        if len(cands) == 1:
            c = cands[0]
            cid = (c["root_pc"], c["quality"])
            song_counts[cid] = song_counts.get(cid, 0) + 1
            root_counts[c["root_pc"]] = root_counts.get(c["root_pc"], 0) + 1

    rlist = slot_runs(slot_cands)
    for r_idx, (s, e) in enumerate(rlist):
        if len(slot_cands[s]) > 1:
            left_c = None
            for l_idx in range(r_idx - 1, -1, -1):
                ls, _ = rlist[l_idx]
                if len(slot_cands[ls]) == 1:
                    left_c = slot_cands[ls][0]
                    break
            right_c = None
            for n_idx in range(r_idx + 1, len(rlist)):
                rs, _ = rlist[n_idx]
                if len(slot_cands[rs]) == 1:
                    right_c = slot_cands[rs][0]
                    break
            f_idxs = [fi for j in range(s, e) for fi in slot_frames[j]]
            resolved = _resolve_single_candidate(
                slot_cands[s], left_c, right_c, song_counts, root_counts, f_idxs, rows
            )
            for j in range(s, e):
                slot_cands[j] = copy.deepcopy(resolved)

    # 1. Bridge short empty (보류) gaps <= 3 sixteenth-note slots (~0.33s) by holding the previous chord
    for s, e in slot_runs(slot_cands):
        if not slot_cands[s] and s > 0 and (e - s) <= 3 and slot_cands[s - 1]:
            for idx in range(s, e):
                slot_cands[idx] = copy.deepcopy(slot_cands[s - 1])

    # 1b. Suppress silence-bounded percussive/mute noise islands (e.g. N -> Daug(0.33s) -> N, or N -> weak Emaj7(0.33s) -> Cmaj7)
    rlist = slot_runs(slot_cands)
    for r_idx, (s, e) in enumerate(rlist):
        span_len = e - s
        if not slot_cands[s] or span_len > 3 or any(slot_has_low_inv[j] for j in range(s, e)):
            continue
        prev_empty = (r_idx == 0) or (not slot_cands[rlist[r_idx - 1][0]])
        next_empty = (r_idx + 1 == len(rlist)) or (not slot_cands[rlist[r_idx + 1][0]])
        if not prev_empty:
            continue
        cand0 = slot_cands[s][0]
        cid0 = (cand0["root_pc"], cand0["quality"])
        f_idxs = [fi for j in range(s, e) for fi in slot_frames[j]]
        raw_hits = sum(
            1
            for fi in f_idxs
            if any((c["root_pc"], c["quality"]) == cid0 for c in (rows[fi].get("top3") or []))
        )
        raw_ratio = raw_hits / len(f_idxs) if f_idxs else 0.0
        sc0 = float(cand0.get("score", 0.0))
        if next_empty:
            if cand0["quality"] in ("aug", "dim", "m7b5") or raw_ratio <= 0.65 or sc0 < 0.78:
                for j in range(s, e):
                    slot_cands[j] = []
        else:
            if raw_ratio < 0.50 or (sc0 < 0.75 and raw_ratio <= 0.65):
                for j in range(s, e):
                    slot_cands[j] = []

    # 2. Consolidate same-root brief variations (<= 2 slots) into adjacent sustained chord (>= 3 slots)
    for _ in range(2):
        rlist = slot_runs(slot_cands)
        for r_idx, (s, e) in enumerate(rlist):
            length = e - s
            if not slot_cands[s] or length > 2 or any(slot_has_low_inv[j] for j in range(s, e)):
                continue
            roots = {c["root_pc"] for c in slot_cands[s]}
            if r_idx > 0:
                ls, le = rlist[r_idx - 1]
                if (
                    (le - ls) >= 3
                    and slot_cands[ls]
                    and not any(slot_has_low_inv[j] for j in range(ls, le))
                    and {c["root_pc"] for c in slot_cands[ls]} == roots
                ):
                    for idx in range(s, e):
                        slot_cands[idx] = copy.deepcopy(slot_cands[ls])
                    continue
            if r_idx + 1 < len(rlist):
                rs, re = rlist[r_idx + 1]
                if (
                    (re - rs) >= 3
                    and slot_cands[rs]
                    and not any(slot_has_low_inv[j] for j in range(rs, re))
                    and {c["root_pc"] for c in slot_cands[rs]} == roots
                ):
                    for idx in range(s, e):
                        slot_cands[idx] = copy.deepcopy(slot_cands[rs])
                    continue

    # 2b. Backward attack backfill: when an initial attack is followed by a certain sustained chord (>= 6 slots),
    # backfill the front slots if:
    #   (i) same root (<= 6 slots and shorter than the following main chord, e.g. Gadd9(5~6) -> G(11~12), Em6(5) -> Em(8)), OR
    #   (ii) <= 4 slots, shares >= 3 pitch classes, AND the following chord was in the front frames' top3 >= 70% of the time (e.g. C6 -> Am7, D -> Bm7).
    # Never overwrite physical low-below-root inversions (e.g. D/F#).
    for _ in range(2):
        rlist = slot_runs(slot_cands)
        changed = False
        for r_idx in range(len(rlist) - 1):
            s, e = rlist[r_idx]
            rs, re = rlist[r_idx + 1]
            front_len = e - s
            back_len = re - rs
            if (
                not slot_cands[s]
                or not slot_cands[rs]
                or front_len > 6
                or back_len < 6
                or len(slot_cands[rs]) != 1
                or any(slot_has_low_inv[j] for j in range(s, re))
            ):
                continue
            b_cand = slot_cands[rs][0]
            b_root = b_cand["root_pc"]
            b_id = (b_root, b_cand["quality"])
            b_pcs = set(b_cand.get("pcs") or [])
            same_root = all(c["root_pc"] == b_root for c in slot_cands[s]) and front_len < back_len
            shared_pcs = front_len <= 4 and any(len(set(c.get("pcs") or []) & b_pcs) >= 3 for c in slot_cands[s])
            front_frame_idxs = [fi for j in range(s, e) for fi in slot_frames[j]]
            if front_frame_idxs:
                supported_count = sum(
                    1
                    for fi in front_frame_idxs
                    if any(
                        (c["root_pc"], c["quality"]) == b_id
                        for c in (rows[fi].get("top3") or []) + ((rows[fi].get("context") or {}).get("top3") or [])
                    )
                )
                support_ratio = supported_count / len(front_frame_idxs)
            else:
                support_ratio = 0.0
            if same_root or (shared_pcs and support_ratio >= 0.70 - 1e-9):
                for j in range(s, e):
                    slot_cands[j] = copy.deepcopy(slot_cands[rs])
                changed = True
        if not changed:
            break

    # 2c. Forward tail consolidation: when a sustained main chord (>= 5 slots, single candidate) is followed
    # by a short same-root release variation (<= 5 slots, e.g. G -> Gadd9, D -> Dadd9, Em -> Esus4, C -> Cadd9, Em7 -> Em),
    # absorb the tail into the preceding main chord.
    for _ in range(2):
        rlist = slot_runs(slot_cands)
        changed = False
        for r_idx in range(1, len(rlist)):
            ls, le = rlist[r_idx - 1]
            s, e = rlist[r_idx]
            main_len = le - ls
            tail_len = e - s
            if (
                not slot_cands[ls]
                or not slot_cands[s]
                or len(slot_cands[ls]) != 1
                or main_len < 5
                or tail_len > 5
                or tail_len > main_len
                or any(slot_has_low_inv[j] for j in range(s, e))
            ):
                continue
            main_root = slot_cands[ls][0]["root_pc"]
            if all(c["root_pc"] == main_root for c in slot_cands[s]):
                for j in range(s, e):
                    slot_cands[j] = copy.deepcopy(slot_cands[ls])
                changed = True
        if not changed:
            break

    # 2d. Same-root fragmented cluster consolidation (e.g. Cmaj7(2) -> Csus2(2) -> Cadd9(2) -> C(2))
    # First bridge 1-2 slot glitches sandwiched between two runs of the same root R
    rlist = slot_runs(slot_cands)
    for r_idx in range(1, len(rlist) - 1):
        ls, le = rlist[r_idx - 1]
        s, e = rlist[r_idx]
        rs, re = rlist[r_idx + 1]
        if (
            (e - s) <= 2
            and slot_cands[ls]
            and slot_cands[rs]
            and not any(slot_has_low_inv[j] for j in range(s, e))
        ):
            l_root = slot_cands[ls][0]["root_pc"]
            r_root = slot_cands[rs][0]["root_pc"]
            if l_root == r_root:
                pick = slot_cands[ls] if (le - ls) >= (re - rs) else slot_cands[rs]
                for j in range(s, e):
                    slot_cands[j] = copy.deepcopy(pick)

    # Now merge consecutive short runs (each <= 4 slots) that share the same root into their best canonical chord
    rlist = slot_runs(slot_cands)
    idx = 0
    while idx < len(rlist):
        s0, e0 = rlist[idx]
        if not slot_cands[s0] or any(slot_has_low_inv[j] for j in range(s0, e0)):
            idx += 1
            continue
        root0 = slot_cands[s0][0]["root_pc"]
        end_idx = idx + 1
        while end_idx < len(rlist):
            sn, en = rlist[end_idx]
            if (
                not slot_cands[sn]
                or slot_cands[sn][0]["root_pc"] != root0
                or any(slot_has_low_inv[j] for j in range(sn, en))
            ):
                break
            end_idx += 1
        if end_idx - idx >= 2:
            # Check if this is a fragmented cluster (at least one short run <= 4 slots)
            lengths = [rlist[k][1] - rlist[k][0] for k in range(idx, end_idx)]
            if min(lengths) <= 4:
                cand_weights = {}
                cand_rep = {}
                for k in range(idx, end_idx):
                    sk, ek = rlist[k]
                    c = slot_cands[sk][0]
                    cid = (c["root_pc"], c["quality"])
                    w = (ek - sk) + 0.6 * _QUALITY_PREFERENCE.get(c["quality"], 0.5)
                    cand_weights[cid] = cand_weights.get(cid, 0.0) + w
                    cand_rep[cid] = slot_cands[sk]
                best_cid = max(cand_weights.keys(), key=lambda k_: cand_weights[k_])
                best_rep = cand_rep[best_cid]
                cluster_start = rlist[idx][0]
                cluster_end = rlist[end_idx - 1][1]
                for j in range(cluster_start, cluster_end):
                    slot_cands[j] = copy.deepcopy(best_rep)
        idx = end_idx

    # 3. Absorb unconfirmed transition chatter (total span <= 4 slots) between sustained anchor runs (>= 3 slots)
    rlist = slot_runs(slot_cands)
    is_anchor = [
        bool(slot_cands[s]) and ((e - s) >= 3 or (any(slot_has_low_inv[j] for j in range(s, e)) and (e - s) >= 2))
        for s, e in rlist
    ]
    idx = 0
    while idx < len(rlist):
        if is_anchor[idx] or not slot_cands[rlist[idx][0]]:
            idx += 1
            continue
        end_idx = idx
        while end_idx < len(rlist) and not is_anchor[end_idx] and slot_cands[rlist[end_idx][0]]:
            end_idx += 1
        span_start = rlist[idx][0]
        span_end = rlist[end_idx - 1][1]
        total_slots = span_end - span_start
        left_anchor = slot_cands[rlist[idx - 1][0]] if idx > 0 and is_anchor[idx - 1] else None
        right_anchor = slot_cands[rlist[end_idx][0]] if end_idx < len(rlist) and is_anchor[end_idx] else None

        if total_slots <= 4 and not any(slot_has_low_inv[j] for j in range(span_start, span_end)):
            if left_anchor and right_anchor and _full_key(left_anchor) == _full_key(right_anchor):
                for j in range(span_start, span_end):
                    slot_cands[j] = copy.deepcopy(left_anchor)
            elif left_anchor and right_anchor:
                for j in range(span_start, span_end):
                    f_idxs = slot_frames[j]
                    right_roots = {c["root_pc"] for c in right_anchor}
                    has_right = any(
                        c["root_pc"] in right_roots
                        for fi in f_idxs
                        for c in (rows[fi].get("top3") or [])[:2]
                    )
                    slot_cands[j] = copy.deepcopy(right_anchor if has_right else left_anchor)
            elif left_anchor:
                for j in range(span_start, span_end):
                    slot_cands[j] = copy.deepcopy(left_anchor)
            elif right_anchor:
                for j in range(span_start, span_end):
                    slot_cands[j] = copy.deepcopy(right_anchor)
        idx = end_idx

    # 3b. Final pass to absorb any remaining 1-2 slot same-root residual fragments adjacent to >= 3 slot runs
    rlist = slot_runs(slot_cands)
    for r_idx, (s, e) in enumerate(rlist):
        if not slot_cands[s] or (e - s) > 2 or any(slot_has_low_inv[j] for j in range(s, e)):
            continue
        roots = {c["root_pc"] for c in slot_cands[s]}
        if r_idx + 1 < len(rlist):
            rs, re = rlist[r_idx + 1]
            if (
                (re - rs) >= 3
                and slot_cands[rs]
                and not any(slot_has_low_inv[j] for j in range(rs, re))
                and {c["root_pc"] for c in slot_cands[rs]} == roots
            ):
                for idx in range(s, e):
                    slot_cands[idx] = copy.deepcopy(slot_cands[rs])
                continue
        if r_idx > 0:
            ls, le = rlist[r_idx - 1]
            if (
                (le - ls) >= 3
                and slot_cands[ls]
                and not any(slot_has_low_inv[j] for j in range(ls, le))
                and {c["root_pc"] for c in slot_cands[ls]} == roots
            ):
                for idx in range(s, e):
                    slot_cands[idx] = copy.deepcopy(slot_cands[ls])

    # 4. Bridge any remaining <= 3 slot empty gaps after consolidation
    for s, e in slot_runs(slot_cands):
        if not slot_cands[s] and s > 0 and (e - s) <= 3 and slot_cands[s - 1]:
            for idx in range(s, e):
                slot_cands[idx] = copy.deepcopy(slot_cands[s - 1])

    for k_idx, f_idxs in enumerate(slot_frames):
        cands = slot_cands[k_idx]
        for fi in f_idxs:
            out[fi]["frame_display_candidates"] = copy.deepcopy(presentation[fi].get("display_candidates") or [])
            if _full_key(out[fi].get("display_candidates") or []) != _full_key(cands):
                out[fi]["display_candidates"] = copy.deepcopy(cands)
                out[fi]["status"] = "quantized_16th_beat_grid"
            out[fi]["beat_slot"] = int(unique_slots[k_idx])
    return out
