import unittest
from evaluate_tutorial_reference import REFERENCES,evaluate
from harmony_engine import QUALITIES
from joint_evidence_review import ROOT,read


class TutorialReferenceTests(unittest.TestCase):
    def test_tab_and_capo_match_reference_pitch_classes(self):
        tuning=[40,45,50,55,59,64]
        for time,(name,root,quality,tab) in REFERENCES.items():
            pcs={(note+fret+1)%12 for note,fret in zip(tuning,tab) if fret is not None}
            expected={(root+1+i)%12 for i in QUALITIES[quality]}
            self.assertEqual(pcs,expected,(time,name))

    def test_extensions_are_not_exact_matches_and_enharmonics_use_root_pc(self):
        reference=dict(concert_root_pc=7,quality='major')
        candidates=[dict(root_pc=7,quality='maj7',score=.9),dict(root_pc=7,quality='major',score=.8)]
        result=evaluate(candidates,reference)
        self.assertFalse(result['exact_top1']);self.assertTrue(result['root_top1']);self.assertTrue(result['exact_top3'])

    def test_saved_evaluation_has_equal_sampling_and_unmodified_weights(self):
        d=read(ROOT/'dataset/integration_review/runs/tutorial_accuracy_20261105_v1/result.json')
        self.assertEqual(len(d['frames']),9)
        self.assertEqual(d['frozen_model']['visual_weight'],.2)
        self.assertTrue(d['frozen_model']['ref_labels_not_used_as_model_input'])
        for row in d['frames']:
            self.assertGreater(row['audio_analysis_frame_count'],0)
            self.assertEqual(row['reference']['capo'],1)
            self.assertEqual(row['reference']['concert_root_pc'],(row['reference']['shape_root_pc']+1)%12)
            self.assertEqual(len(row['audio_only']),len(row['combined']))
        for branch in ['audio','combined']:
            for metric in ['exact_top1','exact_top3','root_top1']:
                self.assertEqual(d['metrics'][branch][metric],sum(row[branch+'_evaluation'][metric] for row in d['frames']))


if __name__=='__main__':unittest.main()
