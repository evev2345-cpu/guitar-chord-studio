import copy
import unittest
import numpy as np
from onset_transition import evidence, context_with_bonus, add_layer
from test_chord_presentation import chord, row
from chord_presentation import prepare


class OnsetTransitionTests(unittest.TestCase):
    def fixture(self,change=True,attack=True):
        grid=np.arange(0,2,.01);notes=np.zeros((200,88));onsets=np.zeros_like(notes)
        notes[:,np.array([48,52,55])-21]=.8
        if change:
            notes[100:]=0;notes[100:,np.array([43,47,50])-21]=.8
        if attack:onsets[99:102,np.array([43,47,50])-21]=.95
        return grid,notes,onsets

    def test_repeated_strum_does_not_become_a_chord_change(self):
        grid,notes,onsets=self.fixture(False,True)
        self.assertFalse(evidence(grid,notes,onsets,[1.])[0]['active'])

    def test_onset_and_new_pcs_are_both_required(self):
        grid,notes,onsets=self.fixture()
        e=evidence(grid,notes,onsets,[1.])[0]
        self.assertTrue(e['active']);self.assertIn(2,e['new_pcs']);self.assertIn(11,e['new_pcs'])
        self.assertFalse(evidence(grid,notes,np.zeros_like(onsets),[1.])[0]['active'])

    def test_missing_onsets_and_edges_are_neutral(self):
        grid,notes,onsets=self.fixture()
        self.assertFalse(evidence(grid,notes,None,[1.])[0]['active'])
        self.assertFalse(evidence(grid,notes,onsets,[.1])[0]['active'])

    def test_only_positive_bonus_and_original_scores_are_preserved(self):
        c=chord(0);g=chord(7);r=row(c,[g]);original=copy.deepcopy(r)
        grid,notes,onsets=self.fixture();e=evidence(grid,notes,onsets,[1.])[0]
        result=context_with_bonus(r['context'],r,e)
        self.assertEqual(result['display_candidates'][0]['root_pc'],7)
        self.assertTrue(all(c['onset_bonus']>=0 for c in result['top3']))
        self.assertTrue(all(c['score']==1. for c in result['top3']))
        self.assertEqual(r,original)

    def test_absent_onset_does_not_block_a_sustained_change(self):
        grid,notes,onsets=self.fixture();rows=[]
        for i in range(48):
            r=row(chord(0 if i<24 else 7));r['time_s']=i/24;rows.append(r)
        shown=prepare(np.arange(48)/24,rows)
        for r,p in zip(rows,shown):r['presentation']=p
        result=dict(branches={'0.2':copy.deepcopy(rows)})
        add_layer(result,grid,notes,np.zeros_like(onsets))
        output=result['branches']['0.2']
        self.assertEqual(output[24]['onset_presentation']['display_candidates'][0]['root_pc'],7)
        self.assertTrue(all(a['presentation']==b['presentation'] for a,b in zip(rows,output)))

    def test_equal_pc_m7_sixth_tie_is_not_resolved_by_onset_alone(self):
        a=dict(root_pc=0,quality='6',pcs=[0,4,7,9],score=1.,symbol='C6')
        b=dict(root_pc=9,quality='m7',pcs=[0,4,7,9],score=1.,symbol='Am7')
        ctx=dict(top3=[a,b],display_candidates=[a,b],status='ambiguous')
        e=dict(active=True,onset_peak=1.,novel_pc_weights=[1 if i in [0,4,7,9] else 0 for i in range(12)])
        result=context_with_bonus(ctx,dict(top3=[a,b]),e)
        self.assertEqual(len(result['display_candidates']),2)


if __name__=='__main__':unittest.main()
