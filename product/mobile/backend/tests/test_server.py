import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import sys
import threading
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from protocol import load_verified_snapshot
from server import QrosDemoServer

TOKEN = 'TEST_ONLY_DO_NOT_REUSE_32_CHARS_ABCde12345'
PIN = (ROOT / 'demo/PUBLIC_PIN.txt').read_text().strip()
SNAPSHOT = load_verified_snapshot(ROOT / 'demo/trust_root.json', PIN, ROOT / 'demo/signed_snapshot.json')


class ReadOnlyApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = QrosDemoServer(('127.0.0.1', 0), TOKEN, SNAPSHOT.response)
        cls.thread = threading.Thread(target=cls.srv.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()
        cls.thread.join(timeout=3)

    def send(self, method='GET', path='/v1/demo-snapshot', auth=True, headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.srv.server_port, timeout=3)
        hs = {} if headers is None else dict(headers)
        if auth:
            hs.setdefault('Authorization', 'Bearer ' + TOKEN)
        conn.request(method, path, body, headers=hs)
        resp = conn.getresponse()
        status = resp.status
        body_bytes = resp.read()
        out_headers = dict(resp.getheaders())
        conn.close()
        return status, json.loads(body_bytes), out_headers

    def test_valid_authenticated_read(self):
        code, body, headers = self.send()
        self.assertEqual(code, 200)
        self.assertEqual(body['mode'], 'TEST_ONLY_SYNTHETIC')
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        self.assertIn('no-store', headers.get('Cache-Control', ''))
        self.assertEqual(headers.get('X-Content-Type-Options'), 'nosniff')

    def test_no_auth(self):
        self.assertEqual(self.send(auth=False)[0], 401)

    def test_wrong_token(self):
        self.assertEqual(self.send(headers={'Authorization': 'Bearer ' + 'a'*32})[0], 401)

    def test_actor_spoofing_cannot_override_write_lock(self):
        self.assertEqual(self.send(method='POST', headers={'X-QROS-Actor':'QROS_CORE'},body=b'{}')[0], 405)
        self.assertEqual(self.send(method='PUT', body=b'{}')[0], 405)
        self.assertEqual(self.send(method='PATCH', body=b'{}')[0], 405)
        self.assertEqual(self.send(method='DELETE')[0], 405)

    def test_cors_preflight_denied(self):
        status, _, headers = self.send(method='OPTIONS', headers={'Origin':'https://evil.example'})
        self.assertEqual(status, 405)
        self.assertNotIn('Access-Control-Allow-Origin', headers)

    def test_query_strings_and_path_traversal_denied(self):
        self.assertEqual(self.send(path='/v1/demo-snapshot?project_id=OTHER')[0], 404)
        self.assertEqual(self.send(path='/../../control/HEAD.json')[0], 404)
        self.assertEqual(self.send(path='/v1/admin')[0], 404)

    def test_auth_protects_status(self):
        self.assertEqual(self.send(path='/v1/status',auth=False)[0], 401)
        status, data, _ = self.send(path='/v1/status')
        self.assertEqual(status, 200)
        self.assertEqual(data['engine_connected'], False)

    def test_invalid_token_or_nonloopback_bind_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TOKEN_COMPLEXITY'):
            QrosDemoServer(('127.0.0.1',0),'password',SNAPSHOT.response)
        with self.assertRaisesRegex(ValueError,'LOCAL_ONLY_BIND_REQUIRED'):
            QrosDemoServer(('0.0.0.0',0),TOKEN,SNAPSHOT.response)

    def test_parallel_reads_do_not_create_scientific_state(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            results=list(pool.map(lambda _:self.send(),range(10)))
        self.assertTrue(all(s==200 and d['scientific_authority']=='NONE' for s,d,_ in results))


if __name__ == '__main__':
    unittest.main()
