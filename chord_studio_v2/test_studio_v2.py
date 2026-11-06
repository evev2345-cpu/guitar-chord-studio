import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.request import Request, urlopen
import cv2
import numpy as np

import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chord_studio_v2 import server_v2


class StudioV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.runs_patch = patch.object(server_v2, 'RUNS', Path(cls.tmp.name))
        cls.runs_patch.start()
        cls.jobs_patch = patch.object(server_v2, 'JOBS', {})
        cls.jobs_patch.start()
        cls.http = server_v2.ThreadingHTTPServer(('127.0.0.1', 0), server_v2.HandlerV2)
        cls.url = f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.jobs_patch.stop()
        cls.runs_patch.stop()
        cls.tmp.cleanup()

    def test_v2_ui_has_no_tab_placeholder_and_includes_editor_and_calibration(self):
        with urlopen(self.url) as response:
            html = response.read().decode('utf-8')
        self.assertIn('Chord Studio', html)
        self.assertNotIn('타브 제작', html)
        self.assertIn('id="chord-editor"', html)
        self.assertIn('id="start-calibrate"', html)
        self.assertIn('id="separate-toggle"', html)

    def test_demo_and_segment_chord_edit_persistence(self):
        job_id = json.load(urlopen(Request(self.url + '/api/demo', data=b'')))['id']
        for _ in range(100):
            job = json.load(urlopen(self.url + '/api/jobs/' + job_id))
            if job['status'] in ('complete', 'error'):
                break
            time.sleep(0.05)
        self.assertEqual(job['status'], 'complete', job)
        self.assertEqual(job.get('separation_status'), 'separated_htdemucs_6s')

        edit_payload = json.dumps({
            'window': '0.2',
            'start_s': 2.0,
            'end_s': 4.0,
            'root_pc': 6,
            'quality': 'm7',
            'bass_pc': None,
        }).encode('utf-8')
        req = Request(
            f'{self.url}/api/jobs/{job_id}/edit',
            data=edit_payload,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        edit_res = json.load(urlopen(req))
        self.assertGreater(edit_res['edited_frames'], 0)
        self.assertEqual(edit_res['candidate']['root_pc'], 6)
        self.assertEqual(edit_res['candidate']['symbol'], 'Gbm7')

        updated = json.load(urlopen(self.url + job['result_url']))
        self.assertEqual(len(updated.get('user_edits', [])), 1)
        target_rows = [r for r in updated['branches']['0.2'] if 2.0 <= r['time_s'] < 3.9]
        self.assertTrue(all(r['presentation']['display_candidates'][0]['symbol'] == 'Gbm7' for r in target_rows))
        self.assertTrue(all(r['presentation']['status'] == 'user_edited_segment' for r in target_rows))

    def test_4corner_calibration_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / 'dummy.mp4'
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            writer = cv2.VideoWriter(str(video_path), fourcc, 24.0, (640, 360))
            for _ in range(10):
                frame = np.full((360, 640, 3), 120, dtype=np.uint8)
                writer.write(frame)
            writer.release()

            corners = [[520, 120], [200, 125], [200, 185], [520, 175]]
            cal = server_v2.build_calibration_from_4corners(video_path, 0.1, corners, capo_candidate=1, total_frets=20)
            self.assertEqual(cal['image_size'], [640, 360])
            self.assertEqual(len(cal['frets']), 13)
            self.assertEqual(cal['geometry_status'], 'user_manual_4point_provisional')
            self.assertEqual(cal['perspective_k'], 0.0)

            # Test with perspective warping
            cal_warped = server_v2.build_calibration_from_4corners(video_path, 0.1, corners, total_frets=22, perspective_k=0.25)
            self.assertEqual(cal_warped['total_frets'], 22)
            self.assertAlmostEqual(cal_warped['perspective_k'], 0.25)
            # Fret 12 position should shift due to perspective k > 0
            self.assertNotEqual(cal['frets'][12]['endpoints'][0][0], cal_warped['frets'][12]['endpoints'][0][0])


if __name__ == '__main__':
    unittest.main()
