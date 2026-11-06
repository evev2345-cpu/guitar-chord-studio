import unittest
import numpy as np
from oracle_chord_audit import note_salience,diagnose_frame

class OracleTests(unittest.TestCase):
    def test_dyad_abstains_even_with_exact_reference(self):
        s=np.zeros(12);s[[0,7]]=.5
        self.assertEqual(diagnose_frame(s,'C:(1,5)')['category'],'fewer_than_three_active_pcs')
    def test_relative_root_ambiguity(self):
        s=np.zeros(12);s[[0,4,7,9]]=.25;d=diagnose_frame(s,'A:min7')
        self.assertTrue(d['target_at_top_score']);self.assertIn('C6',d['same_pitch_class_templates'])
    def test_notes_end_exclusive_and_unique_pcs(self):
        notes=[dict(start=0,end=1,midi=60),dict(start=0,end=2,midi=72)]
        s,p=note_salience(notes,1);self.assertEqual(p,[72]);self.assertEqual(s[0],1)
    def test_exact_major(self):
        s=np.zeros(12);s[[0,4,7]]=1/3
        self.assertTrue(diagnose_frame(s,'C:maj')['correct_top1'])

if __name__=='__main__':unittest.main()
