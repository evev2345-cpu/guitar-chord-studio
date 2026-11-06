import copy
import unittest
import numpy as np
from chord_presentation import prepare


def chord(root,quality='major',score=1.):
    intervals=[0,4,7] if quality=='major' else [0,3,7]
    return dict(root_pc=root,quality=quality,pcs=[(root+i)%12 for i in intervals],score=score,symbol={0:'C',7:'G',9:'Am'}.get(root,'X'))


def row(chosen,alternatives=(),bass_pc=None,activation=.8):
    top=[copy.deepcopy(chosen)]+[copy.deepcopy(c) for c in alternatives]
    return dict(top3=top,context=dict(display_candidates=[copy.deepcopy(chosen)],top3=copy.deepcopy(top),status='audio_supported',
        bass=dict(pc=bass_pc,midi=40 if bass_pc==4 else 45,status='provisional',activation=activation,presence=1.)))


class PresentationTests(unittest.TestCase):
    def test_previous_interpretation_can_remain_within_current_ambiguity(self):
        rows=[row(chord(0)) for _ in range(48)]
        for r in rows[20:35]:r['context']['display_candidates'].append(chord(9,'minor'))
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[24]['status'],'retained_previous_among_ambiguous')
        self.assertEqual(len(out[24]['display_candidates']),1)
        self.assertEqual(len(rows[24]['context']['display_candidates']),2)

    def test_short_supported_return_is_removed_without_mutating_raw(self):
        c=chord(0);g=chord(7,score=.98);rows=[row(c) for _ in range(48)]
        for i in range(20,23):rows[i]=row(g,[chord(0,score=.96)])
        saved=copy.deepcopy(rows);out=prepare(np.arange(48)/24,rows)
        self.assertTrue(all(r['display_candidates'][0]['root_pc']==0 for r in out))
        self.assertEqual(rows,saved)

    def test_strong_brief_change_is_kept(self):
        c=chord(0);g=chord(7);rows=[row(c) for _ in range(48)]
        rows[20]=row(g,[chord(0,score=.5)])
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[20]['display_candidates'][0]['root_pc'],7)

    def test_unsupported_old_chord_is_not_carried(self):
        rows=[row(chord(0)) for _ in range(48)];rows[20]=row(chord(7))
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[20]['display_candidates'][0]['root_pc'],7)

    def test_real_sustained_change_has_no_added_start_delay(self):
        rows=[row(chord(0)) for _ in range(24)]+[row(chord(7),[chord(0,score=.96)]) for _ in range(24)]
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[23]['display_candidates'][0]['root_pc'],0)
        self.assertEqual(out[24]['display_candidates'][0]['root_pc'],7)

    def test_transient_or_moderate_bass_is_not_spelled_as_slash(self):
        rows=[row(chord(0),bass_pc=4,activation=.54) for _ in range(48)]
        out=prepare(np.arange(48)/24,rows)
        self.assertTrue(all('/' not in r['display_candidates'][0]['symbol'] for r in out))
        self.assertEqual(out[24]['observed_bass']['pc'],4)
        rows=[row(chord(0),bass_pc=0) for _ in range(48)]
        for i in range(20,23):rows[i]['context']['bass']['pc']=4
        out=prepare(np.arange(48)/24,rows)
        self.assertTrue(all('/' not in r['display_candidates'][0]['symbol'] for r in out))

    def test_strong_sustained_inversion_remains_available(self):
        rows=[row(chord(0),bass_pc=4) for _ in range(48)]
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[24]['display_candidates'][0]['symbol'],'C/E')

    def test_ambiguous_interpretations_do_not_gain_slash_spam(self):
        rows=[row(chord(0),bass_pc=4) for _ in range(48)]
        for r in rows:r['context']['display_candidates'].append(chord(9,'minor'))
        out=prepare(np.arange(48)/24,rows)
        self.assertTrue(all('/' not in c['symbol'] for r in out for c in r['display_candidates']))
        self.assertEqual(len(out[24]['display_candidates']),2)

    def test_missing_audio_does_not_receive_an_invented_chord(self):
        rows=[row(chord(0)) for _ in range(48)]
        rows[24]['top3']=[];rows[24]['context']['top3']=[];rows[24]['context']['display_candidates']=[]
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[24]['display_candidates'],[])

    def test_multi_step_same_root_extension_chatter_is_consolidated(self):
        base=dict(root_pc=9,quality='major',pcs=[9,1,4],score=1.,symbol='A')
        ext6=dict(root_pc=9,quality='6',pcs=[9,1,4,6],score=1.,symbol='A6')
        add9=dict(root_pc=9,quality='add9',pcs=[9,1,4,11],score=1.,symbol='Aadd9')
        rows=[row(base) for _ in range(48)]
        for i in range(18,22):rows[i]=row(ext6,[base])
        for i in range(22,26):rows[i]=row(add9)
        out=prepare(np.arange(48)/24,rows)
        self.assertTrue(all(r['display_candidates'][0]['quality']=='major' for r in out))
        self.assertEqual(out[23]['status'],'consolidated_same_root_extension')

    def test_physical_low_below_root_inversion_preserved_while_mid_register_suppressed(self):
        eb=dict(root_pc=3,quality='major',pcs=[3,7,10],score=1.,symbol='Eb/G',base_symbol='Eb')
        rows=[row(eb,bass_pc=7,activation=.59) for _ in range(48)]
        for r in rows:r['context']['bass']['midi']=43
        out=prepare(np.arange(48)/24,rows)
        self.assertEqual(out[24]['display_candidates'][0]['symbol'],'Eb/G')
        self.assertEqual(out[24]['display_candidates'][0]['bass_display_status'],'low_string_below_root_inversion')

    def test_sixteenth_note_grid_absorbs_finger_lift_transition_chatter(self):
        c_sharp_m7=dict(root_pc=1,quality='m7',pcs=[1,4,8,11],score=1.,symbol='C#m7',base_symbol='C#m7')
        e7=dict(root_pc=4,quality='7',pcs=[4,8,11,2],score=.82,symbol='E7',base_symbol='E7')
        a_maj=dict(root_pc=9,quality='major',pcs=[9,1,4],score=1.,symbol='A',base_symbol='A')
        rows=[row(c_sharp_m7) for _ in range(18)]+[row(e7) for _ in range(3)]+[row(a_maj) for _ in range(27)]
        out=prepare(np.arange(48)/24,rows,tempo=dict(bpm=130.,offset_s=0.))
        symbols=[r['display_candidates'][0]['symbol'] for r in out]
        self.assertNotIn('E7',symbols)
        self.assertEqual(symbols[0],'C#m7')
        self.assertEqual(symbols[-1],'A')

    def test_backward_attack_backfill_merges_initial_misrecognition_into_certain_following_chord(self):
        c6=dict(root_pc=0,quality='6',pcs=[0,4,7,9],score=1.,symbol='C6',base_symbol='C6')
        am7=dict(root_pc=9,quality='m7',pcs=[9,0,4,7],score=.96,symbol='Am7',base_symbol='Am7')
        rows=[row(c6,[am7]) for _ in range(9)]+[row(am7,[c6]) for _ in range(39)]
        out=prepare(np.arange(48)/24,rows,tempo=dict(bpm=130.,offset_s=0.))
        self.assertTrue(all(r['display_candidates'][0]['symbol']=='Am7' for r in out))

    def test_forward_tail_consolidation_absorbs_same_root_release_variation(self):
        d_maj=dict(root_pc=2,quality='major',pcs=[2,6,9],score=1.,symbol='D',base_symbol='D')
        d_add9=dict(root_pc=2,quality='add9',pcs=[2,4,6,9],score=.95,symbol='Dadd9',base_symbol='Dadd9')
        em=dict(root_pc=4,quality='minor',pcs=[4,7,11],score=1.,symbol='Em',base_symbol='Em')
        rows=[row(d_maj) for _ in range(28)]+[row(d_add9) for _ in range(9)]+[row(em) for _ in range(23)]
        out=prepare(np.arange(60)/24,rows,tempo=dict(bpm=138.,offset_s=0.))
        symbols=[r['display_candidates'][0]['symbol'] for r in out]
        self.assertNotIn('Dadd9',symbols)
        self.assertEqual(symbols[0],'D')
        self.assertEqual(symbols[-1],'Em')

    def test_tied_multi_candidate_slots_resolved_to_single_canonical_chord(self):
        g_sharp7=dict(root_pc=8,quality='7',pcs=[8,0,3,6],score=1.,symbol='G#7',base_symbol='G#7')
        c_sharp_m7=dict(root_pc=1,quality='m7',pcs=[1,4,8,11],score=1.,symbol='C#m7',base_symbol='C#m7')
        e6=dict(root_pc=4,quality='6',pcs=[4,8,11,1],score=1.,symbol='E6',base_symbol='E6')
        rows=[row(g_sharp7) for _ in range(24)]
        for _ in range(24):
            r=row(c_sharp_m7,[e6])
            r['context']['display_candidates']=[c_sharp_m7,e6]
            rows.append(r)
        out=prepare(np.arange(48)/24,rows,tempo=dict(bpm=130.,offset_s=0.))
        self.assertTrue(all(len(r['display_candidates'])==1 for r in out))
        self.assertEqual(out[-1]['display_candidates'][0]['symbol'],'C#m7')

    def test_silence_bounded_aug_noise_island_is_suppressed(self):
        daug=dict(root_pc=2,quality='aug',pcs=[2,6,10],score=1.,symbol='Daug',base_symbol='Daug')
        empty=dict(root_pc=0,quality='major',pcs=[0,4,7],score=1.,symbol='C',base_symbol='C')
        rows=[]
        for i in range(48):
            if 12<=i<16:
                rows.append(row(daug))
            else:
                r=row(empty)
                r['top3']=[];r['context']['top3']=[];r['context']['display_candidates']=[]
                rows.append(r)
        out=prepare(np.arange(48)/24,rows,tempo=dict(bpm=138.,offset_s=0.))
        self.assertTrue(all(r['display_candidates']==[] for r in out))


if __name__=='__main__':unittest.main()
