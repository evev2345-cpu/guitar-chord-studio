import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import numpy as np
import chord_web_server as server
from chord_web_analysis import make_timeline, ROOT


class WebContractTests(unittest.TestCase):
    def test_ranges(self):
        self.assertEqual(server.range_bounds(None, 100), (0, 99, False))
        self.assertEqual(server.range_bounds('bytes=20-39', 100), (20, 39, True))
        self.assertEqual(server.range_bounds('bytes=-10', 100), (90, 99, True))
        self.assertEqual(server.range_bounds('bytes=95-', 100), (95, 99, True))
        for value in ['bytes=100-', 'bytes=40-20', 'bytes=-0', 'bytes=1-2,4-5']:
            with self.assertRaises(ValueError):
                server.range_bounds(value, 100)

    def test_silence_is_not_a_chord_and_edges_remain_unknown(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'silent.npz'
            np.savez(path, times=np.arange(0, 2, .01), note=np.zeros((200, 88)))
            result = make_timeline(path, 2)
            self.assertFalse(result['vision_connected'])
            for rows in result['branches'].values():
                self.assertTrue(all(not r['top3'] for r in rows))
                self.assertEqual(rows[0]['status'], 'audio_edge_no_full_window')
                self.assertTrue(all(r['display']['display_candidate'] is None for r in rows))

    def test_existing_214s_root_tie_preserved(self):
        path = ROOT / 'dataset/integration_review/runs/basic_pitch_20261105_v2/predictions/tutorial_raw.npz'
        result = make_timeline(path, 32)
        row = result['branches']['0.2'][20 * 24]
        roots = {c['root_pc'] for c in row['top3'] if abs(c['score']-row['top3'][0]['score']) < 1e-10}
        self.assertTrue({0, 9}.issubset(roots))
        self.assertGreaterEqual(row['tied_top1_count'], 2)


class HTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.patch = patch.object(server, 'RUNS', Path(cls.tmp.name))
        cls.patch.start()
        cls.jobs_patch = patch.object(server, 'JOBS', {})
        cls.jobs_patch.start()
        cls.http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
        cls.url = f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.jobs_patch.stop()
        cls.patch.stop()
        cls.tmp.cleanup()

    def test_static_and_denied_origin(self):
        with urlopen(self.url) as response:
            self.assertIn('Chord Studio', response.read().decode())
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.url + '/api/demo', data=b'', headers={'Origin': 'https://unrelated.example'}))
        self.assertEqual(caught.exception.code, 403)

    def test_unknown_path_and_invalid_upload(self):
        for suffix in ['/media/../../README.md', '/api/jobs/'+'0'*32]:
            with self.assertRaises(HTTPError) as caught:
                urlopen(self.url + suffix)
            self.assertEqual(caught.exception.code, 404)
        with self.assertRaises(HTTPError) as caught:
            urlopen(Request(self.url + '/api/jobs', data=b''))
        self.assertEqual(caught.exception.code, 413)

    def test_demo_result_and_media_seeking(self):
        job_id = json.load(urlopen(Request(self.url + '/api/demo', data=b'')))['id']
        for _ in range(100):
            job = json.load(urlopen(self.url + '/api/jobs/' + job_id))
            if job['status'] in ('complete', 'error'):
                break
            time.sleep(.05)
        self.assertEqual(job['status'], 'complete', job)
        result = json.load(urlopen(self.url + job['result_url']))
        self.assertEqual(len(result['branches']['0.2']), 768)
        self.assertFalse(result['vision_connected'])
        with urlopen(Request(self.url + job['media_url'], headers={'Range': 'bytes=0-43'})) as response:
            self.assertEqual(response.status, 206)
            self.assertEqual(len(response.read()), 44)
            self.assertTrue(response.headers['Content-Range'].startswith('bytes 0-43/'))


if __name__ == '__main__':
    unittest.main()
