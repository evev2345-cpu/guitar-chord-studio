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


def align_tempo_to_chords(times, rows, presentation, tempo):
    """Align Bar 1 (1마디, offset_s) to the song's first sustained chord start and lock barlines to chord transitions."""
    if not isinstance(tempo, dict) or not tempo.get("bpm") or not rows or not presentation:
        return tempo
    times = np.asarray(times, dtype=float)
    if len(times) < 4:
        return tempo
    dt = float(np.median(np.diff(times)))
    segs = []
    for t, pr in zip(times, presentation):
        cands = pr.get("frame_display_candidates") or pr.get("display_candidates") or []
        root = int(cands[0]["root_pc"]) if cands else None
        if segs and segs[-1][2] == root:
            segs[-1][1] = float(t) + dt
        else:
            segs.append([float(t), float(t) + dt, root])

    t_first = None
    for i, (s, e, root) in enumerate(segs):
        if root is None:
            continue
        active_3s = sum(
            min(s2[1], s + 3.0) - max(s2[0], s)
            for s2 in segs[i:]
            if s2[2] is not None and s2[0] < s + 3.0
        )
        if (e - s) >= 0.45 and active_3s >= 1.1:
            t_first = s
            break
    if t_first is None:
        for s, e, root in segs:
            if root is not None and (e - s) >= 0.35:
                t_first = s
                break
    if t_first is None:
        return tempo

    trans = [s for s, e, root in segs if root is not None and s >= t_first and (e - s) >= 0.55]
    trans_w = [min(3.0, e - s) for s, e, root in segs if root is not None and s >= t_first and (e - s) >= 0.55]
    base_bpm = float(tempo.get("auto_bpm") or tempo["bpm"])
    beat_s0 = 60.0 / base_bpm
    six_s0 = beat_s0 / 4.0
    if len(trans) < 2:
        tempo["offset_s"] = round(float(t_first), 4)
        tempo["sixteenth_offset_s"] = round(float(t_first % six_s0), 4)
        tempo["first_bar_s"] = round(float(t_first), 4)
        return tempo

    trans_arr = np.asarray(trans, dtype=float)
    weights_arr = np.asarray(trans_w, dtype=float)
    best_sc = -1e9
    best_bpm = base_bpm
    best_off = float(t_first)
    for bpm in np.arange(max(40.0, base_bpm - 1.2), min(240.0, base_bpm + 1.25), 0.05):
        beat_s = 60.0 / float(bpm)
        bar_s = 4.0 * beat_s
        half_s = 2.0 * beat_s
        six_s = beat_s / 4.0
        sig = 0.55 * six_s
        for off in np.linspace(t_first - six_s, t_first + six_s, 25):
            if off < 0.0:
                continue
            rel = trans_arr - off
            d_bar = np.abs(((rel + bar_s / 2.0) % bar_s) - bar_s / 2.0)
            d_half = np.abs(((rel + half_s / 2.0) % half_s) - half_s / 2.0)
            d_beat = np.abs(((rel + beat_s / 2.0) % beat_s) - beat_s / 2.0)
            sc = float(
                np.sum(
                    weights_arr
                    * (
                        1.2 * np.exp(-0.5 * (d_bar / sig) ** 2)
                        + 0.7 * np.exp(-0.5 * (d_half / sig) ** 2)
                        + 0.25 * np.exp(-0.5 * (d_beat / sig) ** 2)
                    )
                )
            )
            sc += 4.0 * float(np.exp(-0.5 * ((off - t_first) / (0.4 * six_s)) ** 2))
            sc -= 0.20 * abs(float(bpm) - base_bpm)
            if sc > best_sc:
                best_sc = sc
                best_bpm = round(float(bpm), 1)
                best_off = round(float(off), 4)

    beat_s = 60.0 / best_bpm
    sixteenth_s = beat_s / 4.0
    tempo["bpm"] = best_bpm
    tempo["auto_bpm"] = best_bpm
    tempo["beat_s"] = round(beat_s, 5)
    tempo["sixteenth_s"] = round(sixteenth_s, 5)
    tempo["offset_s"] = best_off
    tempo["sixteenth_offset_s"] = round(float(best_off % sixteenth_s), 4)
    tempo["first_bar_s"] = best_off
    tempo["bar_aligned"] = True
    return tempo


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
        # In guitar music, major 6th chords (e.g. C6, D6, A6) are almost always misidentified relative minor 7th chords.
        has_relative_m7 = (
            c["quality"] == "6"
            and any(
                other["quality"] == "m7"
                and (other["root_pc"] - c["root_pc"]) % 12 == 9
                and set(other.get("pcs") or []) == set(c.get("pcs") or [])
                for other in cands
            )
        )
        sc = _QUALITY_PREFERENCE.get(c["quality"], 0.5)
        if has_relative_m7:
            sc -= 2.0
        sc += 0.35 * min(song_counts.get(cid, 0), 15)
        sc += 0.10 * min(root_counts.get(root, 0), 20)
        if left_cand is not None:
            if (left_cand["root_pc"], left_cand["quality"]) == cid:
                sc += 10.0
            elif left_cand["root_pc"] == root and not has_relative_m7:
                sc += 4.0
            elif (left_cand["root_pc"] - root) % 12 == 7:
                # V -> I resolution (e.g. G#7 -> C#m7, E7 -> Am7)
                sc += 6.0
            elif (root - left_cand["root_pc"]) % 12 in (5, 7):
                sc += 1.5
        if right_cand is not None:
            if (right_cand["root_pc"], right_cand["quality"]) == cid:
                sc += 10.0
            elif right_cand["root_pc"] == root and not has_relative_m7:
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
            if any(
                (c.get("bass_display_status") == "low_string_below_root_inversion" and "/" in str(c.get("symbol", "")))
                or c.get("user_edited")
                for c in cands
            ):
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
                (c.get("bass_display_status") == "low_string_below_root_inversion" and "/" in str(c.get("symbol", "")))
                or c.get("user_edited")
                for c in chosen_cands
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

    offset_slot = int(round((float(offset_s or 0.0) - slot_origin) / sixteenth_s))

    # 1. Bridge empty (보류) gaps:
    # (i) intra-bar decay gaps <= 6 slots (~0.9s) when the gap starts mid-bar (mod16 != 0) and previous chord is active
    # (ii) any other short empty gaps <= 3 slots (~0.45s)
    for s, e in slot_runs(slot_cands):
        if not slot_cands[s] and s > 0 and slot_cands[s - 1]:
            gap_len = e - s
            mod16 = (unique_slots[s] - offset_slot) % 16
            is_intra_bar = (mod16 != 0)
            if gap_len <= 3 or (is_intra_bar and gap_len <= 6):
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
        slot_time_s = float(times[f_idxs[0]]) if f_idxs else 0.0
        raw_hits = sum(
            1
            for fi in f_idxs
            if any((c["root_pc"], c["quality"]) == cid0 for c in (rows[fi].get("top3") or []))
        )
        raw_ratio = raw_hits / len(f_idxs) if f_idxs else 0.0
        sc0 = float(cand0.get("score", 0.0))
        if next_empty:
            if (
                slot_time_s < float(offset_s or 0.0) - 0.3
                or cand0["quality"] in ("aug", "dim", "dim7", "diminished", "m7b5")
                or raw_ratio <= 0.65
                or sc0 < 0.78
            ):
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

    def _mode_family(q):
        if q in ("minor", "m7", "m6", "m7b5"):
            return 1
        if q in ("dim", "dim7", "diminished", "aug"):
            return 2
        return 0

    offset_slot = int(round((float(offset_s or 0.0) - slot_origin) / sixteenth_s))

    def _metrical_weight(slot_idx):
        m = (unique_slots[slot_idx] - offset_slot) % 16
        if m == 0:
            return 4  # Barline (0/4)
        if m == 8:
            return 3  # Half-bar (1/2)
        if m in (4, 12):
            return 2  # Quarter-bar (1/4, 3/4)
        if m % 2 == 0:
            return 1  # Eighth-note off-beat
        return 0      # Odd sixteenth-note

    # 2b. Backward attack backfill: when an initial attack is followed by a certain sustained chord (>= 6 slots),
    # backfill the front slots if:
    #   (i) same root and same major/minor mode family (<= 6 slots and shorter than the following main chord, e.g. Gadd9(5~6) -> G(11~12), Em6(5) -> Em(8)), OR
    #   (ii) <= 4 slots, shares >= 3 pitch classes, AND the following chord was in the front frames' top3 >= 70% of the time (e.g. C6 -> Am7, D -> Bm7).
    # Never pull a transition backward off a stronger metrical boundary (Barline/Half-Bar/Quarter-Bar) onto a weaker off-beat.
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
            if r_idx > 0 and slot_cands[rlist[r_idx - 1][0]] and _metrical_weight(rs) > _metrical_weight(s):
                continue
            b_cand = slot_cands[rs][0]
            b_root = b_cand["root_pc"]
            b_mode = _mode_family(b_cand["quality"])
            b_id = (b_root, b_cand["quality"])
            b_pcs = set(b_cand.get("pcs") or [])
            same_root = (
                all(c["root_pc"] == b_root and _mode_family(c["quality"]) == b_mode for c in slot_cands[s])
                and front_len < back_len
            )
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

    # 4c. Final same-root + same-mode-family consolidation after metrical boundary snap (e.g. Abadd9(4칸) -> Ab(12칸) inside Bar 11)
    rlist = slot_runs(slot_cands)
    for r_idx in range(len(rlist) - 1):
        s, e = rlist[r_idx]
        rs, re = rlist[r_idx + 1]
        if (
            not slot_cands[s]
            or not slot_cands[rs]
            or (e - s) > 6
            or (re - rs) < (e - s)
            or any(slot_has_low_inv[j] for j in range(s, re))
        ):
            continue
        c0 = slot_cands[s][0]
        c1 = slot_cands[rs][0]
        if c0["root_pc"] == c1["root_pc"] and _mode_family(c0["quality"]) == _mode_family(c1["quality"]):
            pick = slot_cands[rs] if _QUALITY_PREFERENCE.get(c1["quality"], 0.5) >= _QUALITY_PREFERENCE.get(c0["quality"], 0.5) else slot_cands[s]
            for j in range(s, re):
                slot_cands[j] = copy.deepcopy(pick)

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
            main_mode = _mode_family(slot_cands[ls][0]["quality"])
            if all(c["root_pc"] == main_root and _mode_family(c["quality"]) == main_mode for c in slot_cands[s]):
                for j in range(s, e):
                    slot_cands[j] = copy.deepcopy(slot_cands[ls])
                changed = True
        if not changed:
            break

    # 4c. Final same-root + same-mode-family consolidation after metrical boundary snap (e.g. Abadd9(4칸) -> Ab(12칸) inside Bar 11)
    rlist = slot_runs(slot_cands)
    for r_idx in range(len(rlist) - 1):
        s, e = rlist[r_idx]
        rs, re = rlist[r_idx + 1]
        if (
            not slot_cands[s]
            or not slot_cands[rs]
            or (e - s) > 6
            or (re - rs) < (e - s)
            or any(slot_has_low_inv[j] for j in range(s, re))
        ):
            continue
        c0 = slot_cands[s][0]
        c1 = slot_cands[rs][0]
        if c0["root_pc"] == c1["root_pc"] and _mode_family(c0["quality"]) == _mode_family(c1["quality"]):
            pick = slot_cands[rs] if _QUALITY_PREFERENCE.get(c1["quality"], 0.5) >= _QUALITY_PREFERENCE.get(c0["quality"], 0.5) else slot_cands[s]
            for j in range(s, re):
                slot_cands[j] = copy.deepcopy(pick)

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
            l_mode = _mode_family(slot_cands[ls][0]["quality"])
            r_mode = _mode_family(slot_cands[rs][0]["quality"])
            s_root = slot_cands[s][0]["root_pc"] if slot_cands[s] else -1
            if l_root == r_root and l_mode == r_mode and (_full_key(slot_cands[ls]) == _full_key(slot_cands[rs]) or s_root != l_root):
                pick = slot_cands[ls] if (le - ls) >= (re - rs) else slot_cands[rs]
                for j in range(s, e):
                    slot_cands[j] = copy.deepcopy(pick)

    # Now merge consecutive short runs (each <= 4 slots) that share the same root and mode family into their best canonical chord
    rlist = slot_runs(slot_cands)
    idx = 0
    while idx < len(rlist):
        s0, e0 = rlist[idx]
        if not slot_cands[s0] or (e0 - s0) > 4 or any(slot_has_low_inv[j] for j in range(s0, e0)):
            idx += 1
            continue
        root0 = slot_cands[s0][0]["root_pc"]
        mode0 = _mode_family(slot_cands[s0][0]["quality"])
        end_idx = idx + 1
        while end_idx < len(rlist):
            sn, en = rlist[end_idx]
            if (
                not slot_cands[sn]
                or (en - sn) > 4
                or slot_cands[sn][0]["root_pc"] != root0
                or _mode_family(slot_cands[sn][0]["quality"]) != mode0
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

    # 2e. Unify consecutive symmetric diminished runs sharing the same diminished pitch-class axis (root_pc % 3)
    def unify_diminished_clusters():
        rlist_dim = slot_runs(slot_cands)
        d_idx = 0
        while d_idx < len(rlist_dim):
            s0, _ = rlist_dim[d_idx]
            if not slot_cands[s0] or slot_cands[s0][0].get("quality") not in ("dim", "dim7", "diminished"):
                d_idx += 1
                continue
            axis = slot_cands[s0][0]["root_pc"] % 3
            end_d = d_idx + 1
            while end_d < len(rlist_dim):
                sn, _ = rlist_dim[end_d]
                if (
                    not slot_cands[sn]
                    or slot_cands[sn][0].get("quality") not in ("dim", "dim7", "diminished")
                    or (slot_cands[sn][0]["root_pc"] % 3) != axis
                ):
                    break
                end_d += 1
            if end_d - d_idx >= 2:
                next_root = (
                    slot_cands[rlist_dim[end_d][0]][0]["root_pc"]
                    if (end_d < len(rlist_dim) and slot_cands[rlist_dim[end_d][0]])
                    else None
                )
                best_rep = None
                best_w = -1.0
                for k in range(d_idx, end_d):
                    sk, ek = rlist_dim[k]
                    c = slot_cands[sk][0]
                    w = float(ek - sk)
                    if next_root is not None and (next_root - c["root_pc"]) % 12 == 1:
                        w += 10.0
                    if w > best_w:
                        best_w = w
                        best_rep = slot_cands[sk]
                if best_rep is not None:
                    for j in range(rlist_dim[d_idx][0], rlist_dim[end_d - 1][1]):
                        slot_cands[j] = copy.deepcopy(best_rep)
            d_idx = end_d

    unify_diminished_clusters()

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
                right_roots = {c["root_pc"] for c in right_anchor}
                right_flags = [
                    any(
                        c["root_pc"] in right_roots
                        for fi in slot_frames[j]
                        for c in (rows[fi].get("top3") or [])[:2]
                    )
                    for j in range(span_start, span_end)
                ]
                split_offset = total_slots
                while split_offset > 0 and right_flags[split_offset - 1]:
                    split_offset -= 1
                for offset, j in enumerate(range(span_start, span_end)):
                    slot_cands[j] = copy.deepcopy(right_anchor if offset >= split_offset else left_anchor)
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

    # 4. Bridge any remaining empty gaps (intra-bar decay gaps <= 6 slots, other <= 3 slots) and unify diminished clusters
    for s, e in slot_runs(slot_cands):
        if not slot_cands[s] and s > 0 and slot_cands[s - 1]:
            gap_len = e - s
            mod16 = (unique_slots[s] - offset_slot) % 16
            is_intra_bar = (mod16 != 0)
            if gap_len <= 3 or (is_intra_bar and gap_len <= 6):
                for idx in range(s, e):
                    slot_cands[idx] = copy.deepcopy(slot_cands[s - 1])
    unify_diminished_clusters()

    # 4b. Hierarchical Metrical Boundary Stabilization:
    # Priority: Barline (0, 1마디 시작) > Half-Bar (8, 1/2 지점) > Quarter-Bar (4/12, n/4 지점) > Rest.
    for _ in range(2):
        rlist = slot_runs(slot_cands)
        run_reps = [copy.deepcopy(slot_cands[s]) for s, _ in rlist]
        changed = False
        for r_idx in range(1, len(rlist)):
            ls, le = rlist[r_idx - 1]
            s, e = rlist[r_idx]
            l_len = le - ls
            r_len = e - s
            if not run_reps[r_idx - 1] or not run_reps[r_idx]:
                continue
            if slot_has_low_inv[s] or slot_has_low_inv[s - 1]:
                continue
            mod16 = (unique_slots[s] - offset_slot) % 16
            # Tier 1: +/- 1 slot around Barline (0) or Half-Bar (8)
            if mod16 in (15, 7) and l_len >= 2 and r_len >= 3:
                slot_cands[s] = copy.deepcopy(run_reps[r_idx - 1])
                changed = True
            elif mod16 in (1, 9) and l_len >= 3 and r_len >= 2:
                slot_cands[s - 1] = copy.deepcopy(run_reps[r_idx])
                changed = True
            # Tier 1b: 2 slots early/late around Half-Bar (8) or Barline (0)
            elif mod16 == 6 and l_len >= 4 and r_len >= 4 and s + 1 < len(slot_cands) and not slot_has_low_inv[s + 1]:
                slot_cands[s] = copy.deepcopy(run_reps[r_idx - 1])
                slot_cands[s + 1] = copy.deepcopy(run_reps[r_idx - 1])
                changed = True
            elif mod16 in (2, 10) and l_len >= 6 and r_len >= 4 and (l_len % 8) == 2 and s >= 2 and not slot_has_low_inv[s - 2]:
                slot_cands[s - 2] = copy.deepcopy(run_reps[r_idx])
                slot_cands[s - 1] = copy.deepcopy(run_reps[r_idx])
                changed = True
            elif mod16 == 14 and l_len >= 4 and r_len >= 6 and s + 1 < len(slot_cands) and not slot_has_low_inv[s + 1]:
                l_root = run_reps[r_idx - 1][0]["root_pc"]
                f_idxs = slot_frames[s] + slot_frames[s + 1]
                prev_supported = any(
                    c["root_pc"] == l_root
                    for fi in f_idxs
                    for c in (rows[fi].get("top3") or []) + ((rows[fi].get("context") or {}).get("top3") or [])
                )
                if prev_supported or r_len >= 17:
                    slot_cands[s] = copy.deepcopy(run_reps[r_idx - 1])
                    slot_cands[s + 1] = copy.deepcopy(run_reps[r_idx - 1])
                    changed = True
            # Tier 2: +/- 1 slot around Quarter-Bar (n/4 points: mod16 == 4 or 12)
            elif mod16 in (3, 11) and l_len >= 2 and r_len >= 3:
                slot_cands[s] = copy.deepcopy(run_reps[r_idx - 1])
                changed = True
            elif mod16 in (5, 13) and l_len >= 3 and r_len >= 2:
                slot_cands[s - 1] = copy.deepcopy(run_reps[r_idx])
                changed = True
        if not changed:
            break

    # 4c. Final same-root + same-mode-family consolidation after metrical boundary snap (e.g. Abadd9(4칸) -> Ab(12칸) inside Bar 11)
    rlist = slot_runs(slot_cands)
    for r_idx in range(len(rlist) - 1):
        s, e = rlist[r_idx]
        rs, re = rlist[r_idx + 1]
        if (
            not slot_cands[s]
            or not slot_cands[rs]
            or (e - s) > 6
            or (re - rs) < (e - s)
            or any(slot_has_low_inv[j] for j in range(s, re))
        ):
            continue
        c0 = slot_cands[s][0]
        c1 = slot_cands[rs][0]
        if c0["root_pc"] == c1["root_pc"] and _mode_family(c0["quality"]) == _mode_family(c1["quality"]):
            pick = slot_cands[rs] if _QUALITY_PREFERENCE.get(c1["quality"], 0.5) >= _QUALITY_PREFERENCE.get(c0["quality"], 0.5) else slot_cands[s]
            for j in range(s, re):
                slot_cands[j] = copy.deepcopy(pick)

    for k_idx, f_idxs in enumerate(slot_frames):
        cands = slot_cands[k_idx]
        for fi in f_idxs:
            out[fi]["frame_display_candidates"] = copy.deepcopy(presentation[fi].get("display_candidates") or [])
            if _full_key(out[fi].get("display_candidates") or []) != _full_key(cands):
                out[fi]["display_candidates"] = copy.deepcopy(cands)
                out[fi]["status"] = "quantized_16th_beat_grid"
            out[fi]["beat_slot"] = int(unique_slots[k_idx])
    return out
