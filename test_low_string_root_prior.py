import unittest
from low_string_root_prior import low_string_support,assess
from test_visual_root_tiebreak import pair

def finger(name,string,fret,mass):return dict(finger=name,cells=[dict(virtual_string_num=string,physical_fret_candidate=fret,position_mass=mass)])

class LowRootTests(unittest.TestCase):
    def test_low_string_higher_weight_same_location_mass(self):
        a=low_string_support([finger('index',6,5,.8)]);b=low_string_support([finger('index',1,5,.8)])
        self.assertGreater(a['root_support'][9],b['root_support'][9])
    def test_unknown_vision_never_forces_root(self):
        r=assess(pair(),[finger('index',6,5,.8)]);self.assertEqual(r['exploratory_tie_order'][0]['symbol'],'Am7');self.assertEqual(r['decision']['candidates'][0]['symbol'],'C6')
    def test_verified_low_string_root_can_rerank_only_tie(self):
        r=assess(pair(),[finger('index',6,5,.8)],visual_status='validated_root_or_voicing');self.assertEqual(r['decision']['candidates'][0]['symbol'],'Am7')
    def test_middle_uncertainty_and_no_double_count(self):
        f=[finger('middle',6,5,.8)];self.assertEqual(low_string_support(f)['root_support'][9],0)
        self.assertAlmostEqual(low_string_support(f,include_uncertain_middle=True)['root_support'][9],.2)
        self.assertAlmostEqual(low_string_support([finger('index',6,5,.8),finger('ring',6,5,.7)])['root_support'][9],.8)
    def test_high_string_alone_does_not_claim_bass_root(self):
        r=assess(pair(),[finger('index',1,5,.8)],visual_status='validated_root_or_voicing');self.assertNotEqual(r['decision']['status'],'root_tie_reranked')

if __name__=='__main__':unittest.main()
